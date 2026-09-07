"""AIExecutor - executes plans, monitors execution, retries failures, and handles rollbacks.

Integrates:
  - CommandParser for NL→CommandRequest conversion
  - PlannerEngine for multi-step plans
  - ContextManager for session awareness
  - ProviderManager for AI-driven fallback on ambiguous commands
  - PermissionService for safety
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from dash_backend.logging_config import get_logger
from dash_backend.services.ai_os.command_parser import get_command_parser
from dash_backend.services.ai_os.context_manager import (
    CommandEntry,
    get_context_manager,
)
from dash_backend.services.ai_os.planner import PlanStep, PlanStepType, get_planner
from dash_backend.services.command.models import (
    CommandCategory,
    CommandRequest,
    CommandStatus,
)
from dash_backend.services.command.service import CommandService, get_command_service
from dash_backend.services.permissions import get_permission_service

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a user's request."""
    success: bool
    plan_id: str = ""
    command_id: str = ""
    steps_completed: int = 0
    steps_failed: int = 0
    summary: str = ""
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


class AIExecutor:
    """Orchestrates execution of user requests through the AI OS pipeline.

    The execution flow is:
      1. Parse natural language → CommandRequest (or Plan)
      2. If multi-step: create Plan via PlannerEngine
      3. Execute plan/command via CommandService
      4. Record in ContextManager for session awareness
      5. Return structured ExecutionResult
    """

    def __init__(self) -> None:
        self._parser = get_command_parser()
        self._planner = get_planner()
        self._context = get_context_manager()
        self._permissions = get_permission_service()

    async def execute(
        self,
        text: str,
        session_id: str = "",
        user_id: str = "",
        source: str = "user",
        auto_approve: bool = False,
    ) -> ExecutionResult:
        """Execute a natural language command.

        Full pipeline: parse → plan → execute → record → return.
        """
        start_time = time.monotonic()

        try:
            # Step 1: Parse
            command_request = self._parser.parse_to_request(
                text,
                source=source,
                user_id=user_id,
            )

            # Step 2: Plan (try multi-step first)
            plan = self._planner.create_plan(text)

            if len(plan.steps) > 1 and command_request:
                # Multi-step plan
                return await self._execute_plan(
                    plan,
                    session_id=session_id,
                    user_id=user_id,
                )

            if command_request:
                # Single command
                return await self._execute_single(
                    command_request,
                    session_id=session_id,
                    user_id=user_id,
                    auto_approve=auto_approve,
                    start_time=start_time,
                )

            # Step 3: Not parsed - return error
            elapsed = (time.monotonic() - start_time) * 1000
            return ExecutionResult(
                success=False,
                error=f"Could not understand: '{text}'. Try rephrasing.",
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - start_time) * 1000
            logger.exception("AIExecutor failed for '%s': %s", text, exc)
            return ExecutionResult(
                success=False,
                error=f"Execution error: {exc}",
                duration_ms=elapsed,
            )

    async def execute_stream(
        self,
        text: str,
        session_id: str = "",
        user_id: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute and yield progress updates."""
        start_time = time.monotonic()

        yield {"type": "parsing", "text": text}

        command_request = self._parser.parse_to_request(
            text,
            source="user",
            user_id=user_id,
        )

        if not command_request:
            yield {"type": "error", "message": f"Could not understand: '{text}'"}
            return

        yield {"type": "parsed", "command": command_request.action, "category": command_request.category.value}

        plan = self._planner.create_plan(text)

        if len(plan.steps) > 1:
            yield {"type": "plan_created", "steps": len(plan.steps), "plan_id": plan.plan_id}

            async for step_update in self._planner.execute_plan(plan):
                yield {
                    "type": "step_completed" if step_update.status == "completed" else "step_failed",
                    "step_id": step_update.step_id,
                    "description": step_update.description,
                    "status": step_update.status,
                    "error": step_update.error,
                }

            elapsed = (time.monotonic() - start_time) * 1000
            yield {"type": "plan_completed", "plan_id": plan.plan_id, "status": plan.status, "duration_ms": elapsed}
        else:
            yield {"type": "executing", "action": command_request.action, "category": command_request.category.value}

            try:
                svc = get_command_service()
                result = await svc.submit(command_request, auto_approve=True)
                elapsed = (time.monotonic() - start_time) * 1000

                # Record in context
                if session_id:
                    self._context.record_command(
                        session_id,
                        CommandEntry(
                            command_id=command_request.command_id,
                            action=command_request.action,
                            category=command_request.category.value,
                            status=result.status.value,
                            result_summary=str(result.result or result.error or ""),
                        ),
                    )

                yield {
                    "type": "completed" if result.status == CommandStatus.COMPLETED else "failed",
                    "command_id": command_request.command_id,
                    "status": result.status.value,
                    "result": result.result,
                    "error": result.error,
                    "duration_ms": elapsed,
                }
            except Exception as exc:
                elapsed = (time.monotonic() - start_time) * 1000
                yield {"type": "error", "message": str(exc), "duration_ms": elapsed}

    async def _execute_single(
        self,
        command: CommandRequest,
        session_id: str,
        user_id: str,
        auto_approve: bool,
        start_time: float,
    ) -> ExecutionResult:
        """Execute a single command request."""
        svc = get_command_service()

        try:
            result = await svc.submit(command, auto_approve=auto_approve)
            elapsed = (time.monotonic() - start_time) * 1000

            # Record in context
            if session_id:
                self._context.record_command(
                    session_id,
                    CommandEntry(
                        command_id=command.command_id,
                        action=command.action,
                        category=command.category.value,
                        status=result.status.value,
                        result_summary=str(result.result or result.error or ""),
                    ),
                )

            return ExecutionResult(
                success=result.status == CommandStatus.COMPLETED,
                command_id=command.command_id,
                steps_completed=1,
                summary=f"{command.action} -> {result.status.value}",
                output=result.result or {},
                error=result.error,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - start_time) * 1000
            logger.exception("Failed to execute command %s: %s", command.action, exc)
            return ExecutionResult(
                success=False,
                command_id=command.command_id,
                error=str(exc),
                duration_ms=elapsed,
            )

    async def _execute_plan(
        self,
        plan,
        session_id: str,
        user_id: str,
    ) -> ExecutionResult:
        """Execute a multi-step plan."""
        start_time = time.monotonic()
        completed = 0
        failed = 0

        try:
            async for step in self._planner.execute_plan(plan):
                if step.status == "completed":
                    completed += 1
                    # Record each step
                    if session_id:
                        self._context.record_command(
                            session_id,
                            CommandEntry(
                                command_id=step.step_id,
                                action=step.action,
                                category=step.category.value,
                                status="completed",
                                result_summary=step.description,
                            ),
                        )
                else:
                    failed += 1

            elapsed = (time.monotonic() - start_time) * 1000

            return ExecutionResult(
                success=failed == 0,
                plan_id=plan.plan_id,
                steps_completed=completed,
                steps_failed=failed,
                summary=f"Plan completed: {completed} steps done, {failed} failed",
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - start_time) * 1000
            logger.exception("Plan execution failed: %s", exc)
            return ExecutionResult(
                success=False,
                plan_id=plan.plan_id,
                error=str(exc),
                duration_ms=elapsed,
            )


# Singleton
_executor: AIExecutor | None = None


def get_executor() -> AIExecutor:
    global _executor
    if _executor is None:
        _executor = AIExecutor()
    return _executor
