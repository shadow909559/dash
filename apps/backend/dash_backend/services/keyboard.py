"""KeyboardService - type text and press hotkeys."""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)


class KeyboardService(Singleton):
    """Simulate keyboard input."""

    async def type_text(self, text: str) -> dict[str, Any]:
        """Type text at current cursor position."""
        if not text:
            raise ValueError("text is required")
        try:
            import pyautogui

            pyautogui.write(text, interval=0.01)
            return {"summary": f"Typed {len(text)} characters"}
        except ImportError:
            raise RuntimeError("pyautogui is required for keyboard typing")
        except Exception as exc:
            logger.exception("keyboard.type_text failed")
            raise RuntimeError(f"Failed to type: {exc}") from exc

    async def hotkey(self, *keys: str) -> dict[str, Any]:
        """Press a keyboard shortcut (e.g., hotkey('ctrl', 'c'))."""
        if not keys:
            raise ValueError("at least one key is required")
        try:
            import pyautogui

            pyautogui.hotkey(*keys)
            return {"summary": f"Pressed hotkey: {'+'.join(keys)}"}
        except ImportError:
            raise RuntimeError("pyautogui is required for hotkeys")
        except Exception as exc:
            logger.exception("keyboard.hotkey failed")
            raise RuntimeError(f"Failed to press hotkey: {exc}") from exc

    async def press(self, key: str) -> dict[str, Any]:
        """Press and release a single key."""
        if not key:
            raise ValueError("key is required")
        try:
            import pyautogui

            pyautogui.press(key)
            return {"summary": f"Pressed key: {key}"}
        except ImportError:
            raise RuntimeError("pyautogui is required for key press")
        except Exception as exc:
            logger.exception("keyboard.press failed")
            raise RuntimeError(f"Failed to press key: {exc}") from exc
