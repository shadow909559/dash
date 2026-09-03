"""Self-Improvement Engine — DASH learns from its own performance.

Tracks:
- Tool success/failure rates
- Common error patterns
- Which goals succeed vs fail
- Optimal tool selections for goal types

Adapts:
- Agent system prompt based on learned patterns
- Tool selection preferences
- Goal decomposition strategies
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ToolStats:
    """Statistics for a single tool."""
    name: str
    total_calls: int = 0
    successes: int = 0
    failures: int = 0
    avg_duration_ms: float = 0.0
    last_error: str = ""
    common_errors: dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.total_calls, 1)

    @property
    def reliability(self) -> str:
        rate = self.success_rate
        if rate >= 0.9:
            return "high"
        elif rate >= 0.7:
            return "medium"
        else:
            return "low"


@dataclass
class GoalPattern:
    """Pattern learned from goal execution."""
    goal_type: str  # keyword-based classification
    tools_used: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    avg_steps: float = 0.0
    total_goals: int = 0


class SelfImproveEngine:
    """Tracks performance and adapts agent strategy."""

    def __init__(self):
        self._tool_stats: dict[str, ToolStats] = {}
        self._goal_patterns: dict[str, GoalPattern] = {}
        self._recent_errors: list[dict[str, Any]] = []
        self._adaptations: list[str] = []

    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float = 0.0,
        error: str = "",
    ) -> None:
        """Record a tool execution result."""
        if tool_name not in self._tool_stats:
            self._tool_stats[tool_name] = ToolStats(name=tool_name)

        stats = self._tool_stats[tool_name]
        stats.total_calls += 1

        if success:
            stats.successes += 1
        else:
            stats.failures += 1
            stats.last_error = error
            if error:
                short_error = error[:100]
                stats.common_errors[short_error] = stats.common_errors.get(short_error, 0) + 1

        # Running average duration
        n = stats.total_calls
        stats.avg_duration_ms = ((stats.avg_duration_ms * (n - 1)) + duration_ms) / n

    def record_goal_result(
        self,
        goal_description: str,
        tools_used: list[str],
        success: bool,
        steps: int,
    ) -> None:
        """Record a goal execution result."""
        # Classify goal by keywords
        goal_type = self._classify_goal(goal_description)

        if goal_type not in self._goal_patterns:
            self._goal_patterns[goal_type] = GoalPattern(goal_type=goal_type)

        pattern = self._goal_patterns[goal_type]
        pattern.total_goals += 1
        pattern.tools_used = list(set(pattern.tools_used + tools_used))

        # Update success rate (running average)
        n = pattern.total_goals
        pattern.success_rate = ((pattern.success_rate * (n - 1)) + (1.0 if success else 0.0)) / n
        pattern.avg_steps = ((pattern.avg_steps * (n - 1)) + steps) / n

    def get_adapted_prompt(self, base_prompt: str, goal_description: str) -> str:
        """Adapt the agent system prompt based on learned patterns."""
        goal_type = self._classify_goal(goal_description)
        hints = []

        # Add tool reliability hints
        unreliable = [
            name for name, stats in self._tool_stats.items()
            if stats.total_calls >= 3 and stats.success_rate < 0.7
        ]
        if unreliable:
            hints.append(f"AVOID these unreliable tools: {', '.join(unreliable)}")

        # Add goal-specific hints
        if goal_type in self._goal_patterns:
            pattern = self._goal_patterns[goal_type]
            if pattern.tools_used and pattern.success_rate > 0.8:
                hints.append(f"For this type of goal, these tools work well: {', '.join(pattern.tools_used[:3])}")

        # Add error prevention hints
        recent_errors = self._recent_errors[-5:]
        if recent_errors:
            error_tools = set(e.get("tool", "") for e in recent_errors)
            hints.append(f"Recent errors with: {', '.join(error_tools)} — double-check args before calling")

        if hints:
            return f"{base_prompt}\n\nLEARNED HINTS:\n" + "\n".join(f"- {h}" for h in hints)
        return base_prompt

    def get_tool_recommendations(self, goal_description: str) -> list[str]:
        """Recommend tools for a goal based on past patterns."""
        goal_type = self._classify_goal(goal_description)
        if goal_type in self._goal_patterns:
            pattern = self._goal_patterns[goal_type]
            # Sort by reliability
            reliable = [
                t for t in pattern.tools_used
                if t in self._tool_stats and self._tool_stats[t].success_rate >= 0.8
            ]
            return reliable[:5]
        return []

    def get_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return {
            "tool_count": len(self._tool_stats),
            "goal_types": len(self._goal_patterns),
            "total_tool_calls": sum(s.total_calls for s in self._tool_stats.values()),
            "overall_success_rate": (
                sum(s.successes for s in self._tool_stats.values()) /
                max(sum(s.total_calls for s in self._tool_stats.values()), 1)
            ),
            "unreliable_tools": [
                name for name, s in self._tool_stats.items()
                if s.total_calls >= 3 and s.success_rate < 0.7
            ],
            "top_tools": sorted(
                [(name, s.total_calls) for name, s in self._tool_stats.items()],
                key=lambda x: -x[1]
            )[:10],
        }

    @staticmethod
    def _classify_goal(description: str) -> str:
        """Classify a goal by keywords."""
        text = description.lower()
        if any(w in text for w in ("file", "folder", "directory", "organize", "find")):
            return "file_management"
        if any(w in text for w in ("system", "cpu", "ram", "disk", "health")):
            return "system_info"
        if any(w in text for w in ("git", "commit", "branch", "code")):
            return "code_management"
        if any(w in text for w in ("backup", "copy", "move")):
            return "backup"
        if any(w in text for w in ("clean", "remove", "delete")):
            return "cleanup"
        return "general"


# Singleton
_engine: SelfImproveEngine | None = None


def get_self_improve_engine() -> SelfImproveEngine:
    global _engine
    if _engine is None:
        _engine = SelfImproveEngine()
    return _engine
