"""Clipboard relay service for remote desktop - syncs clipboard between devices."""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)
IS_WINDOWS = sys.platform == "win32"


class ClipboardRelay:
    """Relays clipboard content between remote desktop client and host.

    Monitors clipboard changes and pushes them to connected clients.
    Also accepts remote clipboard content and writes to local clipboard.
    """

    def __init__(self) -> None:
        self._last_content: str = ""
        self._last_check: float = 0.0
        self._check_interval: float = 0.5
        self._enabled: bool = True

    async def get_clipboard(self) -> dict[str, Any]:
        """Read current clipboard content."""
        try:
            if IS_WINDOWS:
                import ctypes
                CF_UNICODETEXT = 13
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                if not user32.OpenClipboard(None):
                    return {"text": "", "error": "OpenClipboard failed"}
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    user32.CloseClipboard()
                    return {"text": ""}
                lpwcstr = kernel32.GlobalLock(handle)
                size = kernel32.GlobalSize(handle)
                raw = ctypes.create_string_buffer(size)
                ctypes.memmove(raw, lpwcstr, size)
                kernel32.GlobalUnlock(handle)
                user32.CloseClipboard()
                text = raw.raw.decode("utf-16le", errors="ignore").rstrip("\x00")
                return {"text": text}
            else:
                import pyperclip
                text = pyperclip.paste()
                return {"text": text}
        except Exception as exc:
            logger.debug("Clipboard read failed: %s", exc)
            return {"text": "", "error": str(exc)}

    async def set_clipboard(self, text: str) -> dict[str, Any]:
        """Write text to clipboard."""
        if not text:
            return {"error": "empty text"}
        try:
            if IS_WINDOWS:
                import ctypes
                CF_UNICODETEXT = 13
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                if not user32.OpenClipboard(None):
                    return {"error": "OpenClipboard failed"}
                user32.EmptyClipboard()
                hGlobalMem = kernel32.GlobalAlloc(0x0002, (len(text) + 1) * 2)
                lpGlobalMem = kernel32.GlobalLock(hGlobalMem)
                ctypes.memmove(lpGlobalMem, text.encode("utf-16le"), len(text) * 2)
                kernel32.GlobalUnlock(hGlobalMem)
                user32.SetClipboardData(CF_UNICODETEXT, hGlobalMem)
                user32.CloseClipboard()
                self._last_content = text
                return {"success": True}
            else:
                import pyperclip
                pyperclip.copy(text)
                self._last_content = text
                return {"success": True}
        except Exception as exc:
            logger.debug("Clipboard write failed: %s", exc)
            return {"error": str(exc)}

    async def poll_changes(self) -> str | None:
        """Check if clipboard changed and return new content."""
        now = time.time()
        if now - self._last_check < self._check_interval:
            return None
        self._last_check = now
        result = await self.get_clipboard()
        text = result.get("text", "")
        if text and text != self._last_content:
            self._last_content = text
            return text
        return None

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def get_status(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "last_content_length": len(self._last_content),
            "check_interval": self._check_interval,
        }


# Singleton
_relay: ClipboardRelay | None = None


def get_clipboard_relay() -> ClipboardRelay:
    global _relay
    if _relay is None:
        _relay = ClipboardRelay()
    return _relay
