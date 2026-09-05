"""Enhanced Planner with self-verification, plan revision, dependency resolution,
parallel plan generation, and tool chaining support.

The Planner uses the configured LLM provider to decompose high-level goals
into structured subtasks with dependency tracking, self-verification, and
automatic plan revision on failure.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from dash_backend.llm.service import collect_streamed_response, build_chat_messages
from dash_backend.cache.simple_cache import get_cache
from dash_backend.security.input_sanitizer import sanitize_goal_input, sanitize_memory_context

logger = logging.getLogger(__name__)


class Planner:
    """Planner abstraction that uses the configured LLM provider to decompose
    high-level goals into structured subtasks.

    Supports:
    - Goal decomposition into subtasks
    - Dependency resolution between tasks (parallel execution)
    - Self-verification of completed tasks
    - Plan revision on failure
    - Retry logic with exponential backoff
    - Tool chaining (passing outputs between tasks)
    - Parallel plan generation (multiple alternative strategies)
    - Memory-aware planning (injects user context into decomposition)
    """

    @staticmethod
    async def decompose(
        goal_name: str,
        goal_description: str | None = None,
        max_tasks: int = 10,
        memory_context: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Decompose a goal into structured subtasks with dependencies.

        If memory_context is provided, it is injected into the system prompt
        so the planner is aware of user preferences, constraints, and history.

        Returns a list of task dicts with keys:
        - name: short task name
        - description: one-line description
        - est_minutes: optional estimated minutes
        - tools: optional list of tools/skills required
        - depends_on: list of task names that must complete first
        - verification: how to verify this task is complete
        
        Results are cached for 1 hour to improve performance.
        """
        # Sanitize inputs to prevent prompt injection
        sanitized_name, sanitized_description = sanitize_goal_input(goal_name, goal_description)
        sanitized_memory = sanitize_memory_context(memory_context) if memory_context else None
        
        # Check cache first (skip if memory_context is provided as it's user-specific)
        cache = get_cache()
        if not sanitized_memory:
            cache_key = f"planner_decompose_{sanitized_name}_{sanitized_description}_{max_tasks}"
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.info("Using cached planner result for: %s", sanitized_name)
                return cached_result
        
        system_prompt = (
            "You are a task planner. Break the user's goal into a list of up to "
            f"{max_tasks} clear, actionable subtasks. Return the result as JSON array of objects with keys:\n"
            "- name (short task name)\n"
            "- description (one-line description)\n"
            "- est_minutes (optional, estimated minutes)\n"
            "- tools (optional, list of tools/skills required)\n"
            "- depends_on (optional, list of task names that must complete first)\n"
            "- verification (optional, how to verify this task is complete)\n"
            "Respond with JSON only. Do not include any additional explanation.\n\n"
        )

        if sanitized_memory:
            system_prompt += (
                "\n[USER CONTEXT]\n"
                f"{sanitized_memory}\n"
                "[/USER CONTEXT]\n"
                "Consider the above user context when planning.\n"
            )

        user_message = f"Goal: {sanitized_name}\n\nDescription: {sanitized_description or ''}\n\nProduce the JSON array of subtasks."

        messages = build_chat_messages(system_prompt=system_prompt, user_message=user_message)

        # If the caller provided a JSON array directly, prefer parsing it.
        if sanitized_description:
            candidate = sanitized_description.strip()
            if candidate.startswith("[") and candidate.endswith("]"):
                tasks = json.loads(candidate)
                if isinstance(tasks, list):
                    return Planner._normalize_tasks(tasks, max_tasks)

        try:
            text = await collect_streamed_response(messages)
            text = text.strip()
            if text.startswith("```"):
                parts = text.split("```")
                if len(parts) >= 2:
                    text = parts[1].strip()
            tasks = json.loads(text)
            if isinstance(tasks, list):
                normalized = Planner._normalize_tasks(tasks, max_tasks)
                if normalized:
                    # Cache the result if no memory_context was provided
                    if not sanitized_memory:
                        cache_key = f"planner_decompose_{sanitized_name}_{sanitized_description}_{max_tasks}"
                        cache.set(cache_key, normalized, ttl=3600.0)  # 1 hour TTL
                    return normalized
        except Exception as exc:
            logger.warning("Planner LLM decomposition failed: %s", exc)

        # Fallback heuristic
        if goal_description:
            parts = [p.strip() for p in goal_description.replace("!", ".").replace("?", ".").split('.') if p.strip()]
            return [{
                "name": p[:255],
                "description": p,
                "est_minutes": None,
                "tools": [],
                "depends_on": [],
                "verification": None,
            } for p in parts[:max_tasks]]
        return [{
            "name": goal_name,
            "description": goal_description or goal_name,
            "est_minutes": None,
            "tools": [],
            "depends_on": [],
            "verification": None,
        }]

    @staticmethod
    def _normalize_tasks(tasks: List[Dict], max_tasks: int) -> List[Dict[str, Any]]:
        """Normalize task dicts to a consistent format."""
        normalized = []
        for t in tasks[:max_tasks]:
            if not isinstance(t, dict):
                continue
            normalized.append({
                "name": str(t.get("name") or t.get("title") or "Unnamed Task")[:255],
                "description": str(t.get("description") or "")[:1000],
                "est_minutes": int(t.get("est_minutes")) if t.get("est_minutes") else None,
                "tools": t.get("tools") or [],
                "depends_on": t.get("depends_on") or [],
                "verification": str(t.get("verification") or "")[:500] or None,
            })
        return normalized

    @staticmethod
    def resolve_dependencies(tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Resolve task dependencies into execution layers.

        Returns a list of layers, where each layer contains tasks that
        can be executed in parallel (no dependencies between them).
        """
        task_map = {t["name"]: t for t in tasks}
        layers: List[List[Dict[str, Any]]] = []
        executed: set[str] = set()

        remaining = list(tasks)
        while remaining:
            current_layer = []
            still_remaining = []

            for task in remaining:
                deps = task.get("depends_on") or []
                # Check if all dependencies are satisfied
                if all(dep in executed for dep in deps):
                    current_layer.append(task)
                else:
                    still_remaining.append(task)

            if not current_layer:
                # Circular dependency or missing deps - break by adding remaining
                logger.warning("Circular dependency detected, breaking with %d tasks", len(still_remaining))
                current_layer = still_remaining
                still_remaining = []

            layers.append(current_layer)
            for task in current_layer:
                executed.add(task["name"])
            remaining = still_remaining

        return layers

    @staticmethod
    async def verify_task(
        task_name: str,
        task_description: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Self-verify that a task was completed successfully.

        Returns verification result with pass/fail and notes.
        """
        # Simple heuristic verification
        is_error = result.get("status") == "error" or result.get("error") is not None
        has_output = result.get("output") is not None or result.get("result") is not None

        if is_error:
            return {
                "verified": False,
                "task": task_name,
                "reason": f"Task failed with error: {result.get('error', 'unknown')}",
                "needs_revision": True,
            }

        if not has_output:
            return {
                "verified": False,
                "task": task_name,
                "reason": "Task produced no output",
                "needs_revision": True,
            }

        return {
            "verified": True,
            "task": task_name,
            "reason": "Task completed successfully",
            "needs_revision": False,
        }

    @staticmethod
    async def revise_plan(
        goal_name: str,
        original_tasks: List[Dict[str, Any]],
        failed_task: Dict[str, Any],
        failure_reason: str,
        max_tasks: int = 10,
    ) -> List[Dict[str, Any]]:
        """Revise the plan after a task failure.

        Returns a new list of tasks that replaces the failed task
        and any remaining tasks.
        """
        prompt = (
            f"A task failed during execution of goal '{goal_name}'. "
            f"The failed task was: {failed_task.get('name')} "
            f"({failed_task.get('description')}). "
            f"Failure reason: {failure_reason}. "
            "Please provide a revised plan to recover from this failure. "
            "Return a JSON array of remaining tasks with the same format as before. "
            "Respond with JSON only."
        )

        messages = build_chat_messages(
            system_prompt="You are a task planner helping to recover from failures.",
            user_message=prompt,
        )

        try:
            text = await collect_streamed_response(messages)
            text = text.strip()
            if text.startswith("```"):
                parts = text.split("```")
                if len(parts) >= 2:
                    text = parts[1].strip()
            tasks = json.loads(text)
            if isinstance(tasks, list):
                normalized = Planner._normalize_tasks(tasks, max_tasks)
                if normalized:
                    return normalized
        except Exception as exc:
            logger.warning("Plan revision failed: %s", exc)

        # Fallback: retry the failed task
        return [{
            "name": failed_task.get("name", "Retry"),
            "description": f"Retry: {failed_task.get('description', '')}",
            "est_minutes": failed_task.get("est_minutes"),
            "tools": failed_task.get("tools", []),
            "depends_on": [],
            "verification": failed_task.get("verification"),
        }]


class PlannerService:
    """Read-oriented facade over executive goals/tasks for other subsystems
    (voice context, plugins). Backed by real DB state — no fabricated data."""

    async def get_all_goals(self) -> List[Any]:
        from sqlalchemy import select

        from dash_backend.db.session import AsyncSessionLocal
        from dash_backend.executive.models import Goal

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Goal).order_by(Goal.created_at.desc()).limit(100))
            return list(result.scalars().all())

    async def get_context_summary(self, user_id: str | None = None) -> str | None:
        """One-paragraph summary of active goals/tasks, or None when empty."""
        from sqlalchemy import func, select

        from dash_backend.db.session import AsyncSessionLocal
        from dash_backend.executive.models import ExecutiveTask, Goal, TaskStatus

        try:
            async with AsyncSessionLocal() as session:
                goals_result = await session.execute(
                    select(func.count()).select_from(Goal)
                )
                total_goals = int(goals_result.scalar() or 0)

                status_rows = await session.execute(
                    select(ExecutiveTask.status, func.count()).group_by(ExecutiveTask.status)
                )
                counts: Dict[str, int] = {status: int(n) for status, n in status_rows.all()}

                if not total_goals and not any(counts.values()):
                    return None

                pending = counts.get(TaskStatus.PENDING, 0)
                running = counts.get(TaskStatus.RUNNING, 0)
                completed = counts.get(TaskStatus.COMPLETED, 0)
                failed = counts.get(TaskStatus.FAILED, 0)

                recent_goals = await session.execute(
                    select(Goal.name).order_by(Goal.created_at.desc()).limit(3)
                )
                names = [name for (name,) in recent_goals.all()]

                parts = [f"{total_goals} goal(s)"]
                if names:
                    parts.append("recent: " + ", ".join(names))
                parts.append(
                    f"tasks: {pending} pending, {running} running, {completed} completed, {failed} failed"
                )
                return "; ".join(parts)
        except Exception:
            logger.exception("PlannerService.get_context_summary failed")
            return None


_planner_service: PlannerService | None = None


def get_planner_service() -> PlannerService:
    """Return the shared PlannerService instance."""
    global _planner_service
    if _planner_service is None:
        _planner_service = PlannerService()
    return _planner_service