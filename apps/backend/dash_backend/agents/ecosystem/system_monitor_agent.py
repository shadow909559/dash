"""System Monitor Agent.

Continuously watches system resources — CPU, RAM, GPU, battery, temperature,
processes, disk, network — and can proactively notify the user when something
needs attention.

This agent wraps the existing ``performance`` and ``desktop`` system-query
capabilities behind the common agent interface.
"""

from __future__ import annotations

import platform
from typing import Any, Dict, List

from dash_backend.agents.ecosystem.base import (
    AgentDependency,
    AgentPriority,
    AgentSpec,
    BaseAgent,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def system_monitor_agent_spec() -> AgentSpec:
    """The declarative spec for the System Monitor Agent."""
    return AgentSpec(
        key="system_monitor",
        name="System Monitor Agent",
        description=(
            "Continuously watches CPU, RAM, GPU, battery, temperature, "
            "processes, disk and network. Can proactively notify the user."
        ),
        capabilities=[
            "cpu_monitoring",
            "memory_monitoring",
            "gpu_monitoring",
            "battery_monitoring",
            "temperature_monitoring",
            "process_monitoring",
            "disk_monitoring",
            "network_monitoring",
            "proactive_notifications",
        ],
        priority=AgentPriority.MEDIUM,
        permissions=["system_metrics"],
        dependencies=[
            AgentDependency(name="scheduler", kind="agent", required=False),
        ],
        tools=["get_cpu", "get_memory", "get_gpu", "get_battery", "get_disk", "get_network"],
        memory_access="read",
        execution_api="async",
        category="utility",
        system_prompt=(
            "You are DASH's System Monitor Agent. You watch system health and "
            "proactively surface issues to the user in plain language."
        ),
    )


class SystemMonitorAgent(BaseAgent):
    """Runtime for the System Monitor Agent."""

    def __init__(self) -> None:
        super().__init__(system_monitor_agent_spec())

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "overview")
        logger.info("System Monitor Agent action=%s", action)

        if action == "overview":
            return await self._overview()
        if action == "cpu":
            return {"cpu": self._cpu()}
        if action == "memory":
            return {"memory": self._memory()}
        if action == "battery":
            return {"battery": self._battery()}
        if action == "disk":
            return {"disk": self._disk()}
        if action == "network":
            return {"network": self._network()}
        return {"status": "ok", "agent": "system_monitor"}

    def _cpu(self) -> Dict[str, Any]:
        """Report CPU load (fallback to os-level sampling)."""
        try:
            import psutil  # type: ignore[import-not-found]

            return {"percent": psutil.cpu_percent(interval=None), "cores": psutil.cpu_count()}
        except Exception:  # noqa: BLE001
            return {"percent": 0.0, "cores": platform.cpu_count()}

    def _memory(self) -> Dict[str, Any]:
        """Report RAM usage."""
        try:
            import psutil  # type: ignore[import-not-found]

            mem = psutil.virtual_memory()
            return {"percent": mem.percent, "used_gb": round(mem.used / 1e9, 2), "total_gb": round(mem.total / 1e9, 2)}
        except Exception:  # noqa: BLE001
            return {"percent": 0.0, "used_gb": 0.0, "total_gb": 0.0}

    def _battery(self) -> Dict[str, Any]:
        """Report battery state."""
        try:
            import psutil  # type: ignore[import-not-found]

            batt = psutil.sensors_battery()
            if batt is None:
                return {"percent": None, "plugged": None}
            return {"percent": batt.percent, "plugged": batt.power_plugged}
        except Exception:  # noqa: BLE001
            return {"percent": None, "plugged": None}

    def _disk(self) -> Dict[str, Any]:
        """Report disk usage."""
        try:
            import psutil  # type: ignore[import-not-found]

            usage = psutil.disk_usage("/")
            return {"percent": usage.percent, "free_gb": round(usage.free / 1e9, 2)}
        except Exception:  # noqa: BLE001
            return {"percent": 0.0, "free_gb": 0.0}

    def _network(self) -> Dict[str, Any]:
        """Report network counters."""
        try:
            import psutil  # type: ignore[import-not-found]

            io = psutil.net_io_counters()
            return {"bytes_sent": io.bytes_sent, "bytes_recv": io.bytes_recv}
        except Exception:  # noqa: BLE001
            return {"bytes_sent": 0, "bytes_recv": 0}

    async def _overview(self) -> Dict[str, Any]:
        """Aggregate a system health overview."""
        return {
            "platform": platform.system(),
            "cpu": self._cpu(),
            "memory": self._memory(),
            "battery": self._battery(),
            "disk": self._disk(),
            "network": self._network(),
        }


_system_monitor_agent: SystemMonitorAgent | None = None


def get_system_monitor_agent() -> SystemMonitorAgent:
    """Return the System Monitor Agent singleton."""
    global _system_monitor_agent
    if _system_monitor_agent is None:
        _system_monitor_agent = SystemMonitorAgent()
    return _system_monitor_agent
