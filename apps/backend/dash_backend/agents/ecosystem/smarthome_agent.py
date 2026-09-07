"""Smart Home Agent (Future).

A forward-compatible stub for smart home / IoT control. It defines the common
agent contract so a future smart home integration can register without an
orchestration rewrite. Returns a "not yet enabled" contract for now.
"""

from __future__ import annotations

from typing import Any, Dict, List

from dash_backend.agents.ecosystem.base import (
    AgentDependency,
    AgentPriority,
    AgentSpec,
    BaseAgent,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def smarthome_agent_spec() -> AgentSpec:
    """The declarative spec for the Future Smart Home Agent."""
    return AgentSpec(
        key="smarthome",
        name="Smart Home Agent",
        description=(
            "(Future) Controls smart home devices, scenes and routines. "
            "Contract reserved for future release."
        ),
        capabilities=[
            "device_control",
            "scenes",
            "routines",
            "automation",
        ],
        priority=AgentPriority.LOW,
        permissions=["home_devices"],
        dependencies=[],
        tools=["control_device", "activate_scene", "list_devices"],
        memory_access="read_write",
        execution_api="async",
        category="future",
        enabled=False,
        system_prompt=(
            "You are DASH's future Smart Home Agent. This agent is a stub "
            "awaiting the smart home integration release."
        ),
    )


class SmartHomeAgent(BaseAgent):
    """Runtime stub for the Smart Home Agent."""

    def __init__(self) -> None:
        super().__init__(smarthome_agent_spec())

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"enabled": False, "note": "available soon"}


_smarthome_agent: SmartHomeAgent | None = None


def get_smarthome_agent() -> SmartHomeAgent:
    """Return the Smart Home Agent singleton."""
    global _smarthome_agent
    if _smarthome_agent is None:
        _smarthome_agent = SmartHomeAgent()
    return _smarthome_agent
