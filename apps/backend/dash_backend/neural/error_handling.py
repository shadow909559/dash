"""Intelligent Error Handling Engine — explains failures clearly and recovers.

Never says "Something went wrong."
Instead explains:
- What failed
- Why
- How DASH is recovering
- What the user can do

The engine classifies errors, produces human-readable explanations, and
suggests recovery actions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ErrorExplanation:
    """A human-readable explanation of a failure."""

    what_failed: str
    why: str
    recovery: str
    user_action: str
    error_type: str = "unknown"
    severity: str = "medium"  # low | medium | high
    recoverable: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "what_failed": self.what_failed,
            "why": self.why,
            "recovery": self.recovery,
            "user_action": self.user_action,
            "error_type": self.error_type,
            "severity": self.severity,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp,
        }


class ErrorHandlingEngine:
    """Classifies errors and produces clear, actionable explanations."""

    # Error type → (what_failed template, why template, recovery, user_action, severity, recoverable)
    ERROR_PATTERNS: Dict[str, Dict[str, Any]] = {
        "timeout": {
            "what_failed": "The operation timed out.",
            "why": "The request took longer than the allowed time.",
            "recovery": "DASH is retrying with a shorter scope.",
            "user_action": "Try breaking the task into smaller steps.",
            "severity": "medium",
            "recoverable": True,
        },
        "connection": {
            "what_failed": "A connection could not be established.",
            "why": "The remote service or device is unreachable.",
            "recovery": "DASH is checking connectivity and will retry.",
            "user_action": "Check your network or the target service.",
            "severity": "high",
            "recoverable": True,
        },
        "permission": {
            "what_failed": "Permission was denied.",
            "why": "The action requires elevated or missing permissions.",
            "recovery": "DASH is checking available permissions.",
            "user_action": "Grant the required permission or run with appropriate access.",
            "severity": "medium",
            "recoverable": False,
        },
        "not_found": {
            "what_failed": "The requested item was not found.",
            "why": "The file, folder, or resource does not exist at the expected location.",
            "recovery": "DASH is searching for the closest match.",
            "user_action": "Verify the path or name.",
            "severity": "low",
            "recoverable": True,
        },
        "validation": {
            "what_failed": "The input could not be validated.",
            "why": "Some required information is missing or malformed.",
            "recovery": "DASH is identifying the missing fields.",
            "user_action": "Provide the missing or corrected information.",
            "severity": "low",
            "recoverable": True,
        },
        "provider": {
            "what_failed": "The AI provider is unavailable.",
            "why": "The configured AI service could not be reached.",
            "recovery": "DASH is falling back to a local model.",
            "user_action": "Check the AI provider configuration.",
            "severity": "high",
            "recoverable": True,
        },
        "unknown": {
            "what_failed": "An unexpected error occurred.",
            "why": "The cause could not be automatically determined.",
            "recovery": "DASH is logging the details for analysis.",
            "user_action": "Retry the action or share the error details.",
            "severity": "medium",
            "recoverable": True,
        },
    }

    def explain(self, error: str, context: str = "") -> ErrorExplanation:
        """Produce a human-readable explanation for an error."""
        lower = (error or "").lower()
        error_type = "unknown"

        for pattern, info in self.ERROR_PATTERNS.items():
            if pattern in lower:
                error_type = pattern
                break

        # Refine by common error markers.
        if any(m in lower for m in ["timed out", "timeout", "deadline exceeded"]):
            error_type = "timeout"
        elif any(m in lower for m in ["connection refused", "connection reset", "unreachable", "network"]):
            error_type = "connection"
        elif any(m in lower for m in ["permission denied", "forbidden", "unauthorized", "access denied"]):
            error_type = "permission"
        elif any(m in lower for m in ["not found", "no such file", "does not exist", "404"]):
            error_type = "not_found"
        elif any(m in lower for m in ["validation", "invalid", "malformed", "missing field"]):
            error_type = "validation"
        elif any(m in lower for m in ["provider", "ollama", "openai", "api key"]):
            error_type = "provider"

        info = self.ERROR_PATTERNS.get(error_type, self.ERROR_PATTERNS["unknown"])

        what_failed = info["what_failed"]
        if context:
            what_failed = f"{what_failed} ({context})"

        return ErrorExplanation(
            what_failed=what_failed,
            why=info["why"],
            recovery=info["recovery"],
            user_action=info["user_action"],
            error_type=error_type,
            severity=info["severity"],
            recoverable=info["recoverable"],
        )

    def format_for_user(self, explanation: ErrorExplanation) -> str:
        """Format an error explanation as a natural user-facing message."""
        lines = [
            f"{explanation.what_failed}",
            f"Why: {explanation.why}",
            f"Recovery: {explanation.recovery}",
        ]
        if explanation.user_action:
            lines.append(f"You can: {explanation.user_action}")
        return "\n".join(lines)


# Global singleton
_error_handling_engine: Optional[ErrorHandlingEngine] = None


def get_error_handling_engine() -> ErrorHandlingEngine:
    """Return the global ErrorHandlingEngine singleton."""
    global _error_handling_engine
    if _error_handling_engine is None:
        _error_handling_engine = ErrorHandlingEngine()
    return _error_handling_engine