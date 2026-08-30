"""PlannerEngine - multi-step reasoning and plan execution.

Supports:
  - Breaking complex commands into step-by-step plans
  - Sequential and parallel step execution
  - Retry logic for failed steps
  - Rollback on failure
  - Plan monitoring and cancellation
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

from dash_backend.logging_config import get_logger
from dash_backend.services.command.models import (
    CommandCategory,
    CommandRequest,
    CommandStatus,
)
from dash_backend.services.command.service import CommandService, get_command_service

logger = get_logger(__name__)


class PlanStepType(Enum):
    """Type of step in a plan."""
    COMMAND = "command"
    WAIT = "wait"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"


@dataclass
class PlanStep:
    """A single step within a plan."""
    step_id: str = ""
    step_type: PlanStepType = PlanStepType.COMMAND
    description: str = ""
    category: CommandCategory = CommandCategory.SYSTEM
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = True
    timeout_seconds: int = 60
    retry_count: int = 0
    max_retries: int = 2
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class Plan:
    """A complete execution plan."""
    plan_id: str = ""
    user_query: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "pending"
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    rollback_enabled: bool = True


class PlannerEngine:
    """Breaks down complex commands into executable plans.

    Uses heuristic rules for known multi-step operations.
    For unknown operations, falls back to single-step execution.
    """

    # Known multi-step command templates
    _TEMPLATES: dict[str, list[dict[str, Any]]] = {
        "update project": [
            {"description": "Open terminal", "category": CommandCategory.APPS, "action": "launch", "params": {"path": "cmd.exe", "name": "cmd"}},
            {"description": "Pull latest changes", "category": CommandCategory.TERMINAL, "action": "execute", "params": {"command": "cd . && git pull"}},
            {"description": "Install dependencies", "category": CommandCategory.TERMINAL, "action": "execute", "params": {"command": "npm install", "timeout": 120}},
            {"description": "Build project", "category": CommandCategory.TERMINAL, "action": "execute", "params": {"command": "npm run build", "timeout": 120}},
        ],
        "build project": [
            {"description": "Run build", "category": CommandCategory.TERMINAL, "action": "execute", "params": {"command": "npm run build", "timeout": 120}},
        ],
        "deploy": [
            {"description": "Run tests", "category": CommandCategory.TERMINAL, "action": "execute", "params": {"command": "npm test", "timeout": 60}},
            {"description": "Build for production", "category": CommandCategory.TERMINAL, "action": "execute", "params": {"command": "npm run build", "timeout": 120}},
        ],
        "start development": [
            {"description": "Start backend", "category": CommandCategory.TERMINAL, "action": "execute", "params": {"command": "cd apps/backend && python -m dash_backend"} },
            {"description": "Start frontend", "category": CommandCategory.TERMINAL, "action": "execute", "params": {"command": "cd apps/desktop && npm run dev"}},
        ],
    }

    def __init__(self) -> None:
        self._active_plans: dict[str, Plan] = {}

    def create_plan(self, user_query: str) -> Plan:
        """Create a plan from a user query.

        Returns a Plan with steps either from templates or
        as a single command step via CommandParser.
        """
        plan_id = str(uuid.uuid4())
        plan = Plan(
            plan_id=plan_id,
            user_query=user_query,
            created_at=time.time(),
        )

        query_lower = user_query.lower().strip().rstrip(".!?")

        # Check templates
        for template_key, steps_data in self._TEMPLATES.items():
            if template_key in query_lower:
                plan.steps = [
                    PlanStep(
                        step_id=str(uuid.uuid4()),
                        step_type=PlanStepType.COMMAND,
                        **s,
                    )
                    for s in steps_data
                ]
                break

        # If no template matched, create a single-step plan via parser
        if not plan.steps:
            from .command_parser import get_command_parser
            parsed = get_command_parser().parse(query_lower)
            if parsed:
                plan.steps.append(
                    PlanStep(
                        step_id=str(uuid.uuid4()),
                        step_type=PlanStepType.COMMAND,
                        description=parsed.description,
                        category=parsed.category,
                        action=parsed.action,
                        params=parsed.params,
                        requires_approval=parsed.confidence < 0.9,
                    )
                )

        # Set dependencies: each step depends on previous (sequential)
        for i, step in enumerate(plan.steps):
            if i > 0:
                step.depends_on = [plan.steps[i - 1].step_id]

        self._active_plans[plan_id] = plan
        return plan

    async def execute_plan(
        self,
        plan: Plan,
        command_service: CommandService | None = None,
    ) -> AsyncIterator[PlanStep]:
        """Execute a plan step by step.

        Yields each step as it completes.
        """
        svc = command_service or get_command_service()
        plan.status = "running"
        plan.started_at = time.time()

        completed: set[str] = set()
        failed: set[str] = set()

        try:
            while True:
                # Find steps ready to execute
                ready = [
                    s for s in plan.steps
                    if s.status == "pending" and all(dep in completed for dep in s.depends_on)
                ]

                if not ready:
                    # Check if all steps done
                    if len(completed) + len(failed) == len(plan.steps):
                        break
                    if failed:
                        break
                    await asyncio.sleep(0.1)
                    continue

                for step in ready:
                    yield await self._execute_step(step, svc)
                    if step.status == "completed":
                        completed.add(step.step_id)
                    else:
                        failed.add(step.step_id)
                        if plan.rollback_enabled:
                            await self._rollback(plan, completed)
                            break

            plan.status = "completed" if not failed else "failed"
            plan.completed_at = time.time()

        except Exception as exc:
            plan.status = "failed"
            plan.completed_at = time.time()
            logger.exception("Plan execution failed: %s", exc)

        self._active_plans[plan.plan_id] = plan

    async def _execute_step(
        self,
        step: PlanStep,
        command_service: CommandService,
    ) -> PlanStep:
        """Execute a single plan step."""
        step.started_at = time.time()
        step.status = "running"

        for attempt in range(step.max_retries + 1):
            try:
                request = CommandRequest(
                    command_id=str(uuid.uuid4()),
                    category=step.category,
                    action=step.action,
                    params=step.params,
                    source="ai_planner",
                    requires_approval=step.requires_approval and attempt == 0,
                )

                result = await asyncio.wait_for(
                    command_service.submit(request, auto_approve=not step.requires_approval),
                    timeout=step.timeout_seconds,
                )

                if result.status == CommandStatus.COMPLETED:
                    step.status = "completed"
                    step.result = result.result
                    step.error = None
                    step.completed_at = time.time()
                    logger.info("Step %s completed: %s", step.step_id, step.description)
                    return step

                step.error = result.error or f"Status: {result.status.value}"

            except asyncio.TimeoutError:
                step.error = f"Timed out after {step.timeout_seconds}s"
            except Exception as exc:
                step.error = str(exc)

            step.retry_count = attempt + 1
            if attempt < step.max_retries:
                await asyncio.sleep(1.0 * (attempt + 1))
                logger.warning("Retrying step %s (attempt %d/%d): %s", step.step_id, attempt + 1, step.max_retries, step.error)

        step.status = "failed"
        step.completed_at = time.time()
        logger.error("Step %s failed: %s", step.step_id, step.error)
        return step

    async def _rollback(self, plan: Plan, completed: set[str]) -> None:
        """Rollback completed steps in reverse order."""
        if not plan.rollback_enabled:
            return

        logger.info("Rolling back plan %s", plan.plan_id)
        reversed_steps = [s for s in plan.steps if s.step_id in completed]
        for step in reversed(reversed_steps):
            try:
                rollback_action = self._get_rollback_action(step.action)
                if rollback_action:
                    svc = get_command_service()
                    request = CommandRequest(
                        command_id=str(uuid.uuid4()),
                        category=step.category,
                        action=rollback_action,
                        params=step.params,
                        source="ai_planner_rollback",
                        requires_approval=False,
                    )
                    await svc.submit(request, auto_approve=True)
                    logger.info("Rollback step %s: %s -> %s", step.step_id, step.action, rollback_action)
            except Exception as exc:
                logger.exception("Rollback failed for step %s: %s", step.step_id, exc)

    @staticmethod
    def _get_rollback_action(action: str) -> str | None:
        """Get the rollback action for a given action."""
        rollbacks = {
            "launch": "close",
            "close": "launch",
            "copy": "delete",
            "move": "move",
            "rename": "rename",
            "delete": "copy",
            "create_folder": "delete",
            "write": "delete",
        }
        return rollbacks.get(action)

    def get_plan(self, plan_id: str) -> Plan | None:
        """Get a plan by ID."""
        return self._active_plans.get(plan_id)

    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a running plan."""
        plan = self._active_plans.get(plan_id)
        if plan and plan.status == "running":
            plan.status = "cancelled"
            plan.completed_at = time.time()
            return True
        return False

    def list_plans(self, limit: int = 10) -> list[Plan]:
        """List recent plans."""
        plans = sorted(
            self._active_plans.values(),
            key=lambda p: p.created_at,
            reverse=True,
        )
        return plans[:limit]


# Singleton
_planner: PlannerEngine | None = None


def get_planner() -> PlannerEngine:
    global _planner
    if _planner is None:
        _planner = PlannerEngine()
    return _planner
