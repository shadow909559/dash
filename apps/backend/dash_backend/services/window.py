"""WindowService - list, focus, minimize, maximize, and close windows."""

from __future__ import annotations

import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


class WindowService(Singleton):
    """Manage desktop windows."""

    async def list_windows(self) -> dict[str, Any]:
        """List all visible window titles."""
        if not IS_WINDOWS:
            return {"windows": [], "summary": "Window listing not supported on this platform"}

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            EnumWindows = user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )
            IsWindowVisible = user32.IsWindowVisible
            GetWindowTextLength = user32.GetWindowTextLengthW
            GetWindowText = user32.GetWindowTextW

            windows = []

            def foreach_window(hwnd, lParam):
                if not IsWindowVisible(hwnd):
                    return True
                length = GetWindowTextLength(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                text = buff.value
                if text:
                    windows.append({"hwnd": int(hwnd), "title": text})
                return True

            EnumWindows(EnumWindowsProc(foreach_window), 0)
            return {
                "windows": windows,
                "count": len(windows),
                "summary": f"Found {len(windows)} windows",
            }
        except Exception as exc:
            logger.exception("Failed to list windows")
            raise RuntimeError(f"Failed to list windows: {exc}") from exc

    async def focus(self, title: str) -> dict[str, Any]:
        """Bring a window with matching title to front."""
        if not title:
            raise ValueError("title is required")
        if not IS_WINDOWS:
            return {"summary": "Window focus not supported on this platform"}

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            EnumWindows = user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )
            IsWindowVisible = user32.IsWindowVisible
            GetWindowTextLength = user32.GetWindowTextLengthW
            GetWindowText = user32.GetWindowTextW

            matches = []

            def foreach_window(hwnd, lParam):
                if not IsWindowVisible(hwnd):
                    return True
                length = GetWindowTextLength(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                text = buff.value
                if title.lower() in (text or "").lower():
                    matches.append(hwnd)
                    return False  # stop on first match
                return True

            EnumWindows(EnumWindowsProc(foreach_window), 0)
            if not matches:
                raise RuntimeError(f"No window found matching '{title}'")

            hwnd = matches[0]
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return {"summary": f"Focused window: {title}"}
        except Exception as exc:
            logger.exception("Failed to focus window")
            raise RuntimeError(f"Failed to focus window: {exc}") from exc

    async def minimize(self, title: str) -> dict[str, Any]:
        """Minimize a window with matching title."""
        return await self._apply_window_action(title, "minimize")

    async def maximize(self, title: str) -> dict[str, Any]:
        """Maximize a window with matching title."""
        return await self._apply_window_action(title, "maximize")

    async def close_window(self, title: str) -> dict[str, Any]:
        """Close a window with matching title."""
        return await self._apply_window_action(title, "close")

    async def _apply_window_action(
        self, title: str, action: str
    ) -> dict[str, Any]:
        if not title:
            raise ValueError("title is required")
        if not IS_WINDOWS:
            return {"summary": f"Window {action} not supported on this platform"}

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            EnumWindows = user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )
            IsWindowVisible = user32.IsWindowVisible
            GetWindowTextLength = user32.GetWindowTextLengthW
            GetWindowText = user32.GetWindowTextW

            matches = []

            def foreach_window(hwnd, lParam):
                if not IsWindowVisible(hwnd):
                    return True
                length = GetWindowTextLength(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                text = buff.value
                if title.lower() in (text or "").lower():
                    matches.append(hwnd)
                return True

            EnumWindows(EnumWindowsProc(foreach_window), 0)
            if not matches:
                raise RuntimeError(f"No window found matching '{title}'")

            hwnd = matches[0]
            if action == "minimize":
                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            elif action == "maximize":
                user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
            elif action == "close":
                user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            return {"summary": f"Window {action}: {title}"}
        except Exception as exc:
            logger.exception("Failed to apply window action")
            raise RuntimeError(f"Failed to {action} window: {exc}") from exc
