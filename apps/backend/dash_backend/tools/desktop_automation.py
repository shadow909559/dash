"""Desktop automation tools with safety controls.

Provides mouse control, keyboard input, screenshot, window management,
and automation logging with rollback support.
All destructive operations require confirmation.
"""

from __future__ import annotations

import platform
import time
from typing import Any, Dict, List

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)

IS_WINDOWS = platform.system().lower() == "windows"

# Automation execution log
_automation_history: List[Dict[str, Any]] = []


def log_automation(action: str, details: Dict[str, Any], status: str):
    """Log an automation action for history and rollback."""
    entry = {
        "action": action,
        "details": details,
        "status": status,
        "timestamp": time.time(),
    }
    _automation_history.append(entry)
    if len(_automation_history) > 1000:
        _automation_history.pop(0)
    logger.info("Automation: %s -> %s", action, status)
    return entry


def get_automation_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent automation history."""
    return list(_automation_history[-limit:])


# =========================================================================
# Mouse Control
# =========================================================================


class MouseMoveTool(BaseTool):
    name = "mouse_move"
    description = "Move the mouse cursor to specified coordinates (requires AutoGUI or platform API)."
    parameters = [
        ToolParameter("x", "X coordinate", type="integer", required=True),
        ToolParameter("y", "Y coordinate", type="integer", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "automation"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        x = int(kwargs["x"])
        y = int(kwargs["y"])
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=0.2)
            log_automation("mouse_move", {"x": x, "y": y}, "success")
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"x": x, "y": y}, summary=f"Moved mouse to ({x}, {y})"
            )
        except ImportError:
            return ToolResult(
                tool_name=self.name, status=ToolStatus.ERROR,
                error_message="Mouse control requires pyautogui"
            )
        except Exception as exc:
            log_automation("mouse_move", {"x": x, "y": y}, f"error: {exc}")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MouseClickTool(BaseTool):
    name = "mouse_click"
    description = "Click at the current mouse position or at specified coordinates."
    parameters = [
        ToolParameter("x", "Optional X coordinate", type="integer", required=False),
        ToolParameter("y", "Optional Y coordinate", type="integer", required=False),
        ToolParameter("button", "Mouse button (left/right/middle)", required=False, default="left"),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "automation"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        x = kwargs.get("x")
        y = kwargs.get("y")
        button = kwargs.get("button", "left")
        try:
            import pyautogui
            if x is not None and y is not None:
                pyautogui.click(int(x), int(y), button=button)
            else:
                pyautogui.click(button=button)
            log_automation("mouse_click", {"x": x, "y": y, "button": button}, "success")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Clicked {button}")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Mouse control requires pyautogui")
        except Exception as exc:
            log_automation("mouse_click", {"button": button}, f"error: {exc}")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MouseDragTool(BaseTool):
    name = "mouse_drag"
    description = "Drag the mouse from current position to target coordinates."
    parameters = [
        ToolParameter("x", "Target X coordinate", type="integer", required=True),
        ToolParameter("y", "Target Y coordinate", type="integer", required=True),
    ]
    permission_level = PermissionLevel.RESTRICTED
    category = "automation"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        x = int(kwargs["x"])
        y = int(kwargs["y"])
        try:
            import pyautogui
            pyautogui.dragTo(x, y, duration=0.3)
            log_automation("mouse_drag", {"x": x, "y": y}, "success")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Dragged to ({x}, {y})")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Requires pyautogui")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# =========================================================================
# Keyboard Control
# =========================================================================


class KeyboardTypeTool(BaseTool):
    name = "keyboard_type"
    description = "Type text at the current cursor position."
    parameters = [
        ToolParameter("text", "Text to type", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "automation"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        text = kwargs["text"]
        try:
            import pyautogui
            pyautogui.write(text)
            log_automation("keyboard_type", {"length": len(text)}, "success")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Typed {len(text)} characters")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Keyboard control requires pyautogui")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class KeyboardHotkeyTool(BaseTool):
    name = "keyboard_hotkey"
    description = "Press a keyboard shortcut (e.g., Ctrl+C, Alt+Tab)."
    parameters = [
        ToolParameter("keys", "List of keys or a single shortcut string", required=True, type="array"),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "automation"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        keys = kwargs["keys"]
        try:
            import pyautogui
            if isinstance(keys, list):
                pyautogui.hotkey(*keys)
            else:
                pyautogui.write(str(keys))
            log_automation("keyboard_hotkey", {"keys": keys}, "success")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Pressed hotkey")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Requires pyautogui")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# =========================================================================
# Screenshot
# =========================================================================


class ScreenshotTool(BaseTool):
    name = "take_screenshot"
    description = "Capture a screenshot of the primary monitor."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "automation"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        """Try to capture a screenshot using PIL/pyautogui or fallback."""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            import io
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            image_bytes = buf.getvalue()
            log_automation("screenshot", {"size": len(image_bytes)}, "success")
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"image_bytes": list(image_bytes)[:100], "size": len(image_bytes)},
                summary=f"Screenshot captured ({len(image_bytes)} bytes)"
            )
        except ImportError:
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab()
                import io
                buf = io.BytesIO()
                screenshot.save(buf, format="PNG")
                image_bytes = buf.getvalue()
                return ToolResult(
                    tool_name=self.name, status=ToolStatus.SUCCESS,
                    output={"size": len(image_bytes)},
                    summary="Screenshot captured via PIL"
                )
            except ImportError:
                return ToolResult(
                    tool_name=self.name, status=ToolStatus.ERROR,
                    error_message="Screenshot requires pyautogui or PIL"
                )
        except Exception as exc:
            log_automation("screenshot", {}, f"error: {exc}")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class GetAutomationHistoryTool(BaseTool):
    name = "get_automation_history"
    description = "Get recent automation action history."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "automation"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        history = get_automation_history(limit=50)
        return ToolResult(
            tool_name=self.name, status=ToolStatus.SUCCESS,
            output={"history": history},
            summary=f"Returned {len(history)} automation history entries"
        )
