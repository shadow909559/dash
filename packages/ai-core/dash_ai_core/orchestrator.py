"""Orchestrator.

Top-level coordinator: receives user request, plans, and executes.

No LLM API calls are made.
"""

from __future__ import annotations

from typing import Any, Mapping

from .executor import Executor
from .models import OrchestrationResult, Plan
from .planner import Planner


class Orchestrator:
    def __init__(self, *, planner: Planner, executor: Executor) -> None:
        self._planner = planner
        self._executor = executor

    def handle(self, user_request: str, *, context: Mapping[str, Any] | None = None) -> OrchestrationResult:
        context = context or {}
        plan: Plan = self._planner.plan(user_request, context=context)

        # Empty plan -> empty result
        if not plan.steps:
            return OrchestrationResult(output={}, executed_agent_ids=[])

        return self._executor.execute(user_request, plan)


