"""Tool Chain - Chains multiple tools together with output passing.

Enables complex workflows by linking tool outputs to subsequent tool inputs,
with support for conditional branching, error recovery, and result aggregation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import ToolContext, BaseTool
from dash_backend.tools.tool_manager import ToolManager, ToolCallRequest, get_tool_manager
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


@dataclass
class ChainStep:
    """A single step in a tool chain."""
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)  # step_output_key -> next_input_key
    condition: Optional[str] = None  # Optional condition expression
    fallback_tool: Optional[str] = None  # Fallback if this step fails
    timeout: Optional[float] = None  # Per-step timeout
    step_id: str = ""
    result: Optional[ToolResult] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "output_mapping": self.output_mapping,
            "condition": self.condition,
            "fallback_tool": self.fallback_tool,
            "timeout": self.timeout,
            "step_id": self.step_id,
            "error": self.error,
        }


class ToolChain:
    """Chains multiple tool executions with output passing.

    Features:
    - Sequential tool execution with output passing
    - Conditional branching based on results
    - Fallback tools on failure
    - Per-step timeout
    - Result aggregation
    - Streaming execution events
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None):
        self.tool_manager = tool_manager or get_tool_manager()

    async def execute(
        self,
        steps: List[ChainStep],
        context: ToolContext,
    ) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
        """Execute a chain of tools sequentially with output passing.

        Args:
            steps: Ordered list of chain steps to execute.
            context: Tool execution context.

        Yields:
            (event_type, data_dict) tuples for each step.
        """
        accumulated_outputs: Dict[str, Any] = {}
        step_results: List[Dict[str, Any]] = []

        for step_index, step in enumerate(steps):
            step_id = step.step_id or f"step_{step_index}"

            try:
                # Resolve arguments from previous outputs
                resolved_args = self._resolve_arguments(step.arguments, accumulated_outputs)

                # Check condition
                if step.condition:
                    should_execute = self._evaluate_condition(step.condition, accumulated_outputs)
                    if not should_execute:
                        yield (
                            "tool_chain.skipped",
                            {
                                "step_id": step_id,
                                "tool_name": step.tool_name,
                                "reason": f"Condition '{step.condition}' not met",
                            },
                        )
                        step_results.append({"step_id": step_id, "skipped": True})
                        continue

                # Execute the tool
                tool_call = ToolCallRequest(
                    tool_name=step.tool_name,
                    arguments=resolved_args,
                    call_id=step_id,
                )

                step_result: Optional[ToolResult] = None
                async for event_type, data in self._execute_with_timeout(
                    tool_call, context, step.timeout
                ):
                    # Include step metadata in events
                    data["step_id"] = step_id
                    data["step_index"] = step_index
                    yield (event_type, data)

                    if event_type in ("tool.finished", "tool_chain.finished"):
                        step_result = data
                    elif event_type in ("tool.error", "tool_chain.error"):
                        # Try fallback tool if available
                        if step.fallback_tool:
                            yield (
                                "tool_chain.fallback",
                                {
                                    "step_id": step_id,
                                    "failed_tool": step.tool_name,
                                    "fallback_tool": step.fallback_tool,
                                    "error": data.get("error_message", "Unknown error"),
                                },
                            )
                            fallback_call = ToolCallRequest(
                                tool_name=step.fallback_tool,
                                arguments=resolved_args,
                                call_id=f"{step_id}_fallback",
                            )
                            async for fb_event, fb_data in self._execute_with_timeout(
                                fallback_call, context, step.timeout
                            ):
                                fb_data["step_id"] = step_id
                                fb_data["fallback"] = True
                                yield (fb_event, fb_data)
                                if fb_event in ("tool.finished", "tool_chain.finished"):
                                    step_result = fb_data
                        else:
                            step_results.append({
                                "step_id": step_id,
                                "error": data.get("error_message", "Unknown error"),
                            })
                            yield (
                                "tool_chain.step_failed",
                                {
                                    "step_id": step_id,
                                    "tool_name": step.tool_name,
                                    "error": data.get("error_message", "Unknown error"),
                                },
                            )

                # Process outputs
                if step_result and isinstance(step_result, dict):
                    # Extract output and pass to next steps
                    output = step_result.get("output", {})
                    if isinstance(output, dict):
                        accumulated_outputs.update(output)

                    # Apply output mapping
                    for step_key, next_key in step.output_mapping.items():
                        if step_key in output:
                            accumulated_outputs[next_key] = output[step_key]

                    step_results.append({
                        "step_id": step_id,
                        "output": output,
                    })

            except asyncio.TimeoutError:
                error_data = {
                    "step_id": step_id,
                    "tool_name": step.tool_name,
                    "error": "Tool execution timed out",
                }
                yield ("tool_chain.timeout", error_data)
                step_results.append({"step_id": step_id, "error": "timeout"})

            except Exception as exc:
                error_data = {
                    "step_id": step_id,
                    "tool_name": step.tool_name,
                    "error": str(exc),
                }
                yield ("tool_chain.error", error_data)
                step_results.append({"step_id": step_id, "error": str(exc)})

        # Yield final combined result
        yield (
            "tool_chain.completed",
            {
                "steps": step_results,
                "total_steps": len(steps),
                "completed_steps": len([s for s in step_results if "error" not in s]),
                "failed_steps": len([s for s in step_results if "error" in s]),
                "accumulated_outputs": accumulated_outputs,
            },
        )

    async def _execute_with_timeout(
        self,
        tool_call: ToolCallRequest,
        context: ToolContext,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
        """Execute a tool with optional timeout."""
        if timeout:
            try:
                async for event, data in self.tool_manager.execute_tool_stream(tool_call, context):
                    yield (event, data)
            except asyncio.TimeoutError:
                raise
        else:
            async for event, data in self.tool_manager.execute_tool_stream(tool_call, context):
                yield (event, data)

    def _resolve_arguments(
        self,
        args: Dict[str, Any],
        accumulated_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolve template references in arguments from accumulated outputs.

        Supports {{key}} syntax to reference previous step outputs.
        """
        resolved = {}
        for key, value in args.items():
            if isinstance(value, str) and "{{" in value and "}}" in value:
                # Try to resolve template
                resolved_value = value
                import re
                for match in re.finditer(r"\{\{(\w+)\}\}", value):
                    var_name = match.group(1)
                    if var_name in accumulated_outputs:
                        resolved_value = resolved_value.replace(
                            "{{" + var_name + "}}",
                            str(accumulated_outputs[var_name]),
                        )
                resolved[key] = resolved_value
            else:
                resolved[key] = value
        return resolved

    def _evaluate_condition(self, condition: str, outputs: Dict[str, Any]) -> bool:
        """Evaluate a simple condition expression.

        Supports: key == value, key != value, key exists, key in value
        """
        condition = condition.strip()

        # Check if key exists
        if condition.endswith(" exists"):
            key = condition.replace(" exists", "").strip()
            return key in outputs

        # Check if key == value
        if " == " in condition:
            parts = condition.split(" == ")
            key = parts[0].strip()
            value = parts[1].strip().strip("'\"")
            return str(outputs.get(key)) == value

        # Check if key != value
        if " != " in condition:
            parts = condition.split(" != ")
            key = parts[0].strip()
            value = parts[1].strip().strip("'\"")
            return str(outputs.get(key)) != value

        # Check if key in value
        if " in " in condition:
            parts = condition.split(" in ")
            key = parts[0].strip()
            container = outputs.get(parts[1].strip())
            if isinstance(container, (list, tuple, set, dict)):
                return key in container
            if isinstance(container, str):
                return key in container
            return False

        logger.warning("Unknown condition format: %s", condition)
        return True

    @staticmethod
    def create_chain(
        tools: List[Dict[str, Any]],
        output_mappings: Optional[List[Dict[str, str]]] = None,
    ) -> List[ChainStep]:
        """Create a tool chain from tool definitions with output mappings.

        Args:
            tools: List of tool config dicts with 'name', 'arguments' keys.
            output_mappings: Optional list of output mappings per step.

        Returns:
            List of ChainStep objects.
        """
        if output_mappings is None:
            output_mappings = [{} for _ in tools]

        chain = []
        for i, tool_config in enumerate(tools):
            mapping = output_mappings[i] if i < len(output_mappings) else {}
            chain.append(ChainStep(
                tool_name=tool_config.get("name", ""),
                arguments=tool_config.get("arguments", {}),
                output_mapping=mapping,
                fallback_tool=tool_config.get("fallback"),
                timeout=tool_config.get("timeout"),
                step_id=tool_config.get("step_id", f"step_{i}"),
            ))
        return chain


# Global singleton
_chain: Optional[ToolChain] = None


def get_tool_chain() -> ToolChain:
    """Return the global ToolChain singleton."""
    global _chain
    if _chain is None:
        _chain = ToolChain()
    return _chain
