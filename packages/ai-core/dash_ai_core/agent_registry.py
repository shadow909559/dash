"""Agent registry.

Keeps a mapping of agent_id -> agent implementation.
"""

from __future__ import annotations

from typing import Mapping

from .agent_interface import Agent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        agent_id = agent.id
        if not agent_id:
            raise ValueError("Agent id must be non-empty")
        self._agents[agent_id] = agent

    def get(self, agent_id: str) -> Agent:
        try:
            return self._agents[agent_id]
        except KeyError as e:
            raise KeyError(f"Unknown agent: {agent_id}") from e

    def all_agents(self) -> Mapping[str, Agent]:
        return dict(self._agents)

