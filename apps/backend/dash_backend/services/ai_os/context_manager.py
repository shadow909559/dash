"""ContextManager - maintains context between requests.

Knows current project, previous commands, active application,
desktop state, and session memory for persistent awareness.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CommandEntry:
    """A single command executed in the session."""
    command_id: str = ""
    action: str = ""
    category: str = ""
    status: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    result_summary: str = ""


@dataclass
class SessionContext:
    """Full context for a single session."""
    session_id: str = ""
    user_id: str = ""
    started_at: float = 0.0
    last_active_at: float = 0.0
    current_project: str = ""
    current_application: str = ""
    last_command: str = ""
    last_command_result: str = ""
    active_tasks: list[str] = field(default_factory=list)
    recent_files: list[str] = field(default_factory=list)
    recent_commands: list[CommandEntry] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    MAX_RECENT_COMMANDS = 50


class ContextManager:
    """Maintains session context, project awareness, and user preferences.

    Persists context to disk for recovery across restarts.
    """

    def __init__(self, storage_dir: str | None = None) -> None:
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.expanduser("~"), ".dash", "context"
            )
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._sessions: dict[str, SessionContext] = {}
        self._user_preferences: dict[str, dict[str, Any]] = {}
        self._global_state: dict[str, Any] = {
            "current_project": "",
            "current_application": "",
            "last_action": "",
            "last_action_time": 0.0,
        }

    # ── Session Management ───────────────────────────────────

    def get_or_create_session(self, session_id: str, user_id: str = "") -> SessionContext:
        """Get an existing session or create a new one."""
        if session_id not in self._sessions:
            ctx = SessionContext(
                session_id=session_id,
                user_id=user_id,
                started_at=time.time(),
                last_active_at=time.time(),
            )
            self._sessions[session_id] = ctx
            self._persist_session(ctx)
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> SessionContext | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def update_session(self, session_id: str, **kwargs: Any) -> None:
        """Update session fields."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return
        for key, value in kwargs.items():
            if hasattr(ctx, key):
                setattr(ctx, key, value)
        ctx.last_active_at = time.time()
        self._persist_session(ctx)

    # ── Command History ──────────────────────────────────────

    def record_command(self, session_id: str, entry: CommandEntry) -> None:
        """Record a command execution in session history."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return

        ctx.recent_commands.append(entry)
        if len(ctx.recent_commands) > SessionContext.MAX_RECENT_COMMANDS:
            ctx.recent_commands = ctx.recent_commands[
                -SessionContext.MAX_RECENT_COMMANDS:
            ]

        ctx.last_command = entry.action
        ctx.last_command_result = entry.result_summary
        ctx.last_active_at = time.time()

        self._global_state["last_action"] = entry.action
        self._global_state["last_action_time"] = time.time()
        self._persist_session(ctx)

    def get_recent_commands(
        self, session_id: str, limit: int = 10
    ) -> list[CommandEntry]:
        """Get recent commands for a session."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return []
        return ctx.recent_commands[-limit:]

    def get_last_command(self, session_id: str) -> str:
        """Get the last command executed in the session."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return ""
        return ctx.last_command

    # ── Project Awareness ────────────────────────────────────

    def set_current_project(self, session_id: str, project: str) -> None:
        """Set the current working project."""
        if session_id in self._sessions:
            self._sessions[session_id].current_project = project
        self._global_state["current_project"] = project

    def get_current_project(self, session_id: str) -> str:
        """Get the current project for a session."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return self._global_state.get("current_project", "")
        return ctx.current_project or self._global_state.get("current_project", "")

    def set_current_application(self, session_id: str, app: str) -> None:
        """Set the currently active application."""
        if session_id in self._sessions:
            self._sessions[session_id].current_application = app
        self._global_state["current_application"] = app

    def get_current_application(self, session_id: str) -> str:
        """Get the currently active application."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return self._global_state.get("current_application", "")
        return ctx.current_application or self._global_state.get("current_application", "")

    # ── User Preferences ─────────────────────────────────────

    def set_preference(self, user_id: str, key: str, value: Any) -> None:
        """Store a user preference."""
        if user_id not in self._user_preferences:
            self._user_preferences[user_id] = {}
        self._user_preferences[user_id][key] = value
        self._persist_preferences(user_id)

    def get_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        prefs = self._user_preferences.get(user_id, {})
        return prefs.get(key, default)

    def get_all_preferences(self, user_id: str) -> dict[str, Any]:
        """Get all preferences for a user."""
        return self._user_preferences.get(user_id, {})

    # ── Recent Files ─────────────────────────────────────────

    def record_file_access(self, session_id: str, file_path: str) -> None:
        """Record a file access in the session."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return
        if file_path in ctx.recent_files:
            ctx.recent_files.remove(file_path)
        ctx.recent_files.insert(0, file_path)
        ctx.recent_files = ctx.recent_files[:20]  # Keep max 20

    def get_recent_files(self, session_id: str, limit: int = 10) -> list[str]:
        """Get recently accessed files."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return []
        return ctx.recent_files[:limit]

    # ── Global State ─────────────────────────────────────────

    def get_global_state(self) -> dict[str, Any]:
        """Get the global desktop state."""
        return dict(self._global_state)

    def set_global_state(self, key: str, value: Any) -> None:
        """Update global state."""
        self._global_state[key] = value

    # ── Build Context String ─────────────────────────────────

    def build_context_string(self, session_id: str) -> str:
        """Build a human-readable context string for LLM injection."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return "No active session context."

        parts = []

        if ctx.current_project:
            parts.append(f"Current project: {ctx.current_project}")

        if ctx.current_application:
            parts.append(f"Active application: {ctx.current_application}")

        if ctx.last_command:
            parts.append(f"Last command: {ctx.last_action}")

        if ctx.recent_commands:
            last_few = ctx.recent_commands[-5:]
            cmd_strs = [
                f"  - {c.action} ({c.category}) -> {c.status}"
                for c in reversed(last_few)
            ]
            parts.append("Recent commands:\n" + "\n".join(cmd_strs))

        if ctx.recent_files:
            parts.append("Recent files:\n" + "\n".join(f"  - {f}" for f in ctx.recent_files[:5]))

        if not parts:
            return "Session started. No significant context yet."

        return "\n".join(parts)

    # ── Persistence ──────────────────────────────────────────

    def _persist_session(self, ctx: SessionContext) -> None:
        """Save session context to disk."""
        try:
            path = self._storage_dir / f"session_{ctx.session_id}.json"
            data = asdict(ctx)
            data["recent_commands"] = [asdict(c) for c in ctx.recent_commands]
            path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            logger.exception("Failed to persist session %s: %s", ctx.session_id, exc)

    def _persist_preferences(self, user_id: str) -> None:
        """Save user preferences to disk."""
        try:
            path = self._storage_dir / f"prefs_{user_id}.json"
            path.write_text(
                json.dumps(self._user_preferences.get(user_id, {}), indent=2, default=str)
            )
        except Exception as exc:
            logger.exception("Failed to persist preferences for %s: %s", user_id, exc)

    def load_all(self) -> None:
        """Load all persisted sessions and preferences from disk."""
        try:
            for path in self._storage_dir.glob("session_*.json"):
                try:
                    data = json.loads(path.read_text())
                    session_id = data.get("session_id", "")
                    if session_id:
                        commands = [
                            CommandEntry(**c) for c in data.pop("recent_commands", [])
                        ]
                        ctx = SessionContext(**data)
                        ctx.recent_commands = commands
                        self._sessions[session_id] = ctx
                except Exception as exc:
                    logger.warning("Failed to load session %s: %s", path.name, exc)

            for path in self._storage_dir.glob("prefs_*.json"):
                try:
                    user_id = path.stem.replace("prefs_", "")
                    data = json.loads(path.read_text())
                    self._user_preferences[user_id] = data
                except Exception as exc:
                    logger.warning("Failed to load preferences %s: %s", path.name, exc)

            logger.info(
                "Loaded %d sessions and %d user preferences",
                len(self._sessions),
                len(self._user_preferences),
            )
        except Exception as exc:
            logger.exception("Failed to load persisted context: %s", exc)


# Singleton
_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
        _context_manager.load_all()
    return _context_manager
