"""Orchestrator Extension.

Additively extends the Master Orchestrator with the ecosystem's new agents and
three cross-cutting capabilities the user asked for:

1. **Failure Recovery** — retry, alternative strategy, alternative tool, then
   fallback. Only ask the user when absolutely necessary.
2. **Self-Improvement** — after every task, evaluate performance and store
   successful/failed strategies to improve future execution.
3. **Task Memory** — every task stores goal, steps, result, errors, duration,
   tools used, and agent used.

This module does NOT modify the working ``master_orchestrator.py``. Instead it
provides a subclass hook and helper functions that the orchestrator (or a
derived orchestrator) can call. It is purely additive.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# Task Memory
# ──────────────────────────────────────────────


@dataclass
class TaskMemoryRecord:
    """Structured record of a single task execution."""

    task_id: str = ""
    goal: str = ""
    steps: List[str] = field(default_factory=list)
    result: Any = None
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0
    tools_used: List[str] = field(default_factory=list)
    agent_used: str = ""
    status: str = "completed"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "steps": self.steps,
            "result": self.result,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "tools_used": self.tools_used,
            "agent_used": self.agent_used,
            "status": self.status,
            "timestamp": self.timestamp,
        }


class TaskMemoryStore:
    """In-process store of task memory records.

    (A persistent backend can be swapped in without changing the interface.)
    """

    def __init__(self) -> None:
        self._records: Dict[str, TaskMemoryRecord] = {}

    def save(self, record: TaskMemoryRecord) -> None:
        self._records[record.task_id] = record
        logger.debug("Task memory saved: %s (%s)", record.task_id, record.status)

    def get(self, task_id: str) -> Optional[TaskMemoryRecord]:
        return self._records.get(task_id)

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        records = list(self._records.values())
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return [r.to_dict() for r in records[:limit]]

    @property
    def count(self) -> int:
        return len(self._records)


# ──────────────────────────────────────────────
# Self-Improvement
# ──────────────────────────────────────────────


@dataclass
class LearnedStrategy:
    """A strategy learned from a completed (successful or failed) task."""

    key: str
    workflow: str
    roles_used: List[str]
    success: bool
    notes: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "workflow": self.workflow,
            "roles_used": self.roles_used,
            "success": self.success,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }


class ImprovementStore:
    """Stores successful/failed strategies for future reference."""

    def __init__(self) -> None:
        self._strategies: Dict[str, LearnedStrategy] = {}

    def record(self, strategy: LearnedStrategy) -> None:
        self._strategies[strategy.key] = strategy
        logger.info(
            "Learned strategy (%s): %s", "success" if strategy.success else "fail", strategy.key
        )

    def successful_strategy(self, workflow: str, roles: List[str]) -> Optional[LearnedStrategy]:
        """Return a previously successful strategy for a similar workflow."""
        for strat in self._strategies.values():
            if strat.success and set(strat.roles_used) == set(roles):
                return strat
        return None

    def list(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._strategies.values()]


# ──────────────────────────────────────────────
# Failure Recovery
# ──────────────────────────────────────────────


class FailureRecovery:
    """Implements tiered failure recovery for a task execution."""

    def __init__(
        self,
        max_retries: int = 2,
        backoff_base: float = 0.5,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    async def execute_with_recovery(
        self,
        func: Callable[[], Any],
        *,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
        fallback: Optional[Any] = None,
    ) -> Any:
        """Run ``func`` with retry + backoff; fall back if still failing.

        Tiers:
            1. Retry the same strategy (with backoff).
            2. (Alternative strategy/tool is provided by the caller via
               ``func`` — the caller may swap strategy between attempts.)
            3. Return the provided fallback instead of raising.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if on_retry is not None:
                    on_retry(attempt, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_base * (2 ** (attempt - 1)))

        if fallback is not None:
            return fallback
        raise last_exc if last_exc else RuntimeError("Unknown failure")


# ──────────────────────────────────────────────
# Ecosystem orchestrator hook
# ──────────────────────────────────────────────


class EcosystemOrchestratorMixin:
    """Additive capabilities layered on top of the Master Orchestrator.

    This class is meant to be *mixed into* a derived orchestrator, or used as
    a standalone helper that the existing orchestrator delegates to. It does
    not override the working orchestrator's methods; it adds new ones.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.task_memory: TaskMemoryStore = TaskMemoryStore()
        self.improvement: ImprovementStore = ImprovementStore()
        self.recovery: FailureRecovery = FailureRecovery()

    # ── Ecosystem agent dispatch ────────────────

    async def dispatch_ecosystem_agent(
        self,
        agent_key: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Dispatch a task to an ecosystem agent by key."""
        try:
            from dash_backend.agents.ecosystem.registry import get_agent_registry

            registry = get_agent_registry()
            runtime = registry.get_runtime(agent_key)
            if runtime is None:
                return None
            return await runtime.execute(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ecosystem agent %s dispatch failed: %s", agent_key, exc)
            return {"error": str(exc)}

    def list_ecosystem_agents(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered ecosystem agent specs."""
        try:
            from dash_backend.agents.ecosystem.registry import get_agent_registry

            return get_agent_registry().list_specs(category)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to list ecosystem agents: %s", exc)
            return []

    # ── Task memory recording ───────────────────

    def record_task(
        self,
        *,
        goal: str,
        result: Any,
        agent_used: str,
        tools_used: List[str],
        steps: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
        duration_ms: int = 0,
        status: str = "completed",
    ) -> str:
        """Record a completed/failed task into task memory."""
        record = TaskMemoryRecord(
            task_id=str(uuid.uuid4()),
            goal=goal,
            steps=steps or [],
            result=result,
            errors=errors or [],
            duration_ms=duration_ms,
            tools_used=tools_used,
            agent_used=agent_used,
            status=status,
        )
        self.task_memory.save(record)
        return record.task_id

    # ── Self-improvement ────────────────────────

    def learn_from_task(
        self,
        *,
        workflow: str,
        roles_used: List[str],
        success: bool,
        notes: str = "",
    ) -> None:
        """Store a learned strategy from a completed task."""
        key = f"{workflow[:60]}|{'|'.join(sorted(roles_used))}"
        self.improvement.record(
            LearnedStrategy(
                key=key,
                workflow=workflow,
                roles_used=roles_used,
                success=success,
                notes=notes,
            )
        )

    def get_best_strategy(self, workflow: str, roles: List[str]) -> Optional[Dict[str, Any]]:
        """Retrieve the best previously learned successful strategy."""
        strat = self.improvement.successful_strategy(workflow, roles)
        return strat.to_dict() if strat else None


# Global singleton for the mixin's stores
_mixin_state: Optional[EcosystemOrchestratorMixin] = None


def get_ecosystem_state() -> EcosystemOrchestratorMixin:
    """Return a global state holder for the ecosystem extension."""
    global _mixin_state
    if _mixin_state is None:
        _mixin_state = EcosystemOrchestratorMixin()
    return _mixin_state
