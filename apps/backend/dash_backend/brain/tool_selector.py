"""Dynamic Tool Selector - Chooses optimal tools for tasks.

Analyzes task requirements, available tools, and context to
select the best tool for each operation.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.llm.service import build_chat_messages, collect_streamed_response
from dash_backend.tools.tool_manager import get_tool_manager

logger = get_logger(__name__)


class DynamicToolSelector:
    """Selects tools dynamically based on task requirements and context.

    Features:
    - Semantic tool matching against task descriptions
    - Fallback chains for tool failures
    - Parameter optimization based on context
    - Tool composition for complex tasks
    - Learning from past tool selections
    """

    @staticmethod
    async def select_tool(
        task_description: str,
        available_tools: Optional[List[Dict[str, Any]]] = None,
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Select the best tool for a given task.

        Args:
            task_description: Description of what needs to be done
            available_tools: List of available tool dicts. If None, fetches from ToolManager
            context: Optional additional context

        Returns:
            Best matching tool dict, or None if no suitable tool found
        """
        if available_tools is None:
            tool_manager = get_tool_manager()
            available_tools = tool_manager.list_tools()

        if not available_tools:
            return None

        prompt = (
            f"Task: {task_description}\n\n"
        )
        if context:
            prompt += f"Context: {context}\n\n"

        prompt += "Available tools:\n"
        for i, tool in enumerate(available_tools):
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")[:100]
            params = tool.get("parameters", [])
            param_names = [p.get("name", "arg") for p in params[:5]]
            prompt += f"{i+1}. {name}: {desc} (params: {', '.join(param_names)})\n"

        prompt += (
            "\nSelect the best tool. Return JSON:\n"
            '{"tool_index": int, "confidence": float, "reasoning": str}'
        )

        messages = build_chat_messages(
            system_prompt="You select the best tool for each task based on capability and relevance.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages)
            result = result.strip()
            if result.startswith("```"):
                parts = result.split("```")
                if len(parts) >= 2:
                    result = parts[1].strip()
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                idx = parsed.get("tool_index")
                if isinstance(idx, int) and 0 <= idx < len(available_tools):
                    return {
                        **available_tools[idx],
                        "selection_confidence": parsed.get("confidence", 0.5),
                        "selection_reasoning": parsed.get("reasoning", ""),
                    }
        except Exception as exc:
            logger.warning("Tool selection failed: %s", exc)

        # Fallback: Simple keyword matching
        task_lower = task_description.lower()
        best_match = None
        best_score = 0

        for tool in available_tools:
            score = 0
            name = tool.get("name", "").lower()
            desc = tool.get("description", "").lower()

            if name in task_lower:
                score += 3
            for word in task_lower.split():
                if word in name:
                    score += 2
                if word in desc:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = tool

        return best_match

    @staticmethod
    async def build_tool_chain(
        task_description: str,
        available_tools: List[Dict[str, Any]],
        max_chain_length: int = 5,
    ) -> List[Dict[str, Any]]:
        """Build a chain of tools for complex multi-step tasks.

        Returns ordered list of tools to execute sequentially.
        """
        if not available_tools:
            return []

        tools_text = "\n".join(
            f"{i+1}. {t.get('name')}: {t.get('description', '')[:80]}"
            for i, t in enumerate(available_tools[:15])
        )

        prompt = (
            f"Task: {task_description}\n\n"
            f"Available tools:\n{tools_text}\n\n"
            f"Create a chain of up to {max_chain_length} tools to accomplish this task. "
            "Return JSON array of tool indices in execution order:\n"
            '[{"tool_index": int, "reason": str}, ...]'
        )

        messages = build_chat_messages(
            system_prompt="You create tool chains for multi-step tasks.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages)
            result = result.strip()
            if result.startswith("```"):
                parts = result.split("```")
                if len(parts) >= 2:
                    result = parts[1].strip()
            parsed = json.loads(result)
            if isinstance(parsed, list):
                chain = []
                for item in parsed[:max_chain_length]:
                    idx = item.get("tool_index")
                    if isinstance(idx, int) and 0 <= idx < len(available_tools):
                        chain.append(available_tools[idx])
                return chain
        except Exception as exc:
            logger.warning("Tool chain building failed: %s", exc)

        return []

    @staticmethod
    def find_fallback_tool(
        failed_tool_name: str,
        available_tools: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Find a fallback tool when the primary selection fails."""
        failed_lower = failed_tool_name.lower()

        # Look for similar tools
        for tool in available_tools:
            name = tool.get("name", "").lower()
            if name != failed_lower:
                # Check if they share keywords
                failed_keywords = set(failed_lower.split("_"))
                tool_keywords = set(name.split("_"))
                if failed_keywords & tool_keywords:
                    return tool

        # Return the first tool with different name as last resort
        for tool in available_tools:
            if tool.get("name", "").lower() != failed_lower:
                return tool

        return None