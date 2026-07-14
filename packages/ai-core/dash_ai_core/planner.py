"""Planner.

The planner selects which agents should execute which steps.

This package avoids LLM calls; the default implementation uses agent
predicates.
"""


from __future__ import annotations

from typing import Any, Mapping


from .agent_registry import AgentRegistry
from .models import AgentStep, Plan


class Planner:
    def __init__(self, *, agent_registry: AgentRegistry) -> None:
        self._agent_registry = agent_registry

    def plan(self, user_request: str, *, context: Mapping[str, Any] | None = None) -> Plan:
        context = context or {}

        # Deterministic: pick all agents that can handle request, in registration order.
        steps: list[AgentStep] = []
        for agent_id, agent in self._agent_registry.all_agents().items():
            if agent.can_handle(user_request):
                steps.append(AgentStep(agent_id=agent_id, input=dict(context)))

        # If nothing matches, produce empty plan.
        # Orchestrator/executor can decide how to handle.
        return Plan(steps=steps)


def single_step_plan(agent_id: str, *, input: Mapping[str, Any] | None = None) -> Plan:
    """Helper for tests and simple planning."""

    input = input or {}
    return Plan(steps=[AgentStep(agent_id=agent_id, input=dict(input))])

