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
            return await self._cancel(payload)
        if action == "list":
            return await self._list_scheduled(payload)
        if action == "run_workflow":
            return await self._run_workflow(payload)
        return {"status": "ok", "agent": "scheduler"}

    async def _schedule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a task on the shared task queue.

        Real behavior, honest failures: invalid schedule input raises
        ``ValueError`` out of here (execute() marks the agent unhealthy and
        re-raises), never a fabricated ``{"scheduled": True, "task_id":
        "manual"}``. The task is queued on the process-wide queue whose
        runner executes it when due.
        """
        from dash_backend.intelligence.task_queue import (
            TaskPriority,
            get_shared_task_queue,
        )

        queue = get_shared_task_queue()
        await queue.ensure_started()

        priority = TaskPriority.NORMAL
        wanted = str(payload.get("priority") or "").upper()
        if wanted in TaskPriority.__members__:
            priority = TaskPriority[wanted]

        task_spec = payload.get("task") if isinstance(payload.get("task"), dict) else {}
        task_id = await queue.enqueue(
            task_spec or {},
            priority=priority,
            scheduled_at=payload.get("at"),
        )

        result: Dict[str, Any] = {"scheduled": True, "task_id": task_id}
        name = str(task_spec.get("name") or task_spec.get("description") or "unnamed task")
        if task_spec.get("handler") is None and name not in queue.task_handlers:
            # Queued is true, but executing it would fail — say so up front
            # instead of letting the task fail at fire time.
            result["warning"] = (
                "task has no handler and no registered handler for its name; "
                "it will fail at execution time"
            )
        return result

    async def _cancel(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a queued/running task on the shared queue."""
        from dash_backend.intelligence.task_queue import get_shared_task_queue

        task_id = str(payload.get("task_id") or "")
        if not task_id:
            raise ValueError("cancel requires a task_id")
        cancelled = get_shared_task_queue().cancel_task(task_id)
        return {
            "cancelled": cancelled,
            "task_id": task_id,
            **({} if cancelled else {"error": "task not found"}),
        }

    async def _list_scheduled(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """List the tasks actually known to the shared queue."""
        from dash_backend.intelligence.task_queue import get_shared_task_queue

        queue = get_shared_task_queue()
        items = [
            {
                "task_id": t.id,
                "name": t.name,
                "status": t.status.value,
                "priority": t.priority.name,
                "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
                "retry_count": t.retry_count,
            }
            for t in queue.list_tasks()
        ]
        return {"scheduled": items, "count": len(items), "agent": "scheduler"}

    async def _run_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow on the shared engine. Fails honestly."""
        from dash_backend.intelligence.workflow_engine import get_shared_workflow_engine

        workflow_id = str(payload.get("workflow_id") or "")
        if not workflow_id:
            raise ValueError("run_workflow requires a workflow_id")
        result = await get_shared_workflow_engine().execute_workflow(workflow_id)
        return {"workflow_id": workflow_id, "result": result}


_scheduler_agent: SchedulerAgent | None = None


def get_scheduler_agent() -> SchedulerAgent:
    """Return the Scheduler Agent singleton."""
    global _scheduler_agent
    if _scheduler_agent is None:
        _scheduler_agent = SchedulerAgent()
    return _scheduler_agent
