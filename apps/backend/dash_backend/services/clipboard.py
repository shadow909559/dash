"""ClipboardService - read, write, and clear clipboard contents."""

from __future__ import annotations

import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


class ClipboardService(Singleton):
    """Manage system clipboard."""

    async def copy(self, text: str) -> dict[str, Any]:
        """Copy text to clipboard."""
        if not text:
            raise ValueError("text is required")
        try:
            if IS_WINDOWS:
                import ctypes

                CF_UNICODETEXT = 13
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                if not user32.OpenClipboard(None):
                    raise RuntimeError("OpenClipboard failed")
                user32.EmptyClipboard()
                hGlobalMem = kernel32.GlobalAlloc(0x0002, (len(text) + 1) * 2)
                lpGlobalMem = kernel32.GlobalLock(hGlobalMem)
                ctypes.memmove(lpGlobalMem, text.encode("utf-16le"), len(text) * 2)
                kernel32.GlobalUnlock(hGlobalMem)
                user32.SetClipboardData(CF_UNICODETEXT, hGlobalMem)
                user32.CloseClipboard()
                return {"summary": f"Copied {len(text)} chars to clipboard"}
            else:
                import pyperclip

                pyperclip.copy(text)
                return {"summary": f"Copied {len(text)} chars to clipboard"}
        except Exception as exc:
            logger.exception("clipboard.copy failed")
            raise RuntimeError(f"Failed to copy: {exc}") from exc

    async def paste(self) -> dict[str, Any]:
        """Paste from clipboard by simulating Ctrl+V."""
        try:
            from dash_backend.services.keyboard import KeyboardService

            kb = KeyboardService()
            await kb.hotkey("ctrl", "v")
            return {"summary": "Pasted clipboard contents"}
        except Exception as exc:
            logger.exception("clipboard.paste failed")
            raise RuntimeError(f"Failed to paste: {exc}") from exc

    async def read(self) -> dict[str, Any]:
        """Read text from clipboard."""
        try:
            if IS_WINDOWS:
                import ctypes

                CF_UNICODETEXT = 13
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                if not user32.OpenClipboard(None):
                    raise RuntimeError("OpenClipboard failed")
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    user32.CloseClipboard()
                    return {"text": "", "summary": "Clipboard empty"}
                lpwcstr = kernel32.GlobalLock(handle)
                size = kernel32.GlobalSize(handle)
                raw = ctypes.create_string_buffer(size)
                ctypes.memmove(raw, lpwcstr, size)
                kernel32.GlobalUnlock(handle)
                user32.CloseClipboard()
                text = raw.raw.decode("utf-16le", errors="ignore").rstrip("\x00")
                return {"text": text, "summary": f"Read {len(text)} chars from clipboard"}
            else:
                import pyperclip

                text = pyperclip.paste()
                return {"text": text, "summary": f"Read {len(text)} chars from clipboard"}
        except Exception as exc:
            logger.exception("clipboard.read failed")
            raise RuntimeError(f"Failed to read clipboard: {exc}") from exc

    async def clear(self) -> dict[str, Any]:
        """Clear the clipboard."""
        try:
            if IS_WINDOWS:
                import ctypes

                user32 = ctypes.windll.user32
                if not user32.OpenClipboard(None):
                    raise RuntimeError("OpenClipboard failed")
                user32.EmptyClipboard()
                user32.CloseClipboard()
                return {"summary": "Clipboard cleared"}
            else:
                import pyperclip

                pyperclip.copy("")
                return {"summary": "Clipboard cleared"}
        except Exception as exc:
            logger.exception("clipboard.clear failed")
            raise RuntimeError(f"Failed to clear clipboard: {exc}") from exc
