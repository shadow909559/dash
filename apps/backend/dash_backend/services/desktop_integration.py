"""Global hotkey, tray actions, and desktop integration service."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Hotkey Registry ────────────────────────────────────────────────────────

_DEFAULT_HOTKEYS: dict[str, str] = {
    "summon": "CommandOrControl+Shift+Space",
    "quick_chat": "CommandOrControl+Shift+C",
    "voice_toggle": "CommandOrControl+Shift+V",
    "screenshot": "CommandOrControl+Shift+S",
    "clipboard": "CommandOrControl+Shift+X",
    "new_task": "CommandOrControl+Shift+N",
}


class HotkeyRegistry:
    """Manages global keyboard shortcuts for DASH."""

    def __init__(self) -> None:
        self._hotkeys: dict[str, str] = dict(_DEFAULT_HOTKEYS)
        self._custom: dict[str, str] = {}
        self._bindings: list[dict] = []

    def get_all(self) -> dict[str, str]:
        """Return all registered hotkeys."""
        merged = {**self._hotkeys, **self._custom}
        return merged

    def register(self, action: str, shortcut: str) -> dict:
        """Register a custom hotkey for an action."""
        if not shortcut or len(shortcut) < 3:
            return {"ok": False, "reason": "Shortcut too short"}
        self._custom[action] = shortcut
        self._bindings.append({
            "action": action,
            "shortcut": shortcut,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Hotkey registered: %s → %s", action, shortcut)
        return {"ok": True, "action": action, "shortcut": shortcut}

    def unregister(self, action: str) -> dict:
        """Remove a custom hotkey."""
        if action in self._custom:
            del self._custom[action]
            self._bindings = [b for b in self._bindings if b["action"] != action]
            return {"ok": True}
        if action in self._hotkeys:
            return {"ok": False, "reason": "Cannot unregister default hotkey"}
        return {"ok": False, "reason": "Hotkey not found"}

    def get_bindings(self) -> list[dict]:
        """Return all active bindings."""
        result = []
        for action, shortcut in self._hotkeys.items():
            result.append({"action": action, "shortcut": shortcut, "is_default": True})
        for action, shortcut in self._custom.items():
            result.append({"action": action, "shortcut": shortcut, "is_default": False})
        return result


# ── Quick Action ───────────────────────────────────────────────────────────

_DEFAULT_ACTIONS: list[dict] = [
    {"id": "new_chat", "label": "New Chat", "icon": "message-square", "shortcut": "CommandOrControl+Shift+C"},
    {"id": "voice", "label": "Voice Mode", "icon": "mic", "shortcut": "CommandOrControl+Shift+V"},
    {"id": "screenshot", "label": "Screenshot", "icon": "camera", "shortcut": "CommandOrControl+Shift+S"},
    {"id": "memory", "label": "Search Memory", "icon": "brain", "shortcut": "CommandOrControl+Shift+M"},
    {"id": "tasks", "label": "New Task", "icon": "check-square", "shortcut": "CommandOrControl+Shift+N"},
    {"id": "settings", "label": "Settings", "icon": "settings", "shortcut": "CommandOrControl+,"},
    {"id": "minimize", "label": "Minimize to Tray", "icon": "minus"},
    {"id": "quit", "label": "Quit DASH", "icon": "x"},
]


class TrayActions:
    """Manages system tray quick actions."""

    def __init__(self) -> None:
        self._actions = list(_DEFAULT_ACTIONS)
        self._recent: list[dict] = []

    def get_actions(self) -> list[dict]:
        return self._actions

    def get_recent(self, limit: int = 5) -> list[dict]:
        return self._recent[-limit:]

    def record_action(self, action_id: str) -> None:
        self._recent.append({
            "action": action_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._recent) > 50:
            self._recent = self._recent[-50:]

    def add_custom_action(self, label: str, icon: str, callback_type: str) -> dict:
        action = {
            "id": f"custom_{len(self._actions)}",
            "label": label,
            "icon": icon,
            "callback": callback_type,
            "is_custom": True,
        }
        self._actions.append(action)
        return {"ok": True, "action": action}

    def remove_custom_action(self, action_id: str) -> dict:
        self._actions = [a for a in self._actions if a.get("id") != action_id or not a.get("is_custom")]
        return {"ok": True}


# ── Window Snap ────────────────────────────────────────────────────────────

class WindowSnap:
    """Manages window snapping positions."""

    @staticmethod
    def get_snap_positions(screen_width: int, screen_height: int) -> dict[str, dict]:
        return {
            "left_half": {"x": 0, "y": 0, "w": screen_width // 2, "h": screen_height},
            "right_half": {"x": screen_width // 2, "y": 0, "w": screen_width // 2, "h": screen_height},
            "top_half": {"x": 0, "y": 0, "w": screen_width, "h": screen_height // 2},
            "bottom_half": {"x": 0, "y": screen_height // 2, "w": screen_width, "h": screen_height // 2},
            "top_left": {"x": 0, "y": 0, "w": screen_width // 2, "h": screen_height // 2},
            "top_right": {"x": screen_width // 2, "y": 0, "w": screen_width // 2, "h": screen_height // 2},
            "bottom_left": {"x": 0, "y": screen_height // 2, "w": screen_width // 2, "h": screen_height // 2},
            "bottom_right": {"x": screen_width // 2, "y": screen_height // 2, "w": screen_width // 2, "h": screen_height // 2},
            "center": {
                "x": screen_width // 4,
                "y": screen_height // 4,
                "w": screen_width // 2,
                "h": screen_height // 2,
            },
            "third_left": {"x": 0, "y": 0, "w": screen_width // 3, "h": screen_height},
            "third_center": {"x": screen_width // 3, "y": 0, "w": screen_width // 3, "h": screen_height},
            "third_right": {"x": (screen_width * 2) // 3, "y": 0, "w": screen_width // 3, "h": screen_height},
        }

    @staticmethod
    def calculate_snap(drag_x: int, drag_y: int, screen_width: int, screen_height: int) -> Optional[str]:
        """Determine snap position from drag coordinates."""
        edge = 30  # pixels from edge
        if drag_x <= edge and drag_y <= edge:
            return "top_left"
        if drag_x >= screen_width - edge and drag_y <= edge:
            return "top_right"
        if drag_x <= edge and drag_y >= screen_height - edge:
            return "bottom_left"
        if drag_x >= screen_width - edge and drag_y >= screen_height - edge:
            return "bottom_right"
        if drag_x <= edge:
            return "left_half"
        if drag_x >= screen_width - edge:
            return "right_half"
        if drag_y <= edge:
            return "top_half"
        if drag_y >= screen_height - edge:
            return "bottom_half"
        return None


# Singleton instances
hotkey_registry = HotkeyRegistry()
tray_actions = TrayActions()
window_snap = WindowSnap()
