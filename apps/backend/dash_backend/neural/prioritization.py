"""Task Prioritization Engine — classifies tasks by urgency and importance.

DASH automatically schedules work into:
- Urgent (do now)
- Important (do soon)
- Background (do when possible)
- Optional (do if time permits)

The engine uses a lightweight Eisenhower-style matrix with keyword heuristics
and a configurable deadline signal.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TaskPriority:
    """A task classified by urgency and importance."""

    task: str
    tier: str  # urgent | important | background | optional
    urgency: float = 0.0
    importance: float = 0.0
    deadline: Optional[float] = None
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "tier": self.tier,
            "urgency": round(self.urgency, 3),
            "importance": round(self.importance, 3),
            "deadline": self.deadline,
            "reasons": self.reasons,
        }


class PrioritizationEngine:
    """Classifies tasks into urgency/importance tiers."""

    # Strong urgency signals.
    URGENT_KEYWORDS = [
        "asap", "urgent", "immediately", "right now", "emergency",
        "critical", "now", "deadline", "due", "today", "tonight",
        "before tomorrow", "tomorrow", "must", "required",
    ]

    # Strong importance signals.
    IMPORTANT_KEYWORDS = [
        "important", "key", "major", "essential", "crucial", "vital",
        "priority", "high value", "strategic", "core", "primary",
        "interview", "exam", "presentation", "meeting", "deadline",
    ]

    # Background signals.
    BACKGROUND_KEYWORDS = [
        "background", "later", "when i have time", "eventually",
        "someday", "remind me to", "sometime", "low priority",
    ]

    # Optional signals.
    OPTIONAL_KEYWORDS = [
        "optional", "maybe", "if possible", "nice to have",
        "whenever", "not urgent", "someday maybe",
    ]

    def classify(self, task: str, deadline: Optional[float] = None) -> TaskPriority:
        """Classify a single task into a priority tier."""
        lower = (task or "").lower()
        reasons: List[str] = []

        urgency = 0.0
        for kw in self.URGENT_KEYWORDS:
            if kw in lower:
                urgency = max(urgency, 0.8)
                reasons.append(f"Urgency keyword: '{kw}'")

        importance = 0.0
        for kw in self.IMPORTANT_KEYWORDS:
            if kw in lower:
                importance = max(importance, 0.8)
                reasons.append(f"Importance keyword: '{kw}'")

        # Deadline proximity boosts urgency.
        if deadline is not None:
            now = time.time()
            hours_left = max(0.0, (deadline - now) / 3600.0)
            if hours_left <= 24:
                urgency = max(urgency, 0.95)
                reasons.append(f"Deadline within {hours_left:.0f}h")
            elif hours_left <= 72:
                urgency = max(urgency, 0.7)
                reasons.append(f"Deadline within {hours_left:.0f}h")

        # Background / optional signals reduce urgency.
        for kw in self.BACKGROUND_KEYWORDS:
            if kw in lower:
                urgency = min(urgency, 0.3)
                reasons.append(f"Background keyword: '{kw}'")
        for kw in self.OPTIONAL_KEYWORDS:
            if kw in lower:
                urgency = min(urgency, 0.15)
                importance = min(importance, 0.4)
                reasons.append(f"Optional keyword: '{kw}'")

        # Default importance for tasks with no signal.
        if importance == 0.0:
            importance = 0.4
            reasons.append("No explicit importance signal; defaulting to moderate.")

        # Eisenhower-style tiering.
        if urgency >= 0.7 and importance >= 0.6:
            tier = "urgent"
        elif importance >= 0.6:
            tier = "important"
        elif urgency >= 0.5:
            tier = "urgent"
        elif urgency <= 0.2 and importance <= 0.4:
            tier = "optional"
        else:
            tier = "background"

        return TaskPriority(
            task=task,
            tier=tier,
            urgency=urgency,
            importance=importance,
            deadline=deadline,
            reasons=reasons,
        )

    def classify_many(
        self,
        tasks: List[str],
        deadlines: Optional[Dict[str, float]] = None,
    ) -> List[TaskPriority]:
        """Classify multiple tasks and sort by priority tier."""
        deadlines = deadlines or {}
        classified = [
            self.classify(task, deadline=deadlines.get(task))
            for task in tasks
        ]
        tier_order = {"urgent": 0, "important": 1, "background": 2, "optional": 3}
        classified.sort(key=lambda p: (tier_order.get(p.tier, 4), -p.urgency))
        return classified

    def schedule(self, tasks: List[str]) -> Dict[str, List[str]]:
        """Group tasks into a suggested execution schedule."""
        classified = self.classify_many(tasks)
        schedule: Dict[str, List[str]] = {
            "urgent": [],
            "important": [],
            "background": [],
            "optional": [],
        }
        for p in classified:
            schedule[p.tier].append(p.task)
        return schedule


# Global singleton
_prioritization_engine: Optional[PrioritizationEngine] = None


def get_prioritization_engine() -> PrioritizationEngine:
    """Return the global PrioritizationEngine singleton."""
    global _prioritization_engine
    if _prioritization_engine is None:
        _prioritization_engine = PrioritizationEngine()
    return _prioritization_engine