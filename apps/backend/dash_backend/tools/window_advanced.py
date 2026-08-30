"""Advanced window control tools: maximize, minimize, send-to-back, tile, cascade, arrange.

Extends the existing window management capabilities with the higher-level
window layout operations DASH needs for natural-language desktop control.
"""

from __future__ import annotations

import sys
from typing import Any, List

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus
from dash_backend.tools.window_management_tools import _find_window

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


def _get_all_visible_windows() -> List[int]:
    """Enumerate all visible top-level window handles."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    IsWindowVisible = user32.IsWindowVisible
    GetWindowTextLength = user32.GetWindowTextLengthW
    GetWindowText = user32.GetWindowTextW

    hwnds: List[int] = []

    def foreach_window(hwnd, lParam):
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLength(hwnd)
        if length < 1:
            return True
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        if buff.value.strip():
            hwnds.append(hwnd)
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)
    return hwnds


def _get_window_title(hwnd: int) -> str:
    """Get the title of a window handle."""
    import ctypes
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value


class MaximizeWindowTool(BaseTool):
    name = "maximize_window"
    description = "Maximize a window by title substring."
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
            user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Maximized window: {title}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MinimizeWindowTool(BaseTool):
    name = "minimize_window"
    description = "Minimize a window by title substring."
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
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Minimized window: {title}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SendToBackWindowTool(BaseTool):
    name = "send_window_to_back"
    description = "Send a window to the back of the z-order."
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
            # HWND_BOTTOM = 1, SWP_NOSIZE=0x1 | SWP_NOMOVE=0x2 | SWP_NOACTIVATE=0x10
            user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Sent window to back: {title}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class TileWindowsTool(BaseTool):
    name = "tile_windows"
    description = "Tile all visible windows evenly across the screen."
    parameters = [ToolParameter("max_windows", "Maximum windows to tile", type="integer", required=False, default=6)]
    permission_level = PermissionLevel.AUTO
    category = "window"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnds = _get_all_visible_windows()
            if not hwnds:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="No visible windows found")
            max_n = min(int(kwargs.get("max_windows", 6)), len(hwnds))
            hwnds = hwnds[:max_n]

            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            cols = int(__import__("math").ceil(max_n ** 0.5))
            rows = int(__import__("math").ceil(max_n / cols))
            cell_w = screen_w // cols
            cell_h = screen_h // rows

            for i, hwnd in enumerate(hwnds):
                col = i % cols
                row = i // cols
                x = col * cell_w
                y = row * cell_h
                user32.SetWindowPos(hwnd, 0, x, y, cell_w, cell_h, 0x0004)
                user32.ShowWindow(hwnd, 9)  # restore
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"tiled": len(hwnds), "cols": cols, "rows": rows},
                summary=f"Tiled {len(hwnds)} windows ({cols}x{rows})",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CascadeWindowsTool(BaseTool):
    name = "cascade_windows"
    description = "Cascade all visible windows diagonally."
    parameters = [ToolParameter("max_windows", "Maximum windows to cascade", type="integer", required=False, default=6)]
    permission_level = PermissionLevel.AUTO
    category = "window"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnds = _get_all_visible_windows()
            if not hwnds:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="No visible windows found")
            max_n = min(int(kwargs.get("max_windows", 6)), len(hwnds))
            hwnds = hwnds[:max_n]

            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            width = int(screen_w * 0.7)
            height = int(screen_h * 0.7)
            offset = 30

            for i, hwnd in enumerate(hwnds):
                x = i * offset % max(1, screen_w - width)
                y = i * offset % max(1, screen_h - height)
                user32.SetWindowPos(hwnd, 0, x, y, width, height, 0x0004)
                user32.ShowWindow(hwnd, 9)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"cascaded": len(hwnds)},
                summary=f"Cascaded {len(hwnds)} windows",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ArrangeWindowsTool(BaseTool):
    name = "arrange_windows"
    description = "Arrange windows into a grid or layout mode (grid|split|stack)."
    parameters = [
        ToolParameter("layout", "Layout mode", required=False, default="grid",
                      enum=["grid", "split", "stack"]),
        ToolParameter("max_windows", "Maximum windows to arrange", type="integer", required=False, default=6),
    ]
    permission_level = PermissionLevel.AUTO
    category = "window"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnds = _get_all_visible_windows()
            if not hwnds:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="No visible windows found")
            max_n = min(int(kwargs.get("max_windows", 6)), len(hwnds))
            hwnds = hwnds[:max_n]
            layout = kwargs.get("layout", "grid")

            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)

            if layout == "split":
                n = len(hwnds)
                for i, hwnd in enumerate(hwnds):
                    w = screen_w // n
                    user32.SetWindowPos(hwnd, 0, i * w, 0, w, screen_h, 0x0004)
                    user32.ShowWindow(hwnd, 9)
            elif layout == "stack":
                for i, hwnd in enumerate(hwnds):
                    h = screen_h // len(hwnds)
                    user32.SetWindowPos(hwnd, 0, 0, i * h, screen_w, h, 0x0004)
                    user32.ShowWindow(hwnd, 9)
            else:  # grid
                cols = int(__import__("math").ceil(max_n ** 0.5))
                rows = int(__import__("math").ceil(max_n / cols))
                cell_w = screen_w // cols
                cell_h = screen_h // rows
                for i, hwnd in enumerate(hwnds):
                    col = i % cols
                    row = i // cols
                    user32.SetWindowPos(hwnd, 0, col * cell_w, row * cell_h, cell_w, cell_h, 0x0004)
                    user32.ShowWindow(hwnd, 9)

            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"layout": layout, "arranged": len(hwnds)},
                summary=f"Arranged {len(hwnds)} windows ({layout})",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


def register_window_advanced_tools() -> None:
    """Register advanced window tools with the tool registry."""
    from dash_backend.tools.tool_registry import get_registry
    registry = get_registry()
    tool_classes = [
        MaximizeWindowTool,
        MinimizeWindowTool,
        SendToBackWindowTool,
        TileWindowsTool,
        CascadeWindowsTool,
        ArrangeWindowsTool,
    ]
    for cls in tool_classes:
        name = getattr(cls, "name", cls.__name__)
        try:
            if registry.get(name) is None:
                registry.register(cls())
                logger.info("Registered window tool: %s", name)
        except Exception:
            logger.exception("Failed to register window tool %s", name)


# Run on import
register_window_advanced_tools()
