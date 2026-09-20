"""Task graph — dependency-aware step scheduling for agent tasks.

Deterministic layer: computes which steps are ready (dependencies completed),
detects dead ends (failed/cascaded dependencies), and drives parallel
execution of independent ready steps via asyncio. The LLM never decides
scheduling order — it only fills in tool/args for steps that lack them.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from dash_backend.logging_config import get_logger

from dash_backend.autonomous.task_state import AgentTask, StepStatus, TaskStep

logger = get_logger(__name__)


class CycleError(Exception):
    """The step dependency graph contains a cycle."""


def validate_graph(task: AgentTask) -> None:
    """Raise CycleError if the task's depends_on edges contain a cycle."""
    ids = {s.id for s in task.steps}
    color: dict[str, int] = {sid: 0 for sid in ids}  # 0 white 1 grey 2 black

    def visit(sid: str) -> None:
        color[sid] = 1
        for dep in next(s for s in task.steps if s.id == sid).depends_on:
            if dep not in ids:
                continue  # unknown dep treated as satisfied (defensive)
            if color[dep] == 1:
                raise CycleError(f"dependency cycle involving step '{dep}'")
            if color[dep] == 0:
                visit(dep)
        color[sid] = 0 if False else 2  # mark black

    for s in task.steps:
        if color[s.id] == 0:
            visit(s.id)


def ready_steps(task: AgentTask) -> list[TaskStep]:
    """Steps whose dependencies are all COMPLETED and which can still run."""
    by_id = {s.id: s for s in task.steps}
    ready: list[TaskStep] = []
    for s in task.steps:
        if s.status != StepStatus.PENDING:
            continue
        deps = [by_id[d] for d in s.depends_on if d in by_id]
        if all(d.status == StepStatus.COMPLETED for d in deps):
            ready.append(s)
    return ready


def cascade_blocked(task: AgentTask) -> None:
    """Mark pending steps whose dependencies failed/skipped as SKIPPED.

    Honest cascade: a step that can never run because its prerequisite
    failed is recorded as skipped — never silently left 'pending'.
    """
    by_id = {s.id: s for s in task.steps}
    changed = True
    while changed:  # cascade through chained dependencies
        changed = False
        for s in task.steps:
            if s.status != StepStatus.PENDING:
                continue
            deps = [by_id[d] for d in s.depends_on if d in by_id]
            if any(d.status in (StepStatus.FAILED, StepStatus.SKIPPED) for d in deps):
                s.status = StepStatus.SKIPPED
                s.error = "dependency failed or was skipped"
                changed = True


def is_terminal(task: AgentTask) -> bool:
    """True when no step can ever run again (all done/failed/skipped/blocked-by-confirm)."""
    if task.status in ("completed", "failed", "cancelled"):
        return True
    if task.status == "waiting_confirmation":
        return False
    if ready_steps(task):
        return False
    cascade_blocked(task)
    return not ready_steps(task)


async def run_ready_steps(
    task: AgentTask,
    run_step: Callable[[AgentTask, TaskStep], Awaitable[bool]],
    *,
    max_parallel: int = 3,
) -> bool:
    """Execute all currently-ready steps, independent ones in parallel.

    ``run_step`` must be the orchestrator's coroutine that executes ONE step
    (tool selection, confirmation gating, verification, retries) and returns
    True on success. After each wave, newly-unblocked steps run in the next
    wave — a deterministic topological execution with bounded parallelism.

    Returns True if every executed step succeeded.
    """
    all_ok = True
    while True:
        cascade_blocked(task)
        wave = ready_steps(task)
        if not wave:
            break
        wave = wave[:max_parallel]
        results = await asyncio.gather(
            *(run_step(task, s) for s in wave), return_exceptions=True
        )
        for step, res in zip(wave, results):
            if isinstance(res, BaseException):
                logger.exception("Step '%s' crashed", step.id)
                step.status = StepStatus.FAILED
                step.error = f"crashed: {res}"
                step.completed_at = time.time()
                all_ok = False
            elif res is not True:
                all_ok = False
    return all_ok
