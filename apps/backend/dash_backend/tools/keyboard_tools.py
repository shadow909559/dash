"""Keyboard tools - shortcuts, clipboard paste, unicode typing.

Complements the base keyboard Service with additional keyboard-related tools.
"""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


class ClipboardPasteTool(BaseTool):
    name = "clipboard_paste"
    description = "Paste clipboard content at the current cursor position using Ctrl+V."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "keyboard"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "v")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Pasted clipboard content")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class PressShortcutTool(BaseTool):
    name = "press_shortcut"
    description = "Press a preset keyboard shortcut by name. Examples: copy, paste, cut, save, select-all, undo, redo, find, print, close-tab, new-tab, switch-window, lock-screen, screenshot, task-manager, run."
    parameters = [
        ToolParameter("shortcut", "Preset shortcut name", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "keyboard"

    _SHORTCUTS = {
        "copy": ["ctrl", "c"],
        "paste": ["ctrl", "v"],
        "cut": ["ctrl", "x"],
        "save": ["ctrl", "s"],
        "select-all": ["ctrl", "a"],
        "undo": ["ctrl", "z"],
        "redo": ["ctrl", "y"],
        "find": ["ctrl", "f"],
        "print": ["ctrl", "p"],
        "close-tab": ["ctrl", "w"],
        "new-tab": ["ctrl", "t"],
        "switch-window": ["alt", "tab"],
        "lock-screen": ["win", "l"],
        "screenshot": ["win", "shift", "s"],
        "task-manager": ["ctrl", "shift", "esc"],
        "run": ["win", "r"],
        "file-explorer": ["win", "e"],
        "search": ["win", "s"],
        "settings": ["win", "i"],
        "minimize-all": ["win", "d"],
        "virtual-desktop-left": ["ctrl", "win", "left"],
        "virtual-desktop-right": ["ctrl", "win", "right"],
    }

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        shortcut = kwargs.get("shortcut", "").lower().strip()
        if not shortcut:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="shortcut name required")
        keys = self._SHORTCUTS.get(shortcut)
        if not keys:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Unknown shortcut: '{shortcut}'. Available: {', '.join(sorted(self._SHORTCUTS.keys()))}")
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Pressed shortcut: {shortcut}")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class TypeUnicodeTool(BaseTool):
    name = "type_unicode"
    description = "Type Unicode text using clipboard paste for reliable character input."
    parameters = [
        ToolParameter("text", "Unicode text to type", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "keyboard"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text", "")
        if not text:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="text is required")
        try:
            import pyperclip
            import pyautogui
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Typed {len(text)} characters via Unicode paste")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyperclip and pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))

