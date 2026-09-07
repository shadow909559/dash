"""Common Agent Framework.

Every agent in the DASH ecosystem follows this single common interface.

An agent is defined by an ``AgentSpec`` (declarative metadata) and a
``BaseAgent`` runtime that wraps it with a health check, an execution API, and
status tracking. The Master Orchestrator is the ONLY component that talks to
the user; agents collaborate internally through these specs.

This module is purely additive — it does not modify the existing
``intelligence.agent_system.Agent`` dataclass, but is designed to be
interoperable with it (an ``AgentSpec`` can be converted to an
``intelligence.Agent`` for the existing ``AgentSystem``).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class AgentPriority(int, Enum):
    """Priority of an agent relative to others in the ecosystem."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AgentHealthState(str, Enum):
    """Health state of an agent at runtime."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AgentStatus(str, Enum):
    """Runtime status of an agent."""

    IDLE = "idle"
    BUSY = "busy"
    WAITING = "waiting"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class AgentDependency:
    """A declared dependency of an agent (another agent or tool)."""

    name: str
    kind: str = "agent"  # "agent" | "tool" | "service"
    required: bool = True
    description: str = ""


@dataclass
class AgentSpec:
    """Declarative metadata that defines an agent.

    This is the common interface every agent must satisfy. It captures:

    - name / description
    - capabilities
    - priority
    - required permissions
    - dependencies
    - tools
    - memory access
    - execution API
    - health status
    - current task
    """

    key: str
    name: str
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    priority: AgentPriority = AgentPriority.MEDIUM
    permissions: List[str] = field(default_factory=list)
    dependencies: List[AgentDependency] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    memory_access: str = "read"  # "none" | "read" | "read_write"
    execution_api: str = "async"  # "sync" | "async" | "stream"
    system_prompt: str = ""
    category: str = "general"  # core | utility | future
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "priority": self.priority.name,
            "permissions": self.permissions,
            "dependencies": [d.__dict__ for d in self.dependencies],
            "tools": self.tools,
            "memory_access": self.memory_access,
            "execution_api": self.execution_api,
            "category": self.category,
            "enabled": self.enabled,
        }


class BaseAgent:
    """Runtime wrapper around an AgentSpec.

    Provides the common execution API used by the orchestrator:

    - ``execute(payload)``  → run the agent's core logic
    - ``health()``           → current health check
    - ``status()``           → runtime status + current task
    - ``set_task()/clear_task()`` → track what the agent is doing
    """

    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec
        self.id = str(uuid.uuid4())
        self._status: AgentStatus = AgentStatus.IDLE
        self._health: AgentHealthState = AgentHealthState.UNKNOWN
        self._current_task: Optional[str] = None
        self._last_activity: float = time.time()
        self._error: Optional[str] = None
        self._stats: Dict[str, Any] = {
            "executions": 0,
            "failures": 0,
            "total_time_ms": 0,
        }

    # ──────────────────────────────────────────────
    # Public execution API
    # ──────────────────────────────────────────────

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's core logic.

        Subclasses override ``_run`` for the actual implementation. This
        wrapper handles status/health/stats bookkeeping so every agent behaves
        identically from the orchestrator's perspective.
        """
        self._status = AgentStatus.BUSY
        self._current_task = str(payload.get("task", payload)[:120])
        self._last_activity = time.time()
        start = time.time()
        self._stats["executions"] += 1

        try:
            result = await self._run(payload)
            self._health = AgentHealthState.HEALTHY
            self._error = None
            return result
        except Exception as exc:  # noqa: BLE001
            self._health = AgentHealthState.UNHEALTHY
            self._error = str(exc)
            self._stats["failures"] += 1
            raise
        finally:
            elapsed = int((time.time() - start) * 1000)
            self._stats["total_time_ms"] += elapsed
            self._status = AgentStatus.IDLE
            self._current_task = None

    async def health(self) -> Dict[str, Any]:
        """Return the current health status of the agent."""
        return {
            "agent": self.spec.key,
            "state": self._health.value,
            "error": self._error,
            "last_activity": self._last_activity,
            "uptime_s": int(time.time() - self._last_activity),
        }

    async def status(self) -> Dict[str, Any]:
        """Return runtime status + current task."""
        return {
            "agent": self.spec.key,
            "status": self._status.value,
            "current_task": self._current_task,
            "stats": dict(self._stats),
        }

    def set_task(self, task: Optional[str]) -> None:
        """Manually set/clear the current task (best-effort tracking)."""
        self._current_task = task
        self._last_activity = time.time()

    def clear_task(self) -> None:
        """Clear the current task."""
        self._current_task = None

    # ──────────────────────────────────────────────
    # Hooks
    # ──────────────────────────────────────────────

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Subclasses implement the actual agent logic here."""
        raise NotImplementedError(f"{self.spec.key} Agent must implement _run")

    def can_handle(self, task: str) -> bool:
        """Lightweight capability check (keyword-based default).

        Subclasses override for smarter matching.
        """
        text = task.lower()
        return any(kw in text for kw in self.spec.keywords if kw)  # type: ignore[attr-defined]


# Convenience alias for the orchestrator extension
AGENT_COMMON_FIELDS = [
    "name",
    "capabilities",
    "priority",
    "permissions",
    "dependencies",
    "tools",
    "memory_access",
    "execution_api",
    "health_status",
    "current_task",
]
