"""Adaptive Executor - Autonomous execution with failure recovery.

Orchestrates task execution with dynamic adaptation based on
results, failures, and changing conditions.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from dash_backend.logging_config import get_logger
from dash_backend.brain.tool_selector import DynamicToolSelector
from dash_backend.brain.skill_router import BrainSkillRouter
from dash_backend.llm.service import build_chat_messages, collect_streamed_response

logger = get_logger(__name__)


class AdaptiveExecutor:
    """Autonomous task executor with adaptation and recovery.

    Features:
    - Retry with exponential backoff
    - Alternative approach generation on failure
    - Partial result preservation
    - Timeout management
    - Resource-aware scheduling
    - Failure recovery strategies
    """

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_TIMEOUT = 120.0

    def __init__(self):
        self.tool_selector = DynamicToolSelector()
        self.skill_router = BrainSkillRouter()

    async def execute_task(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
        max_retries: int = MAX_RETRIES,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Execute a task with automatic retry and adaptation.

        Args:
            task_description: Description of the task to execute
            context: Optional execution context
            max_retries: Maximum number of retry attempts
            timeout: Timeout in seconds

        Returns:
            Execution result dict
        """
        context = context or {}
        attempts = []
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._execute_once(task_description, context, attempt),
                    timeout=timeout,
                )

                if result.get("status") == "ok":
                    return {
                        "status": "ok",
                        "result": result.get("result"),
                        "attempts": attempt + 1,
                        "retry_count": attempt,
                    }

                last_error = result.get("error", "Unknown error")
                attempts.append(result)

            except asyncio.TimeoutError:
                last_error = "Task timed out"
                attempts.append({"status": "error", "error": "timeout"})
            except Exception as exc:
                last_error = str(exc)
                attempts.append({"status": "error", "error": str(exc)})

            if attempt < max_retries:
                delay = self.BASE_RETRY_DELAY * (2 ** attempt)
                logger.info(
                    "Retrying task (attempt %d/%d) after %.1fs: %s",
                    attempt + 1, max_retries, delay, last_error,
                )
                await asyncio.sleep(delay)

        return {
            "status": "error",
            "error": last_error,
            "attempts": attempts,
            "retry_count": max_retries,
        }

    async def _execute_once(
        self,
        task_description: str,
        context: Dict[str, Any],
        attempt: int,
    ) -> Dict[str, Any]:
        """Execute a single attempt of a task."""
        # Try tool execution first
        from dash_backend.tools.tool_manager import get_tool_manager
        tool_manager = get_tool_manager()

        tool = await self.tool_selector.select_tool(
            task_description,
            context=str(context),
        )

        if tool:
            tool_name = tool.get("name", "")
            tool_instance = tool_manager.get_tool(tool_name)
            if tool_instance:
                from dash_backend.tools.base_tool import ToolContext
                tool_context = ToolContext(
                    user_id=context.get("user_id", "unknown"),
                    conversation_id=context.get("conversation_id"),
                )
                try:
                    result = await tool_instance.execute(
                        context=tool_context,
                        **context.get("args", {}),
                    )
                    return {
                        "status": "ok" if result.status.value == "success" else "error",
                        "result": result.output if hasattr(result, "output") else result.model_dump(),
                        "tool": tool_name,
                    }
                except Exception as exc:
                    logger.warning("Tool %s failed: %s", tool_name, exc)
                    return {"status": "error", "error": str(exc), "tool": tool_name}

        # Fall back to skill routing
        from dash_backend.skills.skill_router import SkillContext
        skill_context = SkillContext(
            user_id=context.get("user_id"),
            session_id=context.get("session_id"),
            extra=context.get("extra", {}),
        )

        result = await self.skill_router.route(
            intent=task_description,
            args=context.get("args", {}),
            context=skill_context,
        )

        return result

    @staticmethod
    async def generate_alternative_strategy(
        task_description: str,
        failed_approach: str,
        error_message: str,
    ) -> Optional[str]:
        """Generate an alternative strategy when the current one fails."""
        prompt = (
            f"Task: {task_description}\n\n"
            f"Failed approach: {failed_approach}\n"
            f"Error: {error_message}\n\n"
            "Suggest a different approach to accomplish this task. "
            "Consider what went wrong and how to avoid it."
        )

        messages = build_chat_messages(
            system_prompt="You generate alternative strategies for failed tasks.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages)
            return result.strip()
        except Exception as exc:
            logger.warning("Alternative strategy generation failed: %s", exc)
            return None

    @staticmethod
    def should_retry(result: Dict[str, Any]) -> bool:
        """Determine if a task should be retried based on the result."""
        status = result.get("status")
        if status == "ok":
            return False

        error = result.get("error", "").lower()
        # Don't retry certain errors
        non_retryable = [
            "permission denied",
            "not found",
            "invalid input",
            "not implemented",
            "unauthorized",
        ]
        for pattern in non_retryable:
            if pattern in error:
                return False

        return True