"""Enhanced remote control tools: browser detection, app search, keyboard hold/release, smooth mouse."""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus
from dash_backend.services.keyboard_enhanced import KeyboardEnhancedService
from dash_backend.services.clipboard_history import get_clipboard_history

logger = get_logger(__name__)
IS_WINDOWS = sys.platform == "win32"


class BrowserDetectionTool(BaseTool):
    name = "detect_browsers"
    description = "Detect installed web browsers on the system."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "browser"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            browsers = []
            candidates = [
                ("Chrome", ["chrome.exe", "google-chrome", "google-chrome-stable"]),
                ("Edge", ["msedge.exe", "microsoft-edge"]),
                ("Firefox", ["firefox.exe", "firefox"]),
                ("Brave", ["brave.exe", "brave-browser"]),
                ("Opera", ["opera.exe", "opera"]),
                ("Vivaldi", ["vivaldi.exe", "vivaldi"]),
                ("Safari", ["safari.exe", "safari"]),
                ("IE", ["iexplore.exe"]),
            ]
            for name, exes in candidates:
                for exe in exes:
                    try:
                        if IS_WINDOWS:
                            result = subprocess.run(
                                ["where", exe], capture_output=True, text=True, timeout=5
                            )
                            if result.returncode == 0 and result.stdout.strip():
                                browsers.append({"name": name, "executable": exe, "path": result.stdout.strip().split("\n")[0]})
                                break
                        else:
                            result = subprocess.run(
                                ["which", exe], capture_output=True, text=True, timeout=5
                            )
                            if result.returncode == 0 and result.stdout.strip():
                                browsers.append({"name": name, "executable": exe, "path": result.stdout.strip()})
                                break
                    except Exception:
                        continue
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"browsers": browsers}, summary=f"Found {len(browsers)} browsers")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ApplicationSearchTool(BaseTool):
    name = "search_applications"
    description = "Search for installed applications by name or keyword."
    parameters = [
        ToolParameter("query", "Search query", required=True),
        ToolParameter("max_results", "Maximum results", type="integer", required=False, default=20),
    ]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").lower()
        max_results = int(kwargs.get("max_results", 20))
        if not query:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="query required")
        try:
            apps = []
            if IS_WINDOWS:
                start_menu = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                if start_menu.exists():
                    for item in start_menu.rglob("*"):
                        if item.suffix.lower() in (".lnk", ".url"):
                            if query in item.stem.lower():
                                apps.append({"name": item.stem, "path": str(item), "type": "shortcut"})
                                if len(apps) >= max_results:
                                    break
                common_dirs = [
                    Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
                    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
                    Path.home() / "AppData" / "Local",
                ]
                for search_dir in common_dirs:
                    if search_dir.exists():
                        for item in search_dir.rglob("*"):
                            if item.suffix.lower() in (".exe", ".lnk", ".url"):
                                if query in item.stem.lower():
                                    apps.append({"name": item.stem, "path": str(item), "type": "application"})
                                    if len(apps) >= max_results:
                                        break
                        if len(apps) >= max_results:
                            break
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"applications": apps}, summary=f"Found {len(apps)} apps matching '{query}'")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SmoothMouseMoveTool(BaseTool):
    name = "smooth_mouse_move"
    description = "Move mouse with smooth animation to coordinates."
    parameters = [
        ToolParameter("x", "Target X coordinate", type="integer", required=True),
        ToolParameter("y", "Target Y coordinate", type="integer", required=True),
        ToolParameter("duration", "Animation duration in seconds", type="number", required=False, default=0.5),
    ]
    permission_level = PermissionLevel.AUTO
    category = "mouse"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            import pyautogui
            x, y = int(kwargs.get("x", 0)), int(kwargs.get("y", 0))
            duration = float(kwargs.get("duration", 0.5))
            pyautogui.moveTo(x, y, duration=duration)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"x": x, "y": y}, summary=f"Smooth mouse to ({x}, {y})")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class KeyboardHoldReleaseTool(BaseTool):
    name = "hold_release_key"
    description = "Hold and then release a keyboard key."
    parameters = [
        ToolParameter("key", "Key to hold/release", required=True),
        ToolParameter("duration_ms", "Hold duration in milliseconds", type="integer", required=False, default=200),
    ]
    permission_level = PermissionLevel.AUTO
    category = "keyboard"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        key = kwargs.get("key")
        duration_ms = int(kwargs.get("duration_ms", 200))
        if not key:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="key required")
        try:
            svc = KeyboardEnhancedService()
            result = await svc.hold_key(key, duration_ms)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class TypeUnicodeTool(BaseTool):
    name = "type_unicode"
    description = "Type Unicode text using clipboard paste method."
    parameters = [
        ToolParameter("text", "Unicode text to type", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "keyboard"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text")
        if not text:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="text required")
        try:
            svc = KeyboardEnhancedService()
            result = await svc.type_unicode(text)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ClipboardHistoryTool(BaseTool):
    name = "clipboard_history"
    description = "Get clipboard history entries."
    parameters = [
        ToolParameter("limit", "Number of entries", type="integer", required=False, default=20),
    ]
    permission_level = PermissionLevel.AUTO
    category = "clipboard"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        limit = int(kwargs.get("limit", 20))
        try:
            svc = get_clipboard_history()
            history = svc.get_history(limit=limit)
            stats = svc.get_stats()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"history": history, "stats": stats}, summary=f"Returned {len(history)} clipboard entries")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ClearClipboardHistoryTool(BaseTool):
    name = "clear_clipboard_history"
    description = "Clear all clipboard history entries."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "clipboard"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            svc = get_clipboard_history()
            svc.clear_history()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Clipboard history cleared")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))
