"""DASH Agent Ecosystem.

A coordinated network of specialized AI agents, all managed by the Master
Orchestrator. The user always talks to ONE AI; internally many agents
collaborate. This package is purely additive — it expands the architecture
without recreating or overwriting existing working implementations.

Agents:
- Voice Agent
- Security Agent
- Scheduler Agent
- System Monitor Agent
- Knowledge Agent
- Conversation Agent
- Android Agent (future)
- Smart Home Agent (future)

Cross-cutting:
- Common agent framework (``base``)
- Ecosystem registry (``registry``)
- Failure recovery / self-improvement / task memory (``orchestrator_extension``)
"""

from __future__ import annotations

from dash_backend.agents.ecosystem.base import (
    AGENT_COMMON_FIELDS,
    AgentDependency,
    AgentHealthState,
    AgentPriority,
    AgentSpec,
    AgentStatus,
    BaseAgent,
)
from dash_backend.agents.ecosystem.registry import (
    AgentRegistry,
    get_agent_registry,
    register_builtin_agents,
)
from dash_backend.agents.ecosystem.orchestrator_extension import (
    EcosystemOrchestratorMixin,
    FailureRecovery,
    ImprovementStore,
    LearnedStrategy,
    TaskMemoryRecord,
    TaskMemoryStore,
    get_ecosystem_state,
)

__all__ = [
    # base
    "AGENT_COMMON_FIELDS",
    "AgentDependency",
    "AgentHealthState",
    "AgentPriority",
    "AgentSpec",
    "AgentStatus",
    "BaseAgent",
    # registry
    "AgentRegistry",
    "get_agent_registry",
    "register_builtin_agents",
    # orchestrator_extension
    "EcosystemOrchestratorMixin",
    "FailureRecovery",
    "ImprovementStore",
    "LearnedStrategy",
    "TaskMemoryRecord",
    "TaskMemoryStore",
    "get_ecosystem_state",
]
