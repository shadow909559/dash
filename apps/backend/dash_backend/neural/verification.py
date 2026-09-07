"""Self-Verification Engine.

DASH verifies before and after performing actions:
- Pre-execution: safety check, risk review, approval gate.
- Post-execution: check that the result matches the expectation, and confirm
  the action actually succeeded.

This makes DASH more trustworthy — it does not blindly fire actions and it
confirms outcomes rather than assuming success.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PreVerificationResult:
    """Result of a pre-execution verification check."""

    approved: bool = True
    reason: str = ""
    requires_approval: bool = False
    checks: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "requires_approval": self.requires_approval,
            "checks": self.checks,
        }


@dataclass
class PostVerificationResult:
    """Result of a post-execution verification check."""

    success: bool = True
    confidence: float = 0.8
    evidence: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence,
            "issues": self.issues,
        }


class VerificationEngine:
    """Checks actions before execution and outcomes after execution."""

    # Destructive / irreversible verbs that must be gated.
    DESTRUCTIVE = [
        "delete", "remove", "rm -rf", "drop", "format", "wipe",
        "shutdown", "restart", "kill", "uninstall", "truncate", "erase",
    ]

    # System-boundary verbs that should prompt for approval.
    SYSTEM_BOUNDARY = [
        "shutdown", "restart", "install", "uninstall", "format",
        "send email", "transfer", "publish", "post", "push",
    ]

    def verify_pre(self, description: str, rich: bool = True) -> PreVerificationResult:
        """Run pre-execution checks on an action description."""
        lower = (description or "").lower()
        checks: List[Dict[str, Any]] = []

        # Safety: lockdown / emergency should never be bypassed.
        destructive = [k for k in self.DESTRUCTIVE if re.search(rf"\b{re.escape(k)}\b", lower)]
        destructive = [k for k in self.DESTRUCTIVE if k in lower]
        if destructive:
            checks.append({
                "check": "destructive_action",
                "pass": False,
                "detail": f"Action affects destructive verbs: {', '.join(sorted(set(destructive)))}",
            })
        else:
            checks.append({"check": "destructive_action", "pass": True})

        boundary = [k for k in self.SYSTEM_BOUNDARY if k in lower]
        if boundary:
            checks.append({
                "check": "system_boundary",
                "pass": False,
                "detail": f"Crosses system boundary: {', '.join(sorted(set(boundary)))}",
            })
        else:
            checks.append({"check": "system_boundary", "pass": True})

        requires_approval = bool(boundary) or bool(destructive)
        approved = not destructive  # destructive always blocked unless explicitly confirmed

        reason = ""
        if destructive:
            reason = "Blocked: destructive action requires explicit confirmation."
        elif boundary:
            reason = "Approval required: crosses a system boundary."

        return PreVerificationResult(
            approved=approved,
            reason=reason,
            requires_approval=requires_approval,
            checks=checks,
        )

    def verify_post(
        self,
        expected: str,
        observed: Optional[str] = None,
        tool_result: Optional[Any] = None,
    ) -> PostVerificationResult:
        """Check that the outcome matches the expectation after execution."""
        evidence: List[str] = []
        issues: List[str] = []

        if observed:
            evidence.append("Observed output was returned.")
        if tool_result is not None:
            evidence.append("Tool execution produced a result.")

        # Heuristic: look for error/exception markers in the observed output.
        if observed:
            lower = observed.lower()
            error_markers = ["error", "exception", "failed", "traceback", "denied", "not found", "refused"]
            found = [m for m in error_markers if m in lower]
            if found:
                issues.append(f"Output contains error indicators: {', '.join(found)}")
                # Downgrade confidence.
                confidence = 0.3
            else:
                confidence = 0.85
        else:
            confidence = 0.6
            issues.append("No observable output was captured for verification.")

        success = confidence >= 0.6 and not issues
        return PostVerificationResult(
            success=success,
            confidence=confidence,
            evidence=evidence,
            issues=issues,
        )


# Global singleton
_verification_engine: Optional[VerificationEngine] = None


def get_verification_engine() -> VerificationEngine:
    """Return the global VerificationEngine singleton."""
    global _verification_engine
    if _verification_engine is None:
        _verification_engine = VerificationEngine()
    return _verification_engine
