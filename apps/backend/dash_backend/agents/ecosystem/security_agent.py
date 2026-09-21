"""Security Agent.

Validates permissions, flags dangerous commands, requires confirmation for
sensitive operations, and guards the system against unsafe actions.

This agent wraps the existing ``security`` module and provides a common
gateway that the Master Orchestrator consults before Execution Agent runs
anything sensitive.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from dash_backend.agents.ecosystem.base import (
    AgentDependency,
    AgentPriority,
    AgentSpec,
    BaseAgent,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Patterns that indicate a potentially dangerous shell command.
DANGEROUS_PATTERNS: List[str] = [
    r"\brm\s+-rf\b",
    r"\bformat\b",
    r"\bdel\s+/s\b",
    r"\bformat\s+[a-z]:",
    r"\b:(){:|:&};:\b",  # fork bomb
    r"\brmdir\s+/s\b",
]


def security_agent_spec() -> AgentSpec:
    """The declarative spec for the Security Agent."""
    return AgentSpec(
        key="security",
        name="Security Agent",
        description=(
            "Validates permissions, flags dangerous commands, requires "
            "confirmation for sensitive operations and guards the system."
        ),
        capabilities=[
            "permission_validation",
            "dangerous_command_detection",
            "confirmation_requests",
            "sensitive_operation_guard",
        ],
        priority=AgentPriority.CRITICAL,
        permissions=["audit", "policy"],
        dependencies=[
            AgentDependency(name="execution", kind="agent", required=True),
        ],
        tools=["validate_permission", "check_dangerous", "request_confirmation"],
        memory_access="read",
        execution_api="async",
        category="core",
        system_prompt=(
            "You are DASH's Security Agent. You validate every sensitive "
            "operation before it executes. You never expose internal policy "
            "details to the user."
        ),
    )


class SecurityAgent(BaseAgent):
    """Runtime for the Security Agent."""

    DANGEROUS = DANGEROUS_PATTERNS

    def __init__(self) -> None:
        super().__init__(security_agent_spec())

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "validate")
        logger.info("Security Agent action=%s", action)

        if action == "validate_permission":
            return await self._validate_permission(payload)
        if action == "check_dangerous":
            return await self._check_dangerous(payload)
        if action == "request_confirmation":
            return await self._request_confirmation(payload)
        return {"status": "ok", "agent": "security"}

    async def _validate_permission(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Check a permission against the REAL permission store.

        The old implementation trusted caller-supplied ``granted_permissions``
        — authority-by-claim, the exact pattern the red-team suite exists to
        kill. Permission state comes from ``PermissionService``; explicit
        deny always overrides allow.
        """
        from dash_backend.services.permissions import get_permission_service

        required = str(payload.get("permission") or "")
        user_id = str(payload.get("user_id") or "")
        if not required or not user_id:
            raise ValueError("validate_permission requires permission and user_id")

        category, _, action = required.rpartition(":")
        category = category or "general"
        action = action or required
        svc = get_permission_service()
        if svc.is_denied(user_id, category, action):
            return {"permission": required, "allowed": False, "reason": "denied"}
        allowed = svc.is_always_allowed(user_id, category, action)
        return {
            "permission": required,
            "allowed": allowed,
            "reason": "granted" if allowed else "missing_permission",
        }

    async def _check_dangerous(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Scan a command/instruction for dangerous patterns."""
        command = str(payload.get("command", payload.get("instruction", "")))
        matches = [p for p in self.DANGEROUS if re.search(p, command, re.IGNORECASE)]
        dangerous = len(matches) > 0
        return {
            "dangerous": dangerous,
            "patterns": matches,
            "requires_confirmation": payload.get("force_confirmation", False) or dangerous,
        }

    async def _request_confirmation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Emit a confirmation request for a sensitive operation."""
        return {
            "requires_confirmation": True,
            "operation": payload.get("operation", ""),
            "reason": payload.get("reason", "sensitive_operation"),
            "approved": payload.get("approved", False),
        }


_security_agent: SecurityAgent | None = None


def get_security_agent() -> SecurityAgent:
    """Return the Security Agent singleton."""
    global _security_agent
    if _security_agent is None:
        _security_agent = SecurityAgent()
    return _security_agent
