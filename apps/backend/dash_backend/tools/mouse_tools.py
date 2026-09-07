"""Mouse control tools - relative move, right/middle click, drag, smooth movement."""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


class MouseRelativeMoveTool(BaseTool):
    name = "mouse_relative_move"
    description = "Move mouse cursor relative to its current position."
    parameters = [
        ToolParameter("dx", "Pixels to move horizontally (negative = left)", type="integer", required=True),
        ToolParameter("dy", "Pixels to move vertically (negative = up)", type="integer", required=True),
        ToolParameter("smooth", "Enable smooth movement", type="boolean", required=False, default=False),
    ]
    permission_level = PermissionLevel.AUTO
    category = "mouse"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        dx = int(kwargs.get("dx", 0))
        dy = int(kwargs.get("dy", 0))
        smooth = kwargs.get("smooth", False)
        try:
            import pyautogui
            x, y = pyautogui.position()
            target_x, target_y = x + dx, y + dy
            if smooth:
                pyautogui.moveTo(target_x, target_y, duration=0.3, tween=pyautogui.easeOutQuad)
            else:
                pyautogui.moveTo(target_x, target_y, duration=0.05)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS,
                              output={"x": target_x, "y": target_y},
                              summary=f"Moved mouse relative ({dx}, {dy})")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MouseDragTool(BaseTool):
    name = "mouse_drag"
    description = "Click and drag the mouse from current position to target."
    parameters = [
        ToolParameter("x", "Target X coordinate", type="integer", required=True),
        ToolParameter("y", "Target Y coordinate", type="integer", required=True),
        ToolParameter("button", "Mouse button: left, right, middle", required=False, default="left",
                      enum=["left", "right", "middle"]),
    ]
    permission_level = PermissionLevel.AUTO
    category = "mouse"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        x = int(kwargs.get("x", 0))
        y = int(kwargs.get("y", 0))
        button = kwargs.get("button", "left")
        try:
            import pyautogui
            pyautogui.dragTo(x, y, duration=0.3, button=button)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS,
                              summary=f"Dragged to ({x}, {y}) with {button} button")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MouseSmoothMoveTool(BaseTool):
    name = "mouse_smooth_move"
    description = "Move mouse to position with smooth animation."
    parameters = [
        ToolParameter("x", "Target X coordinate", type="integer", required=True),
        ToolParameter("y", "Target Y coordinate", type="integer", required=True),
        ToolParameter("duration", "Animation duration in seconds", type="number", required=False, default=0.5),
    ]
    permission_level = PermissionLevel.AUTO
    category = "mouse"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        x = int(kwargs.get("x", 0))
        y = int(kwargs.get("y", 0))
        duration = float(kwargs.get("duration", 0.5))
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=min(duration, 5.0), tween=pyautogui.easeOutQuad)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS,
                              summary=f"Smoothly moved to ({x}, {y})")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MouseRightClickTool(BaseTool):
    name = "mouse_right_click"
    description = "Right-click at the current cursor position."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "mouse"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            import pyautogui
            pyautogui.click(button="right")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Right-clicked")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MouseMiddleClickTool(BaseTool):
    name = "mouse_middle_click"
    description = "Middle-click at the current cursor position."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "mouse"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            import pyautogui
            pyautogui.click(button="middle")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Middle-clicked")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MouseScrollHorizontalTool(BaseTool):
    name = "mouse_scroll_horizontal"
    description = "Scroll horizontally using the mouse wheel."
    parameters = [
        ToolParameter("clicks", "Number of scroll steps (negative = left, positive = right)", type="integer", required=False, default=1),
    ]
    permission_level = PermissionLevel.AUTO
    category = "mouse"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        clicks = int(kwargs.get("clicks", 1))
        try:
            import pyautogui
            pyautogui.hscroll(clicks)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS,
                              summary=f"Scrolled horizontally {clicks} steps")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))

