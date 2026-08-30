"""Confidence Scoring Engine.

Every answer DASH produces is internally scored for:
- Confidence (how sure the AI is of the answer / action)
- Risk (how risky an action is to perform)
- Missing Information (what the AI knows it does not know)
- Required Clarification (whether the user must answer before proceeding)

These scores are internal and are NEVER exposed as chain-of-thought. They inform
how DASH decides, verifies, and communicates with the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ConfidenceAssessment:
    """Internal confidence/risk/missing-info assessment for a response."""

    confidence: float = 0.5
    risk: float = 0.0
    missing_information: List[str] = field(default_factory=list)
    required_clarification: List[str] = field(default_factory=list)
    uncertainty_reasons: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a serializable dict (internal only — never shown verbatim)."""
        return {
            "confidence": round(self.confidence, 3),
            "risk": round(self.risk, 3),
            "missing_information": self.missing_information,
            "required_clarification": self.required_clarification,
            "uncertainty_reasons": self.uncertainty_reasons,
            "suggested_actions": self.suggested_actions,
        }

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.75

    @property
    def needs_clarification(self) -> bool:
        return bool(self.required_clarification) or self.confidence < 0.4

    @property
    def is_risky(self) -> bool:
        return self.risk >= 0.6


class ConfidenceEngine:
    """Computes internal confidence/risk assessments for queries and actions."""

    # Keywords/phrases that indicate missing information or ambiguity.
    MISSING_INFO_HINTS = [
        "which", "who", "where", "when", "how much", "how many",
        "what time", "what date", "could you", "can you please",
        "if possible", "maybe", "perhaps", "not sure", "unsure",
    ]

    # Keywords that raise the risk of an action (mutating/system-level).
    RISK_KEYWORDS = [
        "delete", "remove", "rm ", "drop", "format", "wipe",
        "shutdown", "restart", "kill", "force", "overwrite",
        "reset", "uninstall", "clear", "truncate", "erase",
        "send", "email", "transfer", "publish", "post", "push",
    ]

    # Keywords that make an action require confirmation.
    CLARIFICATION_KEYWORDS = [
        "it", "that", "this", "there", "those", "these", "them",
        "my file", "the file", "that folder", "this folder",
    ]

    def assess_query(self, query: str) -> ConfidenceAssessment:
        """Assess a user query for confidence/missing-info/clarification."""
        q = (query or "").strip()
        lower = q.lower()

        missing: List[str] = []
        for hint in self.MISSING_INFO_HINTS:
            if hint in lower:
                missing.append(hint)

        clarification: List[str] = []
        # Short/vague queries
        if len(q.split()) <= 2:
            clarification.append("The request is very short. More detail would help.")
        for kw in self.CLARIFICATION_KEYWORDS:
            if kw in lower and len(q.split()) <= 6:
                clarification.append(f"Ambiguous reference: '{kw}'.")

        # Confidence heuristic: more detail + on-topic terms → higher confidence
        confidence = 0.5
        word_count = len(lower.split())
        if word_count >= 6:
            confidence += 0.15
        if word_count >= 12:
            confidence += 0.1
        if not missing:
            confidence += 0.1
        if clarification:
            confidence -= 0.2

        # Risk: check for risky action verbs
        risk = 0.0
        for kw in self.RISK_KEYWORDS:
            if kw in lower:
                risk = max(risk, 0.55)
                if kw in ("delete", "remove", "rm", "drop", "format", "wipe", "shutdown", "kill", "force"):
                    risk = max(risk, 0.85)

        confidence = max(0.05, min(0.98, confidence))

        return ConfidenceAssessment(
            confidence=confidence,
            risk=risk,
            missing_information=missing,
            required_clarification=clarification,
            uncertainty_reasons=missing,
            suggested_actions=self._suggest_actions(confidence, risk, clarification),
        )

    def assess_action(
        self,
        description: str,
        requires_approval: bool = False,
        irreversible: bool = False,
    ) -> ConfidenceAssessment:
        """Assess an action before DASH performs it (pre-execution verification)."""
        lower = (description or "").lower()
        risk = 0.0
        if irreversible:
            risk = max(risk, 0.9)
        for kw in self.RISK_KEYWORDS:
            if kw in lower:
                risk = max(risk, 0.7 if kw in ("delete", "remove", "rm", "drop", "format", "wipe", "shutdown", "kill", "force") else 0.5)
        if requires_approval:
            risk = max(risk, 0.6)

        confidence = 0.7
        if risk >= 0.8:
            confidence -= 0.3
        elif risk >= 0.6:
            confidence -= 0.15

        required_clarification: List[str] = []
        if risk >= 0.8:
            required_clarification.append("This action is high-risk. Confirm before proceeding.")

        return ConfidenceAssessment(
            confidence=max(0.1, min(0.98, confidence)),
            risk=max(0.0, min(1.0, risk)),
            missing_information=[],
            required_clarification=required_clarification,
            uncertainty_reasons=[] if risk < 0.8 else ["High-risk action"],
            suggested_actions=self._suggest_actions(confidence, risk, required_clarification),
        )

    def _suggest_actions(
        self,
        confidence: float,
        risk: float,
        clarifications: List[str],
    ) -> List[str]:
        """Suggest how DASH should respond based on internal scores."""
        actions: List[str] = []
        if clarifications:
            actions.append("ask_user_for_clarification")
        elif risk >= 0.8:
            actions.append("request_confirmation")
        elif confidence < 0.4:
            actions.append("gather_more_information")
        elif confidence >= 0.75:
            actions.append("proceed_with_confidence")
        else:
            actions.append("proceed_and_verify")
        return actions


# Global singleton
_confidence_engine: Optional[ConfidenceEngine] = None


def get_confidence_engine() -> ConfidenceEngine:
    """Return the global ConfidenceEngine singleton."""
    global _confidence_engine
    if _confidence_engine is None:
        _confidence_engine = ConfidenceEngine()
    return _confidence_engine
