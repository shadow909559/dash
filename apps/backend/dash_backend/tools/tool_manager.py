"""Tool Manager - orchestrates tool execution, LLM function calling,
and the tool lifecycle.

Integrates the ToolRegistry, ToolExecutor, and LLM service to enable
the AI agent to decide when to use tools, execute them safely, and
return results for the LLM to format into final responses.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import ToolContext
from dash_backend.tools.tool_executor import ToolExecutor
from dash_backend.tools.tool_registry import get_registry
from dash_backend.tools.tool_result import ToolEvent, ToolResult, ToolStatus

logger = get_logger(__name__)


class ToolCallRequest:
    """Represents an LLM's request to call a tool.

    Parsed from the LLM function_call / tool_calls response.
    """

    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        call_id: str | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.arguments = arguments
        self.call_id = call_id or f"call_{tool_name}"

    @classmethod
    def from_openai_tool_call(cls, tool_call: dict[str, Any]) -> "ToolCallRequest":
        """Parse an OpenAI tool_calls entry."""
        function_info = tool_call.get("function", {})
        try:
            arguments = json.loads(function_info.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            arguments = {}

        return cls(
            tool_name=function_info.get("name", ""),
            arguments=arguments,
            call_id=tool_call.get("id", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "call_id": self.call_id,
        }


class ToolManager:
    """Central orchestrator for the tool-calling AI agent.

    Responsibilities:
        1. Provide tool definitions to the LLM
        2. Parse tool calls from LLM responses
        3. Execute tools with safety checks
        4. Return tool results for LLM formatting
        5. Stream lifecycle events to the frontend
    """

    def __init__(self) -> None:
        self._registry = get_registry()
        self._executor = ToolExecutor()

    # ──────────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────────

    @property
    def registry(self):
        return self._registry

    @property
    def executor(self):
        return self._executor

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI-compatible format."""
        return self._registry.get_openai_tools()

    def get_tool(self, name: str):
        """Get a registered tool by name."""
        return self._registry.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools with their specs."""
        return self._registry.list_tools()

    # ──────────────────────────────────────────────
    # Tool Call Parsing
    # ──────────────────────────────────────────────

    def parse_tool_calls(
        self,
        llm_response: dict[str, Any],
    ) -> list[ToolCallRequest]:
        """Parse tool calls from an LLM response.

        Supports both OpenAI `tool_calls` and Ollama function-calling formats.

        Args:
            llm_response: The LLM response dict (a single choice).

        Returns:
            List of ToolCallRequest objects.
        """
        tool_calls: list[ToolCallRequest] = []

        # OpenAI format: response["message"]["tool_calls"]
        message = llm_response.get("message", llm_response)
        raw_calls = message.get("tool_calls", [])

        if raw_calls:
            for tc in raw_calls:
                try:
                    tool_calls.append(ToolCallRequest.from_openai_tool_call(tc))
                except Exception as exc:
                    logger.warning("Failed to parse tool call: %s", exc)

        return tool_calls

    # ──────────────────────────────────────────────
    # Tool Execution with Streaming Events
    # ──────────────────────────────────────────────

    async def execute_tool_stream(
        self,
        tool_call: ToolCallRequest,
        context: ToolContext,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Execute a tool and stream lifecycle events.

        Yields (event_type, data) tuples suitable for WebSocket messages:
            - "tool.started":  Tool execution started
            - "tool.progress": Progress update
            - "tool.finished": Execution completed
            - "tool.error":    Execution failed
            - "tool.confirmation_required": Needs user confirmation

        Args:
            tool_call: Parsed tool call from the LLM.
            context: Execution context.

        Yields:
            (event_type, data_dict) tuples.
        """
        tool = self._registry.get(tool_call.tool_name)
        if tool is None:
            yield (
                ToolEvent.ERROR.value,
                ToolResult(
                    tool_name=tool_call.tool_name,
                    status=ToolStatus.ERROR,
                    error_message=f"Unknown tool: '{tool_call.tool_name}'",
                ).to_dict(),
            )
            return

        async for event, result in self._executor.execute(
            tool, context, **tool_call.arguments
        ):
            data = result.to_dict()
            data["tool_call"] = tool_call.to_dict()
            yield event.value, data

    # ──────────────────────────────────────────────
    # Tool Execution (Sync Result)
    # ──────────────────────────────────────────────

    async def execute_tool(
        self,
        tool_call: ToolCallRequest,
        context: ToolContext,
    ) -> ToolResult:
        """Execute a tool and return the final result.

        This is a convenience wrapper that collects streamed events
        and returns only the final result.

        Args:
            tool_call: Parsed tool call from the LLM.
            context: Execution context.

        Returns:
            Final ToolResult (FINISHED or ERROR).
        """
        final_result: ToolResult | None = None
        async for _event, result in self.execute_tool_stream(tool_call, context):
            final_result = result

        return final_result or ToolResult(
            tool_name=tool_call.tool_name,
            status=ToolStatus.ERROR,
            error_message="Tool execution produced no result",
        )

    # ──────────────────────────────────────────────
    # Confirmation Handling
    # ──────────────────────────────────────────────

    async def confirm_execution(
        self,
        confirmation_token: str,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Confirm a pending tool execution.

        Args:
            confirmation_token: Token from a CONFIRMATION_REQUIRED event.

        Yields:
            (event_type, data_dict) tuples.
        """
        async for event, result in self._executor.execute_confirmed(
            confirmation_token
        ):
            yield event.value, result.to_dict()

    async def reject_execution(
        self,
        confirmation_token: str,
    ) -> dict[str, Any]:
        """Reject a pending tool execution.

        Args:
            confirmation_token: Token from a CONFIRMATION_REQUIRED event.

        Returns:
            Final result dict.
        """
        result = await self._executor.reject_confirmation(confirmation_token)
        return result.to_dict()

    # ──────────────────────────────────────────────
    # Tool Result Formatting for LLM
    # ──────────────────────────────────────────────

    def format_result_for_llm(
        self,
        tool_call: ToolCallRequest,
        result: ToolResult,
    ) -> dict[str, Any]:
        """Format a tool result for inclusion in the LLM messages array.

        Returns a message dict with role "tool" suitable for
        OpenAI-compatible APIs.

        Args:
            tool_call: The original tool call.
            result: The execution result.

        Returns:
            Message dict: {"role": "tool", "tool_call_id": ..., "content": ...}
        """
        content = json.dumps(
            {
                "status": result.status.value,
                "output": result.output,
                "summary": result.summary,
                "error": result.error_message if result.is_error else None,
                "duration_ms": result.duration_ms,
            },
            indent=2,
        )

        return {
            "role": "tool",
            "tool_call_id": tool_call.call_id,
            "content": content,
        }

    def format_function_result_for_llm(
        self,
        tool_call: ToolCallRequest,
        result: ToolResult,
    ) -> dict[str, Any]:
        """Format a tool result for Ollama/function-calling format.

        Returns a message dict compatible with Ollama's function
        calling response format.

        Args:
            tool_call: The original tool call.
            result: The execution result.

        Returns:
            Message dict with role "tool".
        """
        content = json.dumps(
            {
                "status": result.status.value,
                "output": result.output,
                "summary": result.summary,
                "error": result.error_message if result.is_error else None,
            },
            indent=2,
        )

        return {
            "role": "tool",
            "content": content,
            "name": tool_call.tool_name,
        }

    def format_tool_results_for_llm(
        self,
        tool_calls: list[ToolCallRequest],
        results: list[ToolResult],
    ) -> list[dict[str, Any]]:
        """Format multiple tool results for the LLM message array.

        Args:
            tool_calls: List of tool call requests.
            results: Corresponding list of results (same order).

        Returns:
            List of message dicts to append to the LLM conversation.
        """
        messages: list[dict[str, Any]] = []
        for tc, result in zip(tool_calls, results):
            messages.append(self.format_result_for_llm(tc, result))
        return messages


# Global singleton manager
_manager: ToolManager | None = None


def get_tool_manager() -> ToolManager:
    """Return the global ToolManager singleton."""
    global _manager
    if _manager is None:
        _manager = ToolManager()
    return _manager