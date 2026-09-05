"""Predictive Engine — detects user sequences and offers proactive follow-ups.

Example:
- User always opens VS Code after Chrome → offer to launch it.
- User edits DASH every morning → offer to resume the project.

The engine learns lightweight sequence patterns from observations supplied by
the pipeline and produces ranked, low-risk predictions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# How many recent events are kept per user for sequence mining.
_MAX_EVENT_HISTORY = 200

# A pair (A → B) counts toward prediction only when seen at least this many times.
_MIN_SEQUENCE_CONFIDENCE = 2


@dataclass
class Prediction:
    """A predicted next action for a user."""

    action: str
    confidence: float
    based_on: str
    times_seen: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": round(self.confidence, 3),
            "based_on": self.based_on,
            "times_seen": self.times_seen,
        }


class PredictiveEngine:
    """Learns short action sequences and predicts what the user does next."""

    def __init__(self) -> None:
        self._histories: Dict[str, List[str]] = {}
        self._transitions: Dict[str, Dict[str, int]] = {}
        self._sequence_meta: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # ── Ingestion ──────────────────────────────────────────────────────

    def observe(
        self,
        user_id: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record that the user performed ``action``.

        Metadata may include ``time`` (epoch seconds) and ``context`` (free-form
        dict) and is used to enrich future predictions.
        """
        try:
            action = str(action or "").strip().lower()
            if not action:
                return

            history = self._histories.setdefault(user_id, [])
            if history:
                prev = history[-1]
                self._transitions.setdefault(prev, {})
                self._transitions[prev][action] = self._transitions[prev].get(action, 0) + 1
                self._sequence_meta.setdefault(prev, {}).setdefault(
                    action,
                    {
                        "times": self._transitions[prev][action],
                        "last_seen": time.time(),
                        "last_metadata": metadata or {},
                    },
                )

            history.append(action)
            # Keep a bounded window (oldest first).
            if len(history) > _MAX_EVENT_HISTORY:
                del history[: len(history) - _MAX_EVENT_HISTORY]
        except Exception:
            logger.exception("PredictiveEngine.observe failed")

    # ── Prediction ─────────────────────────────────────────────────────

    def predict_next(self, user_id: str, last_action: Optional[str] = None) -> Optional[Prediction]:
        """Predict the user's next action, if any.

        Uses the most recent action as the anchor if ``last_action`` is not
        supplied. Returns ``None`` when no confident pattern exists.
        """
        try:
            history = self._histories.get(user_id) or []
            if not history:
                return None

            anchor = last_action or history[-1]
            anchor = str(anchor or "").strip().lower()
            if not anchor:
                return None

            transitions = self._transitions.get(anchor)
            if not transitions:
                return None

            best_action: Optional[str] = None
            best_count = 0
            for action, count in transitions.items():
                if count > best_count:
                    best_count = count
                    best_action = action

            if best_action is None or best_count < _MIN_SEQUENCE_CONFIDENCE:
                return None

            meta = (self._sequence_meta.get(anchor) or {}).get(best_action) or {}
            total = sum(self._transitions.get(anchor, {}).values()) or 1
            confidence = min(0.95, best_count / total + 0.3 * (best_count / max(1, len(history))))
            return Prediction(
                action=best_action,
                confidence=confidence,
                based_on=anchor,
                times_seen=best_count,
            )
        except Exception:
            logger.exception("PredictiveEngine.predict_next failed")
            return None

    def predict_sequence(self, user_id: str, limit: int = 5) -> List[Prediction]:
        """Return the top predicted actions for a user."""
        history = self._histories.get(user_id) or []
        seen: set[str] = set()
        predictions: List[Prediction] = []
        for anchor in reversed(history):
            if anchor in seen:
                continue
            seen.add(anchor)
            pred = self.predict_next(user_id, last_action=anchor)
            if pred:
                predictions.append(pred)
            if len(predictions) >= limit:
                break
        return predictions

    def sequences(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the strongest learned sequences for analytics/UI."""
        transitions = self._transitions
        rows: List[Dict[str, Any]] = []
        for anchor, targets in transitions.items():
            for action, count in targets.items():
                if count >= _MIN_SEQUENCE_CONFIDENCE:
                    rows.append(
                        {
                            "from": anchor,
                            "to": action,
                            "times": count,
                            "confidence": min(0.95, count / len(self._histories.get(user_id) or []) + 0.3),
                        }
                    )
        rows.sort(key=lambda r: r["times"], reverse=True)
        return rows[:limit]


# Global singleton
_predictive_engine: Optional[PredictiveEngine] = None


def get_predictive_engine() -> PredictiveEngine:
    """Return the global PredictiveEngine singleton."""
    global _predictive_engine
    if _predictive_engine is None:
        _predictive_engine = PredictiveEngine()
    return _predictive_engine