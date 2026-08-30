"""Enhanced keyboard service with hold, release, unicode typing support."""

from __future__ import annotations

import time
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)


class KeyboardEnhancedService(Singleton):
    """Enhanced keyboard simulation with hold/release and unicode support."""

    async def hold_key(self, key: str, duration_ms: int = 500) -> dict[str, Any]:
        """Hold a key down for a specified duration."""
        if not key:
            raise ValueError("key is required")
        try:
            import pyautogui
            pyautogui.keyDown(key)
            await self._sleep(duration_ms / 1000.0)
            pyautogui.keyUp(key)
            return {"summary": f"Key '{key}' held for {duration_ms}ms"}
        except ImportError:
            raise RuntimeError("pyautogui required")
        except Exception as exc:
            logger.exception("hold_key failed")
            raise RuntimeError(f"Failed to hold key: {exc}") from exc

    async def release_key(self, key: str) -> dict[str, Any]:
        """Release a held key."""
        if not key:
            raise ValueError("key is required")
        try:
            import pyautogui
            pyautogui.keyUp(key)
            return {"summary": f"Key '{key}' released"}
        except ImportError:
            raise RuntimeError("pyautogui required")
        except Exception as exc:
            logger.exception("release_key failed")
            raise RuntimeError(f"Failed to release key: {exc}") from exc

    async def press_key(self, key: str) -> dict[str, Any]:
        """Press and release a single key."""
        if not key:
            raise ValueError("key is required")
        try:
            import pyautogui
            pyautogui.press(key)
            return {"summary": f"Pressed key '{key}'"}
        except ImportError:
            raise RuntimeError("pyautogui required")
        except Exception as exc:
            logger.exception("press_key failed")
            raise RuntimeError(f"Failed to press key: {exc}") from exc

    async def type_unicode(self, text: str) -> dict[str, Any]:
        """Type text including Unicode characters using clipboard paste method."""
        if not text:
            raise ValueError("text is required")
        try:
            # Use clipboard to paste Unicode text for reliability
            import pyperclip
            pyperclip.copy(text)
            import pyautogui
            pyautogui.hotkey("ctrl", "v")
            # Small delay to ensure paste completes
            await self._sleep(0.1)
            return {"summary": f"Typed {len(text)} Unicode characters via clipboard paste"}
        except ImportError:
            raise RuntimeError("pyperclip and pyautogui required")
        except Exception as exc:
            logger.exception("type_unicode failed")
            raise RuntimeError(f"Failed to type unicode: {exc}") from exc

    async def hotkey(self, keys: list[str]) -> dict[str, Any]:
        """Execute a keyboard shortcut."""
        if not keys:
            raise ValueError("keys list is required")
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return {"summary": f"Hotkey: {'+'.join(keys)}"}
        except ImportError:
            raise RuntimeError("pyautogui required")
        except Exception as exc:
            logger.exception("hotkey failed")
            raise RuntimeError(f"Failed to press hotkey: {exc}") from exc

    async def write_text(self, text: str, interval: float = 0.01) -> dict[str, Any]:
        """Type text at current cursor position."""
        if not text:
            raise ValueError("text is required")
        try:
            import pyautogui
            pyautogui.write(text, interval=interval)
            return {"summary": f"Typed {len(text)} characters"}
        except ImportError:
            raise RuntimeError("pyautogui required")
        except Exception as exc:
            logger.exception("write_text failed")
            raise RuntimeError(f"Failed to type: {exc}") from exc

    @staticmethod
    async def _sleep(seconds: float) -> None:
        import asyncio
        await asyncio.sleep(seconds)
