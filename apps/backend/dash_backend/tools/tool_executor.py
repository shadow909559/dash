"""Tool Executor - handles safe execution of tools with timeout, error handling,
and permission checks.

Provides the execution layer that wraps tool calls with lifecycle
management, progress reporting, and confirmation workflows.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, PermissionLevel, ToolContext
from dash_backend.tools.tool_result import ToolEvent, ToolResult, ToolStatus

logger = get_logger(__name__)

# Default timeout for tool execution (seconds)
DEFAULT_TOOL_TIMEOUT = 30.0

# Commands that always require confirmation
DANGEROUS_COMMANDS = [
    "rm", "del", "format", "shutdown", "reboot",
    "git push", "git reset", "git push --force",
    "npm install", "pip install", "apt install", "choco install",
    "sudo", "systemctl", "regedit", "diskpart",
]


class ToolExecutor:
    """Executes tools with safety checks, timeouts, and lifecycle events.

    The executor wraps each tool call with:
        1. Permission check (auto vs confirm vs restricted)
        2. Argument validation
        3. Timeout enforcement
        4. Progress event emission
        5. Error handling and result formatting
    """

    def __init__(self, timeout: float = DEFAULT_TOOL_TIMEOUT) -> None:
        self._timeout = timeout
        self._pending_confirmations: dict[str, dict[str, Any]] = {}

    # ──────────────────────────────────────────────
    # Execution
    # ──────────────────────────────────────────────

    async def execute(
        self,
        tool: BaseTool,
        context: ToolContext,
        **kwargs: Any,
    ) -> AsyncIterator[tuple[ToolEvent, ToolResult]]:
        """Execute a tool with full lifecycle management.

        Yields (event, result) tuples for each lifecycle stage:
            - STARTED: Execution has begun
            - PROGRESS: Intermediate progress updates
            - FINISHED: Execution completed successfully
            - ERROR: Execution failed
            - CONFIRMATION_REQUIRED: User confirmation needed

        Args:
            tool: The tool instance to execute.
            context: Execution context (user, session, etc.).
            **kwargs: Tool-specific arguments.

        Yields:
            (ToolEvent, ToolResult) tuples.
        """
        tool_name = tool.name
        started_at = datetime.now(timezone.utc)

        # ── Step 1: Validate arguments ──
        validation_errors = tool.validate_args(**kwargs)
        if validation_errors:
            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error_message="; ".join(validation_errors),
                started_at=started_at,
            )
            yield ToolEvent.ERROR, result
            return

        # ── Step 2: Permission check ──
        if tool.permission_level >= PermissionLevel.CONFIRM:
            confirmation_token = str(uuid.uuid4())
            self._pending_confirmations[confirmation_token] = {
                "tool": tool,
                "context": context,
                "kwargs": kwargs,
                "started_at": started_at,
            }

            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.PENDING_CONFIRMATION,
                confirmation_token=confirmation_token,
                started_at=started_at,
                summary=f"Tool '{tool_name}' requires your confirmation to proceed.",
            )
            yield ToolEvent.CONFIRMATION_REQUIRED, result
            return

        # ── Step 3: Execute ──
        async for event, result in self._run_tool(tool, context, started_at, **kwargs):
            yield event, result

    async def execute_confirmed(
        self,
        confirmation_token: str,
    ) -> AsyncIterator[tuple[ToolEvent, ToolResult]]:
        """Execute a tool after user confirmation.

        Args:
            confirmation_token: Token from a previous CONFIRMATION_REQUIRED event.

        Yields:
            (ToolEvent, ToolResult) tuples.
        """
        pending = self._pending_confirmations.pop(confirmation_token, None)
        if pending is None:
            result = ToolResult(
                tool_name="unknown",
                status=ToolStatus.ERROR,
                error_message="Invalid or expired confirmation token.",
            )
            yield ToolEvent.ERROR, result
            return

        tool: BaseTool = pending["tool"]
        context: ToolContext = pending["context"]
        kwargs: dict[str, Any] = pending["kwargs"]
        started_at: datetime = pending["started_at"]

        async for event, result in self._run_tool(tool, context, started_at, **kwargs):
            yield event, result

    async def reject_confirmation(self, confirmation_token: str) -> ToolResult:
        """Reject a pending tool execution.

        Args:
            confirmation_token: Token from a previous CONFIRMATION_REQUIRED event.

        Returns:
            ToolResult with REJECTED status.
        """
        pending = self._pending_confirmations.pop(confirmation_token, None)
        if pending is None:
            return ToolResult(
                tool_name="unknown",
                status=ToolStatus.ERROR,
                error_message="Invalid or expired confirmation token.",
            )

        return ToolResult(
            tool_name=pending["tool"].name,
            status=ToolStatus.REJECTED,
            summary="Tool execution was rejected by the user.",
        )

    # ──────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────

    async def _run_tool(
        self,
        tool: BaseTool,
        context: ToolContext,
        started_at: datetime,
        **kwargs: Any,
    ) -> AsyncIterator[tuple[ToolEvent, ToolResult]]:
        """Run a tool with timeout and error handling."""
        tool_name = tool.name

        # Emit STARTED
        start_result = ToolResult(
            tool_name=tool_name,
            status=ToolStatus.SUCCESS,
            started_at=started_at,
            summary=f"Executing '{tool_name}'...",
            output={"arguments": kwargs},
        )
        yield ToolEvent.STARTED, start_result

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                tool.execute(context, **kwargs),
                timeout=self._timeout,
            )

            # Ensure result has proper timestamps
            if result.started_at is None:
                result.started_at = started_at
            if result.finished_at is None:
                result.finished_at = datetime.now(timezone.utc)
            if not result.duration_ms and result.started_at and result.finished_at:
                delta = result.finished_at - result.started_at
                result.duration_ms = delta.total_seconds() * 1000.0

            if result.is_success:
                yield ToolEvent.FINISHED, result
            else:
                yield ToolEvent.ERROR, result

        except asyncio.TimeoutError:
            finished_at = datetime.now(timezone.utc)
            delta = finished_at - started_at
            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.TIMEOUT,
                error_message=f"Tool '{tool_name}' timed out after {self._timeout}s",
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=delta.total_seconds() * 1000.0,
            )
            yield ToolEvent.ERROR, result

        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            delta = finished_at - started_at
            logger.exception("Tool '%s' execution failed", tool_name)
            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error_message=str(exc),
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=delta.total_seconds() * 1000.0,
            )
            yield ToolEvent.ERROR, result

    @staticmethod
    def check_dangerous_command(command: str) -> bool:
        """Check if a command string contains dangerous operations.

        Args:
            command: The command string to check.

        Returns:
            True if the command is considered dangerous.
        """
        command_lower = command.lower().strip()
        for dangerous in DANGEROUS_COMMANDS:
            if command_lower.startswith(dangerous) or f" {dangerous}" in command_lower:
                return True
        return False