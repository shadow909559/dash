"""Enhanced window management tools - restore, move, resize, snap, multi-monitor, active window detection."""

from __future__ import annotations

import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)
IS_WINDOWS = sys.platform == "win32"


def _find_window(title: str) -> int | None:
    """Find a window handle by title substring."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    IsWindowVisible = user32.IsWindowVisible
    GetWindowTextLength = user32.GetWindowTextLengthW
    GetWindowText = user32.GetWindowTextW

    matches: list[int] = []

    def foreach_window(hwnd, lParam):
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLength(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        text = buff.value
        if title.lower() in (text or "").lower():
            matches.append(hwnd)
            return False
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)
    return matches[0] if matches else None


class RestoreWindowTool(BaseTool):
    name = "restore_window"
    description = "Restore a minimized or maximized window to its normal size."
    parameters = [ToolParameter("title", "Window title or substring to match", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "window"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title")
        if not title:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="title required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = _find_window(title)
            if hwnd is None:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Window '{title}' not found")
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Restored window: {title}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MoveWindowTool(BaseTool):
    name = "move_window"
    description = "Move a window to a specific screen position."
    parameters = [
        ToolParameter("title", "Window title or substring to match", required=True),
        ToolParameter("x", "Target X coordinate", type="integer", required=True),
        ToolParameter("y", "Target Y coordinate", type="integer", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "window"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title")
        x = int(kwargs.get("x", 0))
        y = int(kwargs.get("y", 0))
        if not title:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="title required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = _find_window(title)
            if hwnd is None:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Window '{title}' not found")
            user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Moved window to ({x}, {y})")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ResizeWindowTool(BaseTool):
    name = "resize_window"
    description = "Resize a window to specific dimensions."
    parameters = [
        ToolParameter("title", "Window title or substring to match", required=True),
        ToolParameter("width", "New width in pixels", type="integer", required=True),
        ToolParameter("height", "New height in pixels", type="integer", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "window"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title")
        width = int(kwargs.get("width", 800))
        height = int(kwargs.get("height", 600))
        if not title:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="title required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = _find_window(title)
            if hwnd is None:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Window '{title}' not found")
            user32.SetWindowPos(hwnd, 0, 0, 0, width, height, 0x0002 | 0x0004)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Resized window to {width}x{height}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SnapWindowTool(BaseTool):
    name = "snap_window"
    description = "Snap a window to a screen region (left, right, top-left, etc.)."
    parameters = [
        ToolParameter("title", "Window title or substring to match", required=True),
        ToolParameter("position", "Snap position", required=True,
                      enum=["left", "right", "top-left", "top-right", "bottom-left", "bottom-right", "top", "bottom", "center", "maximize"]),
    ]
    permission_level = PermissionLevel.AUTO
    category = "window"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title")
        position = kwargs.get("position", "left")
        if not title:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="title required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = _find_window(title)
            if hwnd is None:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Window '{title}' not found")

            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            half_w = screen_width // 2
            half_h = screen_height // 2

            snap_positions = {
                "left": (0, 0, half_w, screen_height),
                "right": (half_w, 0, half_w, screen_height),
                "top-left": (0, 0, half_w, half_h),
                "top-right": (half_w, 0, half_w, half_h),
                "bottom-left": (0, half_h, half_w, half_h),
                "bottom-right": (half_w, half_h, half_w, half_h),
                "top": (0, 0, screen_width, half_h),
                "bottom": (0, half_h, screen_width, half_h),
                "center": (screen_width // 4, screen_height // 4, screen_width // 2, screen_height // 2),
                "maximize": (0, 0, screen_width, screen_height),
            }

            x, y, w, h = snap_positions.get(position, snap_positions["left"])
            user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Snapped window to {position}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class DetectActiveWindowTool(BaseTool):
    name = "detect_active_window"
    description = "Detect the currently active (foreground) window."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "window"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                "hwnd": int(hwnd),
                "title": title or "Unknown",
                "rect": {
                    "left": rect.left, "top": rect.top,
                    "right": rect.right, "bottom": rect.bottom,
                    "width": rect.right - rect.left,
                    "height": rect.bottom - rect.top,
                },
            }, summary=f"Active window: {title or 'Unknown'}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ListMonitorsTool(BaseTool):
    name = "list_monitors"
    description = "List all connected monitors/displays with dimensions."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "display"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            monitors = []
            MONITORINFOF_PRIMARY = 1

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            def monitor_enum_proc(hmonitor, hdc, lprect, lparam):
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))
                
                monitors.append({
                    "handle": int(hmonitor),
                    "left": info.rcMonitor.left, "top": info.rcMonitor.top,
                    "right": info.rcMonitor.right, "bottom": info.rcMonitor.bottom,
                    "width": info.rcMonitor.right - info.rcMonitor.left,
                    "height": info.rcMonitor.bottom - info.rcMonitor.top,
                    "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
                })
                return True

            MONITOR_ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)
            user32.EnumDisplayMonitors(None, None, MONITOR_ENUM_PROC(monitor_enum_proc), 0)

            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                "monitors": monitors,
                "count": len(monitors),
            }, summary=f"Found {len(monitors)} monitor(s)")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))