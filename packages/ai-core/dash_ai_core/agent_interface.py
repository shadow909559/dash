"""Agent contract.

Agents perform actions to satisfy a task.

This module avoids any LLM API calls.
"""


from __future__ import annotations

from typing import Mapping, Protocol, Sequence

from .models import AgentResult, Task


class Agent(Protocol):
    """Contract for an agent implementation."""

    @property
    def id(self) -> str:
        """Unique agent identifier."""

    @property
    def capabilities(self) -> Sequence[str]:
        """Capabilities advertised by this agent."""

    def can_handle(self, user_request: str) -> bool:
        """Cheap predicate used by the planner/orchestrator."""

    def execute(self, task: Task, *, tool_context: Mapping[str, object]) -> AgentResult:
        """Execute the task.

        `tool_context` is provided by the executor and may include tool
        registries, provider references, etc. No LLM calls are made here.
        """

