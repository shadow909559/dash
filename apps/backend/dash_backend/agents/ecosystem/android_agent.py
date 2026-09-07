"""Android Agent (Future).

A forward-compatible stub for mobile/Android control. It wraps the existing
``phone`` module contract so a future mobile integration can register without
an orchestration rewrite. It is intentionally minimal and returns a "not yet
enabled" contract for now.
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


def android_agent_spec() -> AgentSpec:
    """The declarative spec for the Future Android Agent."""
    return AgentSpec(
        key="android",
        name="Android Agent",
        description=(
            "(Future) Controls Android devices via ADB, reads phone state, "
            "and automates mobile tasks. Contract reserved for future release."
        ),
        capabilities=[
            "android_control",
            "adb",
            "phone_state",
            "mobile_automation",
        ],
        priority=AgentPriority.LOW,
        permissions=["adb"],
        dependencies=[
            AgentDependency(name="phone", kind="service", required=False),
        ],
        tools=["adb_execute", "list_devices", "phone_status"],
        memory_access="read",
        execution_api="async",
        category="future",
        enabled=False,
        system_prompt=(
            "You are DASH's future Android Agent. This agent is a stub awaiting "
            "the mobile integration release."
        ),
    )


class AndroidAgent(BaseAgent):
    """Runtime stub for the Android Agent."""

    def __init__(self) -> None:
        super().__init__(android_agent_spec())

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Best-effort: try the existing phone service; otherwise return stub.
        try:
            from dash_backend.phone.service import get_phone_status  # type: ignore[import-not-found]
            status = await get_phone_status()
            return {"enabled": False, "status": status, "note": "available soon"}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Android agent stub: %s", exc)
            return {"enabled": False, "note": "available soon"}


_android_agent: AndroidAgent | None = None


def get_android_agent() -> AndroidAgent:
    """Return the Android Agent singleton."""
    global _android_agent
    if _android_agent is None:
        _android_agent = AndroidAgent()
    return _android_agent
