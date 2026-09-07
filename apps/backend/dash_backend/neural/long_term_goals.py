"""Long-Term Goals Engine — tracks goals and monitors progress automatically.

Examples:
- Build DASH.
- Get internship.
- Finish project.
- Prepare interview.

Goals are stored as memories (category ``goal``) with a JSON payload that
includes status, milestones, and progress metrics. The engine updates progress
heuristically when relevant user activity is observed.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_GOAL = "goal"
SOURCE_NEURAL_GOALS = "neural_long_term_goals"

# If a user mentions the goal name, we bump the progress signal.
_PROGRESS_SIGNAL_KEYWORDS = [
    "done", "finished", "completed", "progress", "working on",
    "started", "updated", "resumed", "practicing", "preparing",
]


@dataclass
class TrackedGoal:
    """A long-term goal tracked by DASH."""

    name: str
    description: str = ""
    status: str = "active"  # active | paused | completed | abandoned
    priority: str = "important"
    milestones: List[str] = field(default_factory=list)
    completed_milestones: List[str] = field(default_factory=list)
    progress: float = 0.0  # 0.0 - 1.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    relevant_domains: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "milestones": self.milestones,
            "completed_milestones": self.completed_milestones,
            "progress": round(self.progress, 3),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "relevant_domains": self.relevant_domains,
        }


@dataclass
class GoalProgress:
    """A progress update result for a goal."""

    goal: TrackedGoal
    delta: float = 0.0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal.to_dict(),
            "delta": round(self.delta, 3),
            "message": self.message,
        }


class LongTermGoalsEngine:
    """Tracks long-term goals and monitors their progress automatically."""

    def __init__(self) -> None:
        self._goals: Dict[str, Dict[str, TrackedGoal]] = {}

    # ── Goal management ────────────────────────────────────────────────

    def add_goal(
        self,
        user_id: str,
        name: str,
        description: str = "",
        *,
        milestones: Optional[List[str]] = None,
        priority: str = "important",
        domains: Optional[List[str]] = None,
    ) -> TrackedGoal:
        """Add a new long-term goal for a user."""
        goal = TrackedGoal(
            name=name,
            description=description,
            priority=priority,
            milestones=milestones or [],
            relevant_domains=domains or [],
        )
        user_goals = self._goals.setdefault(user_id, {})
        user_goals[name.lower()] = goal
        logger.info("Added long-term goal '%s' for user %s", name, user_id)
        return goal

    def get_goals(self, user_id: str, *, include_completed: bool = False) -> List[TrackedGoal]:
        """Return the tracked goals for a user."""
        goals = list((self._goals.get(user_id) or {}).values())
        if not include_completed:
            goals = [g for g in goals if g.status != "completed"]
        return sorted(goals, key=lambda g: g.created_at)

    def get_goal(self, user_id: str, name: str) -> Optional[TrackedGoal]:
        """Return a single tracked goal by name."""
        return (self._goals.get(user_id) or {}).get(name.lower())

    def update_goal_status(
        self,
        user_id: str,
        name: str,
        status: str,
    ) -> Optional[TrackedGoal]:
        """Update a goal's status (active, paused, completed, abandoned)."""
        goal = self.get_goal(user_id, name)
        if goal is None:
            return None
        goal.status = status
        goal.updated_at = time.time()
        if status == "completed":
            goal.progress = 1.0
            goal.completed_milestones = list(goal.milestones)
        return goal

    def complete_milestone(
        self,
        user_id: str,
        name: str,
        milestone: str,
    ) -> Optional[GoalProgress]:
        """Mark a milestone as completed and update goal progress."""
        goal = self.get_goal(user_id, name)
        if goal is None:
            return None

        if milestone not in goal.milestones:
            return GoalProgress(goal=goal, delta=0.0, message="Milestone not in goal.")

        if milestone not in goal.completed_milestones:
            goal.completed_milestones.append(milestone)

        total = len(goal.milestones)
        completed = len(goal.completed_milestones)
        new_progress = completed / total if total > 0 else 0.0
        delta = new_progress - goal.progress
        goal.progress = new_progress
        goal.updated_at = time.time()

        if new_progress >= 1.0:
            goal.status = "completed"
            message = "All milestones complete. Goal achieved."
        else:
            message = f"Milestone '{milestone}' completed ({completed}/{total})."

        return GoalProgress(goal=goal, delta=delta, message=message)

    # ── Automatic monitoring ───────────────────────────────────────────

    def observe_activity(self, user_id: str, activity: str) -> Optional[GoalProgress]:
        """Monitor user activity and auto-update goal progress.

        When the user mentions a tracked goal (or its description) along with a
        progress verb, we bump the goal's progress signal. This never makes the
        goal jump to completion — the bump is small and the user can correct it.
        """
        activity_lower = (activity or "").lower()
        if len(activity_lower.split()) < 3:
            return None

        best_goal: Optional[TrackedGoal] = None
        best_score = 0.0
        for goal in self.get_goals(user_id):
            score = 0.0
            if goal.name.lower() in activity_lower:
                score += 1.0
            for word in (goal.description or "").lower().split():
                if len(word) > 3 and word in activity_lower:
                    score += 0.3
            if score > best_score:
                best_score = score
                best_goal = goal

        if best_goal is None or best_score < 0.8:
            return None

        if not any(kw in activity_lower for kw in _PROGRESS_SIGNAL_KEYWORDS):
            return None

        old_progress = best_goal.progress
        best_goal.progress = min(0.95, old_progress + 0.05)
        best_goal.updated_at = time.time()
        return GoalProgress(
            goal=best_goal,
            delta=best_goal.progress - old_progress,
            message=f"Detected activity related to '{best_goal.name}'. Progress signal updated.",
        )

    # ── Persistence (additive memory writes) ───────────────────────────

    async def persist_goals(
        self,
        session: Any,
        user_id: str,
    ) -> None:
        """Persist all active goals as memories (category ``goal``)."""
        try:
            from dash_backend.memory import service as memory_service

            goals = self.get_goals(user_id, include_completed=False)
            for goal in goals:
                await memory_service.save_memory(
                    session,
                    user_id,
                    json.dumps(goal.to_dict(), default=str),
                    source=SOURCE_NEURAL_GOALS,
                    category=CATEGORY_GOAL,
                    importance=0.85,
                    memory_type="Goal",
                    title=f"Long-term goal: {goal.name}",
                )
        except Exception:
            logger.exception("Failed to persist long-term goals")

    async def load_goals(
        self,
        session: Any,
        user_id: str,
    ) -> int:
        """Load previously persisted goals from memory."""
        try:
            from dash_backend.memory import service as memory_service

            memories, _ = await memory_service.get_user_memories(
                session,
                user_id,
                limit=100,
                category=CATEGORY_GOAL,
            )
            count = 0
            for m in memories:
                if m.source != SOURCE_NEURAL_GOALS:
                    continue
                try:
                    data = json.loads(m.content)
                    goal = self.add_goal(
                        user_id,
                        data.get("name", ""),
                        description=data.get("description", ""),
                        milestones=data.get("milestones") or [],
                        priority=data.get("priority", "important"),
                        domains=data.get("relevant_domains") or [],
                    )
                    goal.status = data.get("status", "active")
                    goal.progress = float(data.get("progress", 0.0))
                    goal.completed_milestones = data.get("completed_milestones") or []
                    goal.created_at = float(data.get("created_at", time.time()))
                    goal.updated_at = float(data.get("updated_at", time.time()))
                    count += 1
                except Exception:
                    continue
            return count
        except Exception:
            logger.exception("Failed to load long-term goals")
            return 0


# Global singleton
_long_term_goals_engine: Optional[LongTermGoalsEngine] = None


def get_long_term_goals_engine() -> LongTermGoalsEngine:
    """Return the global LongTermGoalsEngine singleton."""
    global _long_term_goals_engine
    if _long_term_goals_engine is None:
        _long_term_goals_engine = LongTermGoalsEngine()
    return _long_term_goals_engine