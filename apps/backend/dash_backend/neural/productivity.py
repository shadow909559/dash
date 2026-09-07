"""Productivity Engine — focus mode, break reminders, and summaries.

Features:
- Focus mode (track focused work sessions)
- Break reminders (after prolonged work)
- Daily summary
- Work summary
- Coding summary
- Research summary
- Project timeline

The engine tracks work sessions and produces natural summaries.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_PRODUCTIVITY = "productivity"
SOURCE_NEURAL_PRODUCTIVITY = "neural_productivity"

# Break reminder threshold (seconds).
BREAK_REMINDER_SECONDS = 3 * 3600  # 3 hours
FOCUS_SESSION_MIN_SECONDS = 25 * 60  # 25 minutes


@dataclass
class WorkSession:
    """A tracked work session."""

    id: str
    started_at: float
    ended_at: Optional[float] = None
    task: str = ""
    category: str = "general"
    duration_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "task": self.task,
            "category": self.category,
            "duration_s": round(self.duration_s, 2),
        }


@dataclass
class ProductivitySummary:
    """A summary of user productivity."""

    total_sessions: int = 0
    total_work_seconds: float = 0.0
    sessions_by_category: Dict[str, int] = field(default_factory=dict)
    longest_session_s: float = 0.0
    average_session_s: float = 0.0
    needs_break: bool = False
    break_after_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "total_work_seconds": round(self.total_work_seconds, 2),
            "sessions_by_category": self.sessions_by_category,
            "longest_session_s": round(self.longest_session_s, 2),
            "average_session_s": round(self.average_session_s, 2),
            "needs_break": self.needs_break,
            "break_after_s": round(self.break_after_s, 2),
        }


class ProductivityEngine:
    """Tracks work sessions and produces productivity summaries."""

    def __init__(self) -> None:
        self._sessions: Dict[str, List[WorkSession]] = {}
        self._active_sessions: Dict[str, WorkSession] = {}
        self._last_activity: Dict[str, float] = {}

    # ── Session tracking ───────────────────────────────────────────────

    def start_session(
        self,
        user_id: str,
        task: str = "",
        category: str = "general",
    ) -> WorkSession:
        """Start a work session for a user."""
        import uuid

        session = WorkSession(
            id=str(uuid.uuid4()),
            started_at=time.time(),
            task=task,
            category=category,
        )
        self._active_sessions[user_id] = session
        self._last_activity[user_id] = time.time()
        return session

    def end_session(self, user_id: str) -> Optional[WorkSession]:
        """End the active work session for a user."""
        session = self._active_sessions.pop(user_id, None)
        if session is None:
            return None
        session.ended_at = time.time()
        session.duration_s = session.ended_at - session.started_at
        self._sessions.setdefault(user_id, []).append(session)
        # Keep last 100 sessions.
        self._sessions[user_id] = self._sessions[user_id][-100:]
        return session

    def register_activity(self, user_id: str) -> None:
        """Register user activity (resets break timer)."""
        self._last_activity[user_id] = time.time()

    def get_active_session(self, user_id: str) -> Optional[WorkSession]:
        """Return the active work session for a user."""
        return self._active_sessions.get(user_id)

    # ── Summaries ──────────────────────────────────────────────────────

    def summary(self, user_id: str, limit: int = 50) -> ProductivitySummary:
        """Produce a productivity summary from recent sessions."""
        sessions = (self._sessions.get(user_id) or [])[-limit:]
        if not sessions:
            return ProductivitySummary()

        total_seconds = sum(s.duration_s for s in sessions)
        categories: Dict[str, int] = {}
        for s in sessions:
            categories[s.category] = categories.get(s.category, 0) + 1

        longest = max(s.duration_s for s in sessions)
        average = total_seconds / len(sessions)

        # Break reminder: if the user has been active continuously for 3h.
        last_activity = self._last_activity.get(user_id, time.time())
        active_seconds = time.time() - last_activity
        needs_break = active_seconds >= BREAK_REMINDER_SECONDS

        return ProductivitySummary(
            total_sessions=len(sessions),
            total_work_seconds=total_seconds,
            sessions_by_category=categories,
            longest_session_s=longest,
            average_session_s=average,
            needs_break=needs_break,
            break_after_s=max(0.0, BREAK_REMINDER_SECONDS - active_seconds),
        )

    def daily_summary(self, user_id: str) -> Dict[str, Any]:
        """Produce a daily summary of work."""
        today_start = time.time() - 86400
        sessions = [
            s for s in (self._sessions.get(user_id) or [])
            if s.started_at >= today_start
        ]
        total = sum(s.duration_s for s in sessions)
        categories: Dict[str, int] = {}
        for s in sessions:
            categories[s.category] = categories.get(s.category, 0) + 1

        return {
            "date": time.strftime("%Y-%m-%d"),
            "sessions": len(sessions),
            "total_work_minutes": round(total / 60, 1),
            "categories": categories,
            "top_category": max(categories, key=categories.get) if categories else "none",
        }

    def coding_summary(self, user_id: str) -> Dict[str, Any]:
        """Produce a coding-focused summary."""
        sessions = [
            s for s in (self._sessions.get(user_id) or [])
            if s.category == "coding"
        ]
        total = sum(s.duration_s for s in sessions)
        return {
            "coding_sessions": len(sessions),
            "total_coding_minutes": round(total / 60, 1),
            "tasks": [s.task for s in sessions[-5:] if s.task],
        }

    def research_summary(self, user_id: str) -> Dict[str, Any]:
        """Produce a research-focused summary."""
        sessions = [
            s for s in (self._sessions.get(user_id) or [])
            if s.category == "research"
        ]
        total = sum(s.duration_s for s in sessions)
        return {
            "research_sessions": len(sessions),
            "total_research_minutes": round(total / 60, 1),
            "topics": [s.task for s in sessions[-5:] if s.task],
        }

    def project_timeline(self, user_id: str, project: str = "") -> List[Dict[str, Any]]:
        """Produce a project timeline from sessions."""
        sessions = self._sessions.get(user_id) or []
        if project:
            sessions = [s for s in sessions if project.lower() in s.task.lower()]
        return [s.to_dict() for s in sessions[-20:]]

    # ── Persistence ────────────────────────────────────────────────────

    async def persist_summary(self, session: Any, user_id: str) -> None:
        """Persist the daily summary as a memory."""
        try:
            from dash_backend.memory import service as memory_service

            summary = self.daily_summary(user_id)
            await memory_service.save_memory(
                session,
                user_id,
                json.dumps(summary, default=str),
                source=SOURCE_NEURAL_PRODUCTIVITY,
                category=CATEGORY_PRODUCTIVITY,
                importance=0.5,
                memory_type="Summary",
                title="Daily productivity summary",
            )
        except Exception:
            logger.exception("Failed to persist productivity summary")


# Global singleton
_productivity_engine: Optional[ProductivityEngine] = None


def get_productivity_engine() -> ProductivityEngine:
    """Return the global ProductivityEngine singleton."""
    global _productivity_engine
    if _productivity_engine is None:
        _productivity_engine = ProductivityEngine()
    return _productivity_engine