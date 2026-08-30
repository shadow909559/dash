"""Multitasking Engine — runs multiple agents/workflows in parallel.

Example:
User: "Continue indexing while researching AI agents and fixing the backend."

DASH automatically:
- Memory Agent (indexing)
- Research Agent (AI agents)
- Coding Agent (fix backend)

run simultaneously, merge results, and report naturally.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ParallelTask:
    """A single task to run in parallel."""

    id: str
    name: str
    agent_type: str
    coro: Optional[Awaitable[Any]] = None
    status: str = "pending"  # pending | running | completed | failed
    result: Any = None
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "agent_type": self.agent_type,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ParallelExecutionResult:
    """The merged result of parallel task execution."""

    tasks: List[ParallelTask] = field(default_factory=list)
    total_duration_s: float = 0.0
    all_succeeded: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self.tasks],
            "total_duration_s": round(self.total_duration_s, 2),
            "all_succeeded": self.all_succeeded,
        }

    def merged_results(self) -> Dict[str, Any]:
        """Merge task results into a single dict keyed by task name."""
        merged: Dict[str, Any] = {}
        for t in self.tasks:
            merged[t.name] = t.result
        return merged


class MultitaskingEngine:
    """Runs multiple tasks concurrently and merges results."""

    def __init__(self) -> None:
        self._history: List[ParallelExecutionResult] = []

    async def run_parallel(
        self,
        tasks: List[Dict[str, Any]],
        *,
        max_concurrency: int = 4,
    ) -> ParallelExecutionResult:
        """Run multiple tasks concurrently.

        Each task dict must have:
        - name: str
        - agent_type: str
        - coro: awaitable (or ``fn`` callable returning awaitable)

        Returns a merged result with per-task status.
        """
        start = time.perf_counter()

        # Build ParallelTask objects.
        parallel_tasks: List[ParallelTask] = []
        for spec in tasks:
            name = str(spec.get("name") or spec.get("agent_type") or "task")
            agent_type = str(spec.get("agent_type") or "general")
            coro = spec.get("coro")
            if coro is None and callable(spec.get("fn")):
                coro = spec["fn"]()
            parallel_tasks.append(
                ParallelTask(
                    id=str(uuid.uuid4()),
                    name=name,
                    agent_type=agent_type,
                    coro=coro,
                )
            )

        # Run with bounded concurrency.
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_one(task: ParallelTask) -> None:
            if task.coro is None:
                task.status = "failed"
                task.error = "No coroutine provided"
                return
            task.status = "running"
            task.started_at = time.time()
            try:
                async with semaphore:
                    task.result = await task.coro
                task.status = "completed"
            except Exception as exc:
                task.status = "failed"
                task.error = str(exc)
                logger.warning("Parallel task '%s' failed: %s", task.name, exc)
            finally:
                task.completed_at = time.time()

        await asyncio.gather(*(run_one(t) for t in parallel_tasks))

        result = ParallelExecutionResult(
            tasks=parallel_tasks,
            total_duration_s=time.perf_counter() - start,
            all_succeeded=all(t.status == "completed" for t in parallel_tasks),
        )
        self._history.append(result)
        self._history = self._history[-20:]
        return result

    def history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent parallel execution results."""
        return [r.to_dict() for r in self._history[-limit:]]

    @staticmethod
    def decompose_request(request: str) -> List[Dict[str, str]]:
        """Heuristically decompose a multi-part request into parallel tasks.

        Splits on conjunctions like "while", "and", "also", "plus".
        Returns a list of {name, agent_type} dicts.
        """
        lower = (request or "").lower()
        parts: List[str] = []

        # Split on common multitasking conjunctions.
        for sep in [" while ", " and also ", " plus ", " meanwhile "]:
            if sep in lower:
                parts = [p.strip() for p in request.split(sep) if p.strip()]
                break

        if not parts:
            parts = [request.strip()] if request.strip() else []

        tasks: List[Dict[str, str]] = []
        for i, part in enumerate(parts):
            agent_type = "general"
            part_lower = part.lower()
            if any(k in part_lower for k in ["research", "search", "find", "look up"]):
                agent_type = "research"
            elif any(k in part_lower for k in ["code", "fix", "bug", "refactor", "implement"]):
                agent_type = "coding"
            elif any(k in part_lower for k in ["index", "memory", "remember", "store"]):
                agent_type = "memory"
            elif any(k in part_lower for k in ["browser", "web", "website"]):
                agent_type = "browser"
            elif any(k in part_lower for k in ["desktop", "window", "file", "folder"]):
                agent_type = "desktop"
            tasks.append({"name": part[:80], "agent_type": agent_type})

        return tasks


# Global singleton
_multitasking_engine: Optional[MultitaskingEngine] = None


def get_multitasking_engine() -> MultitaskingEngine:
    """Return the global MultitaskingEngine singleton."""
    global _multitasking_engine
    if _multitasking_engine is None:
        _multitasking_engine = MultitaskingEngine()
    return _multitasking_engine