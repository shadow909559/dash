"""Keyboard shortcuts, DND mode, notification sounds, and settings search."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Keyboard Shortcuts ────────────────────────────────────────────────────

_DEFAULT_SHORTCUTS: dict[str, str] = {
    "chat.new": "CommandOrControl+N",
    "chat.search": "CommandOrControl+F",
    "chat.export": "CommandOrControl+E",
    "chat.clear": "CommandOrControl+Shift+Delete",
    "memory.search": "CommandOrControl+M",
    "memory.new": "CommandOrControl+Shift+M",
    "settings.open": "CommandOrControl+,",
    "command_palette": "CommandOrControl+K",
    "toggle_sidebar": "CommandOrControl+B",
    "toggle_dnd": "CommandOrControl+Shift+D",
    "voice.toggle": "CommandOrControl+Shift+V",
    "screenshot": "CommandOrControl+Shift+S",
    "window.minimize": "CommandOrControl+M",
    "window.maximize": "CommandOrControl+Shift+M",
    "window.close": "CommandOrControl+W",
    "find_in_page": "CommandOrControl+H",
    "zoom.in": "CommandOrControl+=",
    "zoom.out": "CommandOrControl+-",
    "zoom.reset": "CommandOrControl+0",
    "focus.next_panel": "CommandOrControl+Tab",
    "focus.prev_panel": "CommandOrControl+Shift+Tab",
    "toggle_compact": "CommandOrControl+Shift+.",
    "undo": "CommandOrControl+Z",
    "redo": "CommandOrControl+Shift+Z",
    "select_all": "CommandOrControl+A",
    "copy": "CommandOrControl+C",
    "paste": "CommandOrControl+V",
    "cut": "CommandOrControl+X",
}


class ShortcutManager:
    """Manages customizable keyboard shortcuts."""

    def __init__(self) -> None:
        self._defaults = dict(_DEFAULT_SHORTCUTS)
        self._custom: dict[str, str] = {}

    def get_all(self) -> list[dict]:
        result = []
        for action, shortcut in self._defaults.items():
            custom = self._custom.get(action)
            result.append({
                "action": action,
                "shortcut": custom or shortcut,
                "default": shortcut,
                "is_custom": action in self._custom,
            })
        return result

    def set_custom(self, action: str, shortcut: str) -> dict:
        if not shortcut:
            return {"ok": False, "reason": "Shortcut cannot be empty"}
        self._custom[action] = shortcut
        return {"ok": True, "action": action, "shortcut": shortcut}

    def reset(self, action: Optional[str] = None) -> dict:
        if action:
            self._custom.pop(action, None)
        else:
            self._custom.clear()
        return {"ok": True}

    def search(self, query: str) -> list[dict]:
        """Search shortcuts by action name."""
        query_lower = query.lower()
        return [s for s in self.get_all() if query_lower in s["action"].lower()]


# ── Do Not Disturb ─────────────────────────────────────────────────────────

class DNDManager:
    """Do Not Disturb mode management."""

    def __init__(self) -> None:
        self._enabled = False
        self._schedule: dict[str, str] = {"start": "22:00", "end": "07:00"}
        self._exceptions: list[str] = []  # actions that bypass DND
        self._history: list[dict] = []

    def get_state(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "enabled": self._enabled,
            "schedule": self._schedule,
            "exceptions": self._exceptions,
            "toggled_at": self._history[-1].get("timestamp") if self._history else None,
        }

    def toggle(self, enabled: Optional[bool] = None) -> dict:
        self._enabled = enabled if enabled is not None else not self._enabled
        self._history.append({
            "enabled": self._enabled,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._history) > 100:
            self._history = self._history[-100:]
        return {"ok": True, "enabled": self._enabled}

    def set_schedule(self, start: str, end: str) -> dict:
        self._schedule = {"start": start, "end": end}
        return {"ok": True, "schedule": self._schedule}

    def add_exception(self, action: str) -> dict:
        if action not in self._exceptions:
            self._exceptions.append(action)
        return {"ok": True}

    def remove_exception(self, action: str) -> dict:
        self._exceptions = [e for e in self._exceptions if e != action]
        return {"ok": True}

    def should_suppress(self, action: str) -> bool:
        if not self._enabled:
            return False
        if action in self._exceptions:
            return False
        return True

    def get_history(self) -> list[dict]:
        return list(self._history)


# ── Notification Sounds ────────────────────────────────────────────────────

class NotificationSounds:
    """Manage notification sound settings."""

    _SOUND_OPTIONS = [
        {"id": "none", "label": "Silent"},
        {"id": "default", "label": "Default"},
        {"id": "chime", "label": "Chime"},
        {"id": "bell", "label": "Bell"},
        {"id": "ding", "label": "Ding"},
        {"id": "pop", "label": "Pop"},
        {"id": "success", "label": "Success"},
        {"id": "warning", "label": "Warning"},
        {"id": "error", "label": "Error"},
    ]

    def __init__(self) -> None:
        self._settings: dict[str, str] = {
            "message": "default",
            "mention": "bell",
            "error": "error",
            "success": "success",
            "warning": "warning",
            "reminder": "chime",
            "agent_complete": "ding",
            "approval": "bell",
        }
        self._volume = 0.7
        self._enabled = True

    def get_settings(self) -> dict:
        return {
            "sounds": self._settings,
            "volume": self._volume,
            "enabled": self._enabled,
            "options": self._SOUND_OPTIONS,
        }

    def set_sound(self, event_type: str, sound_id: str) -> dict:
        valid_ids = {s["id"] for s in self._SOUND_OPTIONS}
        if sound_id not in valid_ids:
            return {"ok": False, "reason": f"Invalid sound: {sound_id}"}
        self._settings[event_type] = sound_id
        return {"ok": True}

    def set_volume(self, volume: float) -> dict:
        self._volume = max(0.0, min(1.0, volume))
        return {"ok": True, "volume": self._volume}

    def toggle(self, enabled: Optional[bool] = None) -> dict:
        self._enabled = enabled if enabled is not None else not self._enabled
        return {"ok": True, "enabled": self._enabled}


# ── Settings Search ────────────────────────────────────────────────────────

_ALL_SETTINGS: list[dict] = [
    {"path": "theme", "label": "Theme", "category": "Appearance", "keywords": "dark light color"},
    {"path": "accent_color", "label": "Accent Color", "category": "Appearance", "keywords": "color green blue"},
    {"path": "font_size", "label": "Font Size", "category": "Appearance", "keywords": "text size zoom"},
    {"path": "font_family", "label": "Font Family", "category": "Appearance", "keywords": "typeface font"},
    {"path": "code_font", "label": "Code Font", "category": "Appearance", "keywords": "monospace coding"},
    {"path": "compact_mode", "label": "Compact Mode", "category": "Appearance", "keywords": "density spacing"},
    {"path": "show_line_numbers", "label": "Line Numbers", "category": "Editor", "keywords": "code editor lines"},
    {"path": "word_wrap", "label": "Word Wrap", "category": "Editor", "keywords": "wrap text"},
    {"path": "tab_size", "label": "Tab Size", "category": "Editor", "keywords": "indent spaces"},
    {"path": "language", "label": "Language", "category": "General", "keywords": "locale i18n"},
    {"path": "notifications", "label": "Notifications", "category": "Notifications", "keywords": "alerts popup"},
    {"path": "sounds", "label": "Notification Sounds", "category": "Notifications", "keywords": "audio beep"},
    {"path": "dnd_enabled", "label": "Do Not Disturb", "category": "Notifications", "keywords": "quiet silence"},
    {"path": "dnd_schedule", "label": "DND Schedule", "category": "Notifications", "keywords": "time hours"},
    {"path": "auto_save", "label": "Auto Save", "category": "General", "keywords": "save backup"},
    {"path": "session_timeout_minutes", "label": "Session Timeout", "category": "Security", "keywords": "timeout lock"},
    {"path": "max_conversation_length", "label": "Max Conversation Length", "category": "Chat", "keywords": "history messages"},
    {"path": "auto_summarize_threshold", "label": "Auto-Summarize Threshold", "category": "Chat", "keywords": "summary"},
    {"path": "backup_enabled", "label": "Backup Enabled", "category": "Data", "keywords": "backup save"},
    {"path": "backup_interval_hours", "label": "Backup Interval", "category": "Data", "keywords": "frequency"},
    {"path": "hotkeys.summon", "label": "Summon DASH", "category": "Shortcuts", "keywords": "global hotkey"},
    {"path": "hotkeys.voice", "label": "Voice Toggle", "category": "Shortcuts", "keywords": "voice mic"},
    {"path": "hotkeys.screenshot", "label": "Screenshot", "category": "Shortcuts", "keywords": "capture screen"},
    {"path": "model.provider", "label": "AI Provider", "category": "AI", "keywords": "llm model openai ollama"},
    {"path": "model.temperature", "label": "Temperature", "category": "AI", "keywords": "creativity randomness"},
    {"path": "model.max_tokens", "label": "Max Tokens", "category": "AI", "keywords": "length output"},
    {"path": "privacy.data_retention", "label": "Data Retention", "category": "Privacy", "keywords": "delete old data"},
    {"path": "privacy.export", "label": "Export Data", "category": "Privacy", "keywords": "download backup"},
    {"path": "privacy.delete", "label": "Delete All Data", "category": "Privacy", "keywords": "remove wipe"},
]


class SettingsSearch:
    """Search through all available settings."""

    @staticmethod
    def search(query: str) -> list[dict]:
        if not query:
            return _ALL_SETTINGS
        q = query.lower()
        return [s for s in _ALL_SETTINGS if q in s["label"].lower() or q in s["category"].lower() or q in s["keywords"]]

    @staticmethod
    def get_categories() -> list[str]:
        return sorted(set(s["category"] for s in _ALL_SETTINGS))

    @staticmethod
    def get_by_category(category: str) -> list[dict]:
        return [s for s in _ALL_SETTINGS if s["category"] == category]


# Singletons
shortcut_manager = ShortcutManager()
dnd_manager = DNDManager()
notification_sounds = NotificationSounds()
settings_search = SettingsSearch()
