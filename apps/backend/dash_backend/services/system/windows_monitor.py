"""Window monitor - open windows, focused window, window details."""

from __future__ import annotations

import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def get_open_windows() -> list[dict[str, Any]]:
    """Return list of open windows with title, size, and monitor info.

    Each entry: title, hwnd, rect (x, y, width, height), monitor_number, is_focused.
    """
    windows: list[dict[str, Any]] = []

    if platform.system() != "Windows":
        return windows

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        # Window enumeration callback
        window_list: list[dict[str, Any]] = []

        def enum_windows_proc(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            title_str = title.value
            if not title_str:
                return True

            # Get window rect
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            # Get monitor info
            monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(monitor_info)
            user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info))

            # Determine monitor number
            monitor_num = 0
            try:
                # Count monitors
                monitor_count = user32.GetSystemMetrics(80)  # SM_CMONITORS
                # Simple heuristic: use work area left position
                monitor_num = monitor_info.rcWork.left // 1920 + 1 if monitor_info.rcWork.left > 0 else 1
            except Exception:
                pass

            # Check if focused
            focused_hwnd = user32.GetForegroundWindow()
            is_focused = hwnd == focused_hwnd

            window_list.append({
                "title": title_str,
                "hwnd": hwnd,
                "x": rect.left,
                "y": rect.top,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top,
                "monitor_number": monitor_num,
                "is_focused": is_focused,
            })
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        proc = WNDENUMPROC(enum_windows_proc)
        user32.EnumWindows(proc, 0)

        windows = window_list

    except Exception:
        logger.exception("Failed to enumerate windows")

    return windows


def get_focused_window() -> dict[str, Any] | None:
    """Return the currently focused window details."""
    windows = get_open_windows()
    for w in windows:
        if w.get("is_focused"):
            return w
    return None