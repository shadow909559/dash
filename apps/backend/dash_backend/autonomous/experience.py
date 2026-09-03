"""Experience Cache — remembers what worked so the agent learns from past goals.

When a goal completes successfully, the agent stores:
  - The goal description
  - The sequence of tools that worked (tool_name + args + result summary)
  - The final outcome

When a new goal starts, the agent retrieves similar past experiences
and injects them into the thinking context. This way, if the agent
successfully searched Downloads before, it remembers the exact path
and tool to use next time.

This is the difference between a chatbot and an agent that learns.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GoalExperience:
    """A recorded experience from a completed goal."""
    goal_description: str
    tool_sequence: list[dict[str, Any]]  # [{tool, args, result_summary, success}]
    outcome: str  # final result or error
    success: bool
    timestamp: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)  # extracted keywords

    def to_dict(self) -> dict:
        return {
            "goal": self.goal_description[:100],
            "tools": [t["tool"] for t in self.tool_sequence if t.get("success")],
            "outcome": self.outcome[:100],
            "success": self.success,
        }

    def tool_summary(self) -> str:
        """Human-readable summary of what tools were used successfully."""
        successful = [t for t in self.tool_sequence if t.get("success")]
        if not successful:
            return "No successful steps recorded."
        lines = []
        for t in successful:
            args_str = json.dumps(t.get("args", {}))[:80]
            lines.append(f"  - {t['tool']}({args_str}) → {(t.get('result_summary', '') or '')[:60]}")
        return "\n".join(lines)


class ExperienceCache:
    """In-memory cache of past goal experiences.

    Stores successful goal patterns and retrieves similar ones
    for injection into new goal contexts.
    """

    def __init__(self, max_entries: int = 50):
        self._experiences: list[GoalExperience] = []
        self._max_entries = max_entries

    def record(self, goal_description: str, steps: list[Any], outcome: str, success: bool) -> None:
        """Record a completed goal's experience."""
        tool_sequence = []
        for s in steps:
            if hasattr(s, "tool_name") and s.tool_name:
                tool_sequence.append({
                    "tool": s.tool_name,
                    "args": getattr(s, "tool_args", {}) or {},
                    "result_summary": (getattr(s, "tool_result", None) or "")[:200],
                    "success": getattr(s, "success", False),
                })

        if not tool_sequence:
            return  # nothing useful to remember

        tags = _extract_tags(goal_description)

        exp = GoalExperience(
            goal_description=goal_description,
            tool_sequence=tool_sequence,
            outcome=outcome[:500],
            success=success,
            tags=tags,
        )

        self._experiences.append(exp)

        # Keep bounded
        if len(self._experiences) > self._max_entries:
            self._experiences = self._experiences[-self._max_entries:]

        logger.info(
            "Experience recorded: '%s' → %d tools, success=%s",
            goal_description[:50], len(tool_sequence), success,
        )

    def retrieve(self, goal_description: str, top_k: int = 3) -> list[GoalExperience]:
        """Find past experiences similar to the given goal.

        Uses keyword overlap for matching (fast, no embeddings needed).
        """
        goal_tags = _extract_tags(goal_description)
        if not goal_tags:
            return []

        scored = []
        for exp in self._experiences:
            # Compute tag overlap
            overlap = len(goal_tags & set(exp.tags))
            if overlap > 0:
                # Bonus for successful experiences
                score = overlap + (0.5 if exp.success else 0)
                scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:top_k]]

    def format_for_context(self, goal_description: str) -> str:
        """Retrieve and format past experiences for injection into the agent prompt."""
        experiences = self.retrieve(goal_description)
        if not experiences:
            return ""

        lines = ["PAST EXPERIENCES (similar goals that worked before):"]
        for i, exp in enumerate(experiences, 1):
            lines.append(f"\n{i}. Goal: \"{exp.goal_description[:80]}\"")
            lines.append(f"   Tools used successfully:")
            lines.append(exp.tool_summary())
            lines.append(f"   Outcome: {exp.outcome[:80]}")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        return {
            "total": len(self._experiences),
            "successful": sum(1 for e in self._experiences if e.success),
            "failed": sum(1 for e in self._experiences if not e.success),
        }


def _extract_tags(text: str) -> set[str]:
    """Extract meaningful keywords from text for matching."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "because", "but", "and", "or", "if",
        "while", "about", "against", "up", "down", "find", "list", "get",
        "show", "check", "look", "see", "make", "create", "set", "run",
        "and", "that", "this", "it", "my", "your", "me", "i",
    }
    words = set()
    for word in text.lower().split():
        clean = "".join(c for c in word if c.isalnum())
        if len(clean) > 2 and clean not in stop_words:
            words.add(clean)
    return words


# Singleton
_cache: ExperienceCache | None = None


def get_experience_cache() -> ExperienceCache:
    global _cache
    if _cache is None:
        _cache = ExperienceCache()
    return _cache
