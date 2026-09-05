"""MouseService - control mouse cursor position and clicks."""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)


class MouseService(Singleton):
    """Simulate mouse movements and clicks."""

    async def move(self, x: int, y: int) -> dict[str, Any]:
        """Move mouse to absolute coordinates."""
        try:
            import pyautogui

            pyautogui.moveTo(x, y, duration=0.1)
            return {"summary": f"Moved mouse to ({x}, {y})", "x": x, "y": y}
        except ImportError:
            raise RuntimeError("pyautogui is required for mouse control")
        except Exception as exc:
            logger.exception("mouse.move failed")
            raise RuntimeError(f"Failed to move mouse: {exc}") from exc

    async def click(self, button: str = "left") -> dict[str, Any]:
        """Click at current position."""
        try:
            import pyautogui

            pyautogui.click(button=button)
            return {"summary": f"Clicked {button} button"}
        except ImportError:
            raise RuntimeError("pyautogui is required for mouse control")
        except Exception as exc:
            logger.exception("mouse.click failed")
            raise RuntimeError(f"Failed to click: {exc}") from exc

    async def double_click(self) -> dict[str, Any]:
        """Double-click at current position."""
        try:
            import pyautogui

            pyautogui.doubleClick()
            return {"summary": "Double-clicked"}
        except ImportError:
            raise RuntimeError("pyautogui is required for mouse control")
        except Exception as exc:
            logger.exception("mouse.double_click failed")
            raise RuntimeError(f"Failed to double-click: {exc}") from exc

    async def scroll(self, clicks: int = 1) -> dict[str, Any]:
        """Scroll the mouse wheel."""
        try:
            import pyautogui

            pyautogui.scroll(clicks)
            return {"summary": f"Scrolled {clicks} clicks"}
        except ImportError:
            raise RuntimeError("pyautogui is required for mouse control")
        except Exception as exc:
            logger.exception("mouse.scroll failed")
            raise RuntimeError(f"Failed to scroll: {exc}") from exc

    async def get_position(self) -> dict[str, Any]:
        """Get current mouse position."""
        try:
            import pyautogui

            x, y = pyautogui.position()
            return {"x": x, "y": y, "summary": f"Mouse at ({x}, {y})"}
        except ImportError:
            raise RuntimeError("pyautogui is required for mouse control")
        except Exception as exc:
            logger.exception("mouse.get_position failed")
            raise RuntimeError(f"Failed to get position: {exc}") from exc
