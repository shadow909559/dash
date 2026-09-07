"""Agent Ecosystem Registry.

Maintains the catalog of all agents in the DASH ecosystem. It provides a
plugin-friendly auto-registration hook so future plugins can register new
agents without an architecture rewrite.

The registry is read-only from the orchestrator's perspective — agents are
*discovered* here, then executed by the orchestrator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from dash_backend.agents.ecosystem.base import AgentSpec, BaseAgent
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class AgentRegistry:
    """A registry of agent specs and their runtime instances."""

    def __init__(self) -> None:
        self._specs: Dict[str, AgentSpec] = {}
        self._runtimes: Dict[str, BaseAgent] = {}
        self._factories: Dict[str, Any] = {}

    # ──────────────────────────────────────────────
    # Registration
    # ──────────────────────────────────────────────

    def register(self, spec: AgentSpec, runtime: Optional[BaseAgent] = None) -> None:
        """Register an agent spec (and optionally a prebuilt runtime)."""
        self._specs[spec.key] = spec
        if runtime is not None:
            self._runtimes[spec.key] = runtime
        logger.info("Registered ecosystem agent: %s", spec.key)

    def register_factory(self, key: str, factory: Any) -> None:
        """Register a factory that produces a BaseAgent on demand.

        This is the plugin auto-registration hook: a plugin can register a
        factory for a new agent key and the orchestrator can instantiate it
        lazily without any architecture change.
        """
        self._factories[key] = factory
        logger.info("Registered ecosystem agent factory: %s", key)

    # ──────────────────────────────────────────────
    # Lookup
    # ──────────────────────────────────────────────

    def get_spec(self, key: str) -> Optional[AgentSpec]:
        """Get an agent spec by key."""
        return self._specs.get(key)

    def get_runtime(self, key: str) -> Optional[BaseAgent]:
        """Get (or lazily create) a runtime for an agent key."""
        if key in self._runtimes:
            return self._runtimes[key]
        # Lazy factory instantiation supports plugin agents transparently.
        factory = self._factories.get(key)
        if factory is not None:
            runtime = factory()
            self._runtimes[key] = runtime
            return runtime
        return None

    def list_specs(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered specs (optionally filtered by category)."""
        specs = list(self._specs.values())
        if category is not None:
            specs = [s for s in specs if s.category == category]
        return [s.to_dict() for s in specs]

    def list_keys(self) -> List[str]:
        """List all registered agent keys."""
        return sorted(self._specs.keys())

    def enabled_keys(self) -> List[str]:
        """List keys of enabled agents (excludes future stubs)."""
        return [k for k, s in self._specs.items() if s.enabled]

    @property
    def count(self) -> int:
        """Number of registered agent specs."""
        return len(self._specs)


# Global singleton
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Return the global AgentRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def register_builtin_agents() -> None:
    """Register all built-in ecosystem agents.

    This is called once at import time (or application startup) to seed the
    registry with the core + utility + future agents defined in this package.
    """
    registry = get_agent_registry()

    # Lazy imports to avoid circular deps at module load.
    from dash_backend.agents.ecosystem.voice_agent import VoiceAgent, voice_agent_spec
    from dash_backend.agents.ecosystem.security_agent import SecurityAgent, security_agent_spec
    from dash_backend.agents.ecosystem.scheduler_agent import SchedulerAgent, scheduler_agent_spec
    from dash_backend.agents.ecosystem.system_monitor_agent import SystemMonitorAgent, system_monitor_agent_spec
    from dash_backend.agents.ecosystem.knowledge_agent import KnowledgeAgent, knowledge_agent_spec
    from dash_backend.agents.ecosystem.conversation_agent import ConversationAgent, conversation_agent_spec
    from dash_backend.agents.ecosystem.android_agent import AndroidAgent, android_agent_spec
    from dash_backend.agents.ecosystem.smarthome_agent import SmartHomeAgent, smarthome_agent_spec

    builtins = [
        (voice_agent_spec(), VoiceAgent),
        (security_agent_spec(), SecurityAgent),
        (scheduler_agent_spec(), SchedulerAgent),
        (system_monitor_agent_spec(), SystemMonitorAgent),
        (knowledge_agent_spec(), KnowledgeAgent),
        (conversation_agent_spec(), ConversationAgent),
        (android_agent_spec(), AndroidAgent),
        (smarthome_agent_spec(), SmartHomeAgent),
    ]

    for spec, runtime_cls in builtins:
        # Register the spec + a factory that produces a fresh runtime.
        registry.register(spec)
        registry.register_factory(spec.key, runtime_cls)


# Seed the registry once at import time.
register_builtin_agents()
