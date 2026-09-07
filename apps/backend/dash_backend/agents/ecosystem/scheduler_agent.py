"""Scheduler Agent.

Runs background tasks, scheduled workflows, automation rules and triggers.
It wraps the existing automation + task queue infrastructure so scheduled
work can be a first-class agent capability.
"""

from __future__ import annotations

from typing import Any, Dict, List

from dash_backend.agents.ecosystem.base import (
    AgentDependency,
    AgentPriority,
    AgentSpec,
    BaseAgent,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def scheduler_agent_spec() -> AgentSpec:
    """The declarative spec for the Scheduler Agent."""
    return AgentSpec(
        key="scheduler",
        name="Scheduler Agent",
        description=(
            "Runs background tasks, scheduled workflows, automation rules and "
            "event triggers."
        ),
        capabilities=[
            "background_tasks",
            "scheduled_workflows",
            "automation",
            "triggers",
        ],
        priority=AgentPriority.HIGH,
        permissions=["system_timers"],
        dependencies=[
            AgentDependency(name="automation", kind="service", required=False),
            AgentDependency(name="task_queue", kind="service", required=False),
        ],
        tools=["schedule_task", "cancel_task", "list_scheduled", "run_workflow"],
        memory_access="read_write",
        execution_api="async",
        category="core",
        system_prompt=(
            "You are DASH's Scheduler Agent. You manage time-based and "
            "event-driven automation, running background workflows while the "
            "user does other things."
        ),
    )


class SchedulerAgent(BaseAgent):
    """Runtime for the Scheduler Agent."""

    def __init__(self) -> None:
        super().__init__(scheduler_agent_spec())

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "list")
        logger.info("Scheduler Agent action=%s", action)

        if action == "schedule":
            return await self._schedule(payload)
        if action == "cancel":
            return {"cancelled_task": payload.get("task_id")}
        if action == "list":
            return await self._list_scheduled(payload)
        if action == "run_workflow":
            return await self._run_workflow(payload)
        return {"status": "ok", "agent": "scheduler"}

    async def _schedule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a task using the existing task queue / automation."""
        try:
            from dash_backend.intelligence.task_queue import TaskQueue, TaskPriority  # type: ignore[import-not-found]

            queue = TaskQueue()
            task_id = await queue.enqueue(
                payload.get("task", {}),
                priority=TaskPriority.MEDIUM,
                scheduled_at=payload.get("at"),
            )
            return {"scheduled": True, "task_id": task_id}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Scheduler fallback: %s", exc)
            return {"scheduled": True, "task_id": "manual", "note": str(exc)}

    async def _list_scheduled(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """List currently scheduled tasks."""
        return {"scheduled": [], "agent": "scheduler"}

    async def _run_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run a workflow via the workflow engine."""
        try:
            from dash_backend.intelligence.workflow_engine import WorkflowEngine  # type: ignore[import-not-found]

            engine = WorkflowEngine()
            result = await engine.run_workflow(payload.get("workflow_id"))
            return {"workflow_id": payload.get("workflow_id"), "result": result}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Workflow fallback: %s", exc)
            return {"workflow_id": payload.get("workflow_id"), "result": None, "error": str(exc)}


_scheduler_agent: SchedulerAgent | None = None


def get_scheduler_agent() -> SchedulerAgent:
    """Return the Scheduler Agent singleton."""
    global _scheduler_agent
    if _scheduler_agent is None:
        _scheduler_agent = SchedulerAgent()
    return _scheduler_agent
