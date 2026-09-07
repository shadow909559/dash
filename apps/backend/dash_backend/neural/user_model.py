"""User Model Engine — continuously learns the user's habits, tools, and patterns.

Tracks:
- Work habits (active hours, task cadence)
- Sleep habits (inferred from idle/first-activity times)
- Coding habits (language stack, edit frequency)
- Favorite tools and frequently used commands
- Most opened folders
- Frequently contacted people (via companion/phone events)

Persistence is additive — observations are written as memories using the
existing ``memories`` table with the ``neural`` category family so no new
persistent tables are required.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Memory categories used by the user-model layer.
CATEGORY_USER_MODEL = "user_model"
CATEGORY_USER_HABITS = "user_habits"
CATEGORY_USER_PATTERNS = "user_patterns"
CATEGORY_USER_CONTACTS = "user_contacts"

# Maximum number of observations kept per bucket before rotation.
_MAX_OBSERVATIONS = 200


@dataclass
class FrequentCommand:
    """A frequently issued command/tool invocation."""

    command: str
    count: int = 1
    last_used: float = 0.0
    domains: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "count": self.count,
            "last_used": self.last_used,
            "domains": self.domains,
        }


@dataclass
class UserHabits:
    """Aggregated habit profile for a user."""

    typical_start_hour: Optional[int] = None
    typical_end_hour: Optional[int] = None
    active_hours: List[int] = field(default_factory=list)
    sleep_window: Optional[Dict[str, Any]] = None
    coding_languages: List[str] = field(default_factory=list)
    favorite_tools: List[str] = field(default_factory=list)
    frequent_commands: List[FrequentCommand] = field(default_factory=list)
    most_opened_folders: List[str] = field(default_factory=list)
    frequently_contacted: List[str] = field(default_factory=list)
    observations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "typical_start_hour": self.typical_start_hour,
            "typical_end_hour": self.typical_end_hour,
            "active_hours": self.active_hours,
            "sleep_window": self.sleep_window,
            "coding_languages": self.coding_languages,
            "favorite_tools": self.favorite_tools,
            "frequent_commands": [c.to_dict() for c in self.frequent_commands],
            "most_opened_folders": self.most_opened_folders,
            "frequently_contacted": self.frequently_contacted,
            "observations": self.observations,
        }


class UserModelEngine:
    """Tracks user observations and builds a durable habit profile.

    Observations are intentionally best-effort: the engine never crashes the
    pipeline when a system metric (e.g. `psutil`) is unavailable.
    """

    def __init__(self) -> None:
        self._habits: Dict[str, UserHabits] = {}
        self._events: List[Dict[str, Any]] = []

    # ── Observation ingestion ──────────────────────────────────────────

    def observe(
        self,
        user_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a single observation about a user."""
        try:
            payload = payload or {}
            event = {
                "user_id": user_id,
                "event_type": event_type,
                "payload": payload,
                "ts": time.time(),
            }
            self._events.append(event)
            # Rotate in-memory events.
            if len(self._events) > _MAX_OBSERVATIONS:
                self._events = self._events[-_MAX_OBSERVATIONS:]

            habits = self._habits.setdefault(user_id, UserHabits())
            habits.observations += 1

            if event_type == "command":
                self._observe_command(user_id, payload)
            elif event_type == "activity":
                self._observe_activity(user_id, payload)
            elif event_type == "folder":
                self._observe_folder(user_id, payload)
            elif event_type == "contact":
                self._observe_contact(user_id, payload)
            elif event_type == "coding":
                self._observe_coding(user_id, payload)
            elif event_type == "tool":
                self._observe_tool(user_id, payload)
        except Exception:
            logger.exception("UserModelEngine.observe failed")

    def _observe_command(self, user_id: str, payload: Dict[str, Any]) -> None:
        cmd = str(payload.get("command") or payload.get("text") or "").strip().lower()
        if not cmd:
            return
        habits = self._habits[user_id]
        now = time.time()
        for freq in habits.frequent_commands:
            if freq.command == cmd:
                freq.count += 1
                freq.last_used = now
                dom = payload.get("domains") or []
                for d in dom:
                    if d not in freq.domains:
                        freq.domains.append(d)
                break
        else:
            habits.frequent_commands.append(
                FrequentCommand(
                    command=cmd,
                    count=1,
                    last_used=now,
                    domains=payload.get("domains") or [],
                )
            )
        # Keep top 25 by usage.
        habits.frequent_commands.sort(key=lambda c: c.count, reverse=True)
        habits.frequent_commands = habits.frequent_commands[:25]

    def _observe_activity(self, user_id: str, payload: Dict[str, Any]) -> None:
        habits = self._habits[user_id]
        hour = self._extract_hour(payload)
        if hour is not None and hour not in habits.active_hours:
            habits.active_hours.append(hour)
            habits.active_hours.sort()

        start = payload.get("start_hour")
        end = payload.get("end_hour")
        if isinstance(start, int) and 0 <= start <= 23:
            habits.typical_start_hour = start
        if isinstance(end, int) and 0 <= end <= 23:
            habits.typical_end_hour = end

        # Infer a sleep window if the user is inactive overnight.
        if payload.get("sleep"):
            habits.sleep_window = {
                "start": payload.get("sleep_start") or 23,
                "end": payload.get("sleep_end") or 7,
                "inferred": True,
            }

    def _observe_folder(self, user_id: str, payload: Dict[str, Any]) -> None:
        folder = str(payload.get("folder") or payload.get("path") or "").strip()
        if not folder:
            return
        habits = self._habits[user_id]
        if folder not in habits.most_opened_folders:
            habits.most_opened_folders.append(folder)
        # Keep most-recently-opened order, most recent first.
        habits.most_opened_folders.remove(folder)
        habits.most_opened_folders.insert(0, folder)
        habits.most_opened_folders = habits.most_opened_folders[:15]

    def _observe_contact(self, user_id: str, payload: Dict[str, Any]) -> None:
        name = str(payload.get("name") or payload.get("contact") or "").strip()
        if not name:
            return
        habits = self._habits[user_id]
        if name not in habits.frequently_contacted:
            habits.frequently_contacted.append(name)
            habits.frequently_contacted = habits.frequently_contacted[:20]

    def _observe_coding(self, user_id: str, payload: Dict[str, Any]) -> None:
        habits = self._habits[user_id]
        langs = payload.get("languages") or []
        for lang in langs:
            lang = str(lang).strip()
            if lang and lang not in habits.coding_languages:
                habits.coding_languages.append(lang)
                habits.coding_languages = habits.coding_languages[:10]

    def _observe_tool(self, user_id: str, payload: Dict[str, Any]) -> None:
        tool = str(payload.get("tool") or payload.get("name") or "").strip()
        if not tool:
            return
        habits = self._habits[user_id]
        if tool not in habits.favorite_tools:
            habits.favorite_tools.append(tool)
            habits.favorite_tools = habits.favorite_tools[:10]

    # ── Public accessors ───────────────────────────────────────────────

    def get_habits(self, user_id: str) -> UserHabits:
        """Return the in-memory habit profile for a user."""
        return self._habits.setdefault(user_id, UserHabits())

    def predict_next_action(self, user_id: str) -> Optional[str]:
        """Heuristically predict the user's likely next action.

        Uses the most frequent command as the base prediction, refined by
        time-of-day activity when available.
        """
        habits = self._habits.get(user_id)
        if not habits or not habits.frequent_commands:
            return None
        return habits.frequent_commands[0].command

    def recent_events(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent observations for a user."""
        filtered = [e for e in self._events if e.get("user_id") == user_id]
        return filtered[-limit:]

    # ── Persistence helpers (additive memory writes) ───────────────────

    async def persist_snapshot(
        self,
        session: Any,
        user_id: str,
    ) -> None:
        """Persist the current habit profile as a memory snapshot.

        Uses the existing ``memories`` table with ``category='user_habits'``.
        """
        try:
            from dash_backend.memory import service as memory_service

            habits = self.get_habits(user_id)
            snapshot = json.dumps(habits.to_dict(), default=str)
            await memory_service.save_memory(
                session,
                user_id,
                snapshot,
                source="neural_user_model",
                category=CATEGORY_USER_HABITS,
                importance=0.7,
                memory_type="Preference",
                title="User habit profile snapshot",
            )
        except Exception:
            logger.exception("Failed to persist user-model snapshot")

    @staticmethod
    def _extract_hour(payload: Dict[str, Any]) -> Optional[int]:
        """Extract an hour-of-day from an activity payload."""
        hour = payload.get("hour")
        if isinstance(hour, int) and 0 <= hour <= 23:
            return hour
        ts = payload.get("ts")
        if ts:
            try:
                return datetime.fromtimestamp(float(ts), tz=UTC).hour
            except Exception:
                pass
        now_s = payload.get("time")
        if now_s:
            try:
                return datetime.fromtimestamp(float(now_s), tz=UTC).hour
            except Exception:
                pass
        return None


# Global singleton
_user_model_engine: Optional[UserModelEngine] = None


def get_user_model_engine() -> UserModelEngine:
    """Return the global UserModelEngine singleton."""
    global _user_model_engine
    if _user_model_engine is None:
        _user_model_engine = UserModelEngine()
    return _user_model_engine