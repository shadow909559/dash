"""Shared models for DASH AI core (scaffold).

This module intentionally avoids any LLM API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence



@dataclass(frozen=True, slots=True)
class Task:
    """A unit of work to be executed by an agent/executor."""

    id: str
    user_request: str
    input: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Description of a tool callable by name."""

    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class AgentStep:
    """A single step in a plan."""

    agent_id: str
    input: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Plan:
    """A plan describing which agent steps to execute."""

    steps: Sequence[AgentStep]


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Standard result produced by an agent."""

    output: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    """Final result produced by an orchestration run."""

    output: Mapping[str, Any]
    executed_agent_ids: Sequence[str]

