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
        return await self._apply_window_action(title, "focus")

    async def minimize(self, title: str) -> dict[str, Any]:
        """Minimize a window with matching title."""
        return await self._apply_window_action(title, "minimize")

    async def maximize(self, title: str) -> dict[str, Any]:
        """Maximize a window with matching title."""
        return await self._apply_window_action(title, "maximize")

    async def close_window(self, title: str) -> dict[str, Any]:
        """Close a window with matching title."""
        return await self._apply_window_action(title, "close")

    async def move(self, title: str, x: int, y: int) -> dict[str, Any]:
        """Move a window."""
        return await self._apply_window_action(title, "move", x=x, y=y)

    async def resize(self, title: str, width: int, height: int) -> dict[str, Any]:
        """Resize a window."""
        return await self._apply_window_action(title, "resize", width=width, height=height)

    async def restore(self, title: str) -> dict[str, Any]:
        """Restore a minimized or maximized window to its original size and position."""
        return await self._apply_window_action(title, "restore")

    async def snap(self, title: str, position: str, monitor: int = 0) -> dict[str, Any]:
        """Snap a window to a screen edge on a specific monitor."""
        return await self._apply_window_action(title, "snap", position=position, monitor=monitor)

    async def get_monitors(self) -> dict[str, Any]:
        """Get information about all connected monitors."""
        if not IS_WINDOWS:
            return {"monitors": [], "summary": "Monitor detection not supported on this platform"}

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            
            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)
                ]

            monitors = []
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(MONITORINFO)

            def monitor_enum_proc(hmonitor, hdc, lprc, lparam):
                user32.GetMonitorInfoW(hmonitor, ctypes.byref(monitor_info))
                monitors.append({
                    "index": len(monitors),
                    "left": monitor_info.rcMonitor.left,
                    "top": monitor_info.rcMonitor.top,
                    "right": monitor_info.rcMonitor.right,
                    "bottom": monitor_info.rcMonitor.bottom,
                    "width": monitor_info.rcMonitor.right - monitor_info.rcMonitor.left,
                    "height": monitor_info.rcMonitor.bottom - monitor_info.rcMonitor.top,
                    "work_left": monitor_info.rcWork.left,
                    "work_top": monitor_info.rcWork.top,
                    "work_right": monitor_info.rcWork.right,
                    "work_bottom": monitor_info.rcWork.bottom,
                    "primary": (monitor_info.dwFlags & 1) != 0  # MONITORINFOF_PRIMARY
                })
                return True

            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, wintypes.LPRECT, wintypes.LPARAM
            )
            user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(monitor_enum_proc), 0)
            
            return {
                "monitors": monitors,
                "count": len(monitors),
                "summary": f"Found {len(monitors)} monitors"
            }
        except Exception as exc:
            logger.exception("Failed to get monitors")
            raise RuntimeError(f"Failed to get monitors: {exc}") from exc

    async def arrange(self, arrangement: str = "tile") -> dict[str, Any]:
        """Arrange all windows in a specified layout: tile, cascade, or side-by-side."""
        return await self._apply_window_action(None, "arrange", arrangement=arrangement)

    async def move_to_monitor(self, title: str, monitor_index: int) -> dict[str, Any]:
        """Move a window to a specific monitor."""
        return await self._apply_window_action(title, "move_to_monitor", monitor_index=monitor_index)

    async def get_foreground_window(self) -> dict[str, Any]:
        """Get the current foreground (active) window."""
        if not IS_WINDOWS:
            return {"window": None, "summary": "Foreground detection not supported on this platform"}

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            
            return {
                "window": {
                    "hwnd": int(hwnd),
                    "title": buff.value
                } if hwnd else None,
                "summary": f"Foreground window: {buff.value}" if buff.value else "No foreground window found"
            }
        except Exception as exc:
            logger.exception("Failed to get foreground window")
            raise RuntimeError(f"Failed to get foreground window: {exc}") from exc

    async def cascade(self) -> dict[str, Any]:
        """Cascade all visible windows."""
        return await self._apply_window_action(None, "cascade")

    async def tile(self) -> dict[str, Any]:
        """Tile all visible windows."""
        return await self._apply_window_action(None, "tile")

    async def _apply_window_action(
        self, title: str | None, action: str, **kwargs: Any
    ) -> dict[str, Any]:
        if not IS_WINDOWS:
            return {"summary": f"Window {action} not supported on this platform"}

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            if action in ["cascade", "tile", "arrange"]:
                if action == "cascade" or (action == "arrange" and kwargs.get('arrangement') == "cascade"):
                    user32.CascadeWindows(None, 0, None, 0, None)
                    arrangement = "cascaded"
                elif action == "tile" or (action == "arrange" and kwargs.get('arrangement') == "tile"):
                    user32.TileWindows(None, 0, None, 0, None)
                    arrangement = "tiled"
                elif action == "arrange" and kwargs.get('arrangement') == "side-by-side":
                    # Implement side-by-side arrangement
                    self._arrange_side_by_side()
                    arrangement = "arranged side-by-side"
                else:
                    user32.TileWindows(None, 0, None, 0, None)
                    arrangement = "tiled"
                return {"summary": f"Windows {arrangement}"}

            if not title:
                raise ValueError("title is required for this action")

            hwnd = self._find_window_by_title(title)
            if not hwnd:
                raise RuntimeError(f"No window found matching '{title}'")

            if action == "focus":
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
            elif action == "minimize":
                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            elif action == "maximize":
                user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
            elif action == "restore":
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            elif action == "close":
                user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            elif action == "move":
                user32.SetWindowPos(hwnd, 0, kwargs['x'], kwargs['y'], 0, 0, 0x0001 | 0x0004)
            elif action == "resize":
                user32.SetWindowPos(hwnd, 0, 0, 0, kwargs['width'], kwargs['height'], 0x0002 | 0x0004)
            elif action == "snap":
                if 'monitor' in kwargs:
                    self._snap_window(hwnd, kwargs['position'], kwargs['monitor'])
                else:
                    self._snap_window(hwnd, kwargs['position'])
            elif action == "move_to_monitor":
                self._move_window_to_monitor(hwnd, kwargs['monitor_index'])

            return {"summary": f"Window {action}: {title}"}
        except Exception as exc:
            logger.exception("Failed to apply window action")
            raise RuntimeError(f"Failed to {action} window: {exc}") from exc

    def _find_window_by_title(self, title: str) -> Any | None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        matches = []

        def foreach_window(hwnd, lParam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            text = buff.value
            if title.lower() in (text or "").lower():
                matches.append(hwnd)
            return True

        user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(foreach_window), 0)
        return matches[0] if matches else None

    def _snap_window(self, hwnd: Any, position: str, monitor_index: int = 0) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        
        # Get all monitors first
        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)
            ]

        monitors = []
        monitor_info = MONITORINFO()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFO)

        def monitor_enum_proc(hmonitor, hdc, lprc, lparam):
            user32.GetMonitorInfoW(hmonitor, ctypes.byref(monitor_info))
            monitors.append({
                "left": monitor_info.rcMonitor.left,
                "top": monitor_info.rcMonitor.top,
                "right": monitor_info.rcMonitor.right,
                "bottom": monitor_info.rcMonitor.bottom,
                "width": monitor_info.rcMonitor.right - monitor_info.rcMonitor.left,
                "height": monitor_info.rcMonitor.bottom - monitor_info.rcMonitor.top,
            })
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, wintypes.LPRECT, wintypes.LPARAM
        )
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(monitor_enum_proc), 0)

        # Use requested monitor or fall back to primary if index is invalid
        if monitor_index >= len(monitors):
            monitor_index = 0
        
        monitor = monitors[monitor_index] if monitors else {
            "left": 0, "top": 0, "width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1)
        }

        screen_width = monitor["width"]
        screen_height = monitor["height"]
        offset_x = monitor["left"]
        offset_y = monitor["top"]
        half_w = screen_width // 2
        half_h = screen_height // 2

        snap_positions = {
            "left": (offset_x, offset_y, half_w, screen_height),
            "right": (offset_x + half_w, offset_y, half_w, screen_height),
            "top-left": (offset_x, offset_y, half_w, half_h),
            "top-right": (offset_x + half_w, offset_y, half_w, half_h),
            "bottom-left": (offset_x, offset_y + half_h, half_w, half_h),
            "bottom-right": (offset_x + half_w, offset_y + half_h, half_w, half_h),
            "top": (offset_x, offset_y, screen_width, half_h),
            "bottom": (offset_x, offset_y + half_h, screen_width, half_h),
            "center": (offset_x + screen_width // 4, offset_y + screen_height // 4, screen_width // 2, screen_height // 2),
            "maximize": (offset_x, offset_y, screen_width, screen_height),
            "fullscreen": (offset_x, offset_y, screen_width, screen_height),
        }

        x, y, w, h = snap_positions.get(position, snap_positions["left"])
        user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004)

    def _move_window_to_monitor(self, hwnd: Any, monitor_index: int) -> None:
        """Move a window to the specified monitor and center it."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        
        # Get all monitors
        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)
            ]

        monitors = []
        monitor_info = MONITORINFO()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFO)

        def monitor_enum_proc(hmonitor, hdc, lprc, lparam):
            user32.GetMonitorInfoW(hmonitor, ctypes.byref(monitor_info))
            monitors.append({
                "left": monitor_info.rcMonitor.left,
                "top": monitor_info.rcMonitor.top,
                "right": monitor_info.rcMonitor.right,
                "bottom": monitor_info.rcMonitor.bottom,
                "width": monitor_info.rcMonitor.right - monitor_info.rcMonitor.left,
                "height": monitor_info.rcMonitor.bottom - monitor_info.rcMonitor.top,
            })
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, wintypes.LPRECT, wintypes.LPARAM
        )
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(monitor_enum_proc), 0)

        if monitor_index >= len(monitors):
            monitor_index = 0
        
        monitor = monitors[monitor_index] if monitors else {
            "left": 0, "top": 0, "width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1)
        }

        # Get current window rect
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        window_width = rect.right - rect.left
        window_height = rect.bottom - rect.top

        # Center the window on the target monitor
        new_x = monitor["left"] + (monitor["width"] - window_width) // 2
        new_y = monitor["top"] + (monitor["height"] - window_height) // 2
        
        user32.SetWindowPos(hwnd, 0, new_x, new_y, window_width, window_height, 0x0004)

    def _arrange_side_by_side(self) -> None:
        """Arrange all visible windows side by side on the primary monitor."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        
        # Get all visible windows
        windows = []
        def foreach_window(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                if buff.value:
                    windows.append(hwnd)
            return True

        user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(foreach_window), 0)

        if not windows:
            return

        # Get primary monitor dimensions
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # Calculate window size
        num_windows = len(windows)
        window_width = screen_width // num_windows
        
        # Position each window
        for i, hwnd in enumerate(windows):
            x = i * window_width
            user32.SetWindowPos(hwnd, 0, x, 0, window_width, screen_height, 0x0004)