"""ClipboardService - read, write, and clear clipboard contents."""

import sys
from typing import Any

import ctypes

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


def _win_clipboard_apis():
    """ctypes bindings with correct 64-bit HANDLE prototypes.

    Without explicit restype/argtypes ctypes assumes 32-bit ints, which
    truncates HANDLEs on x64 ('int too long to convert' OverflowErrors).
    """
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.CloseClipboard.restype = ctypes.c_int
    user32.EmptyClipboard.restype = ctypes.c_int
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    return user32, kernel32


class ClipboardService(Singleton):
    """Manage system clipboard."""

    async def copy(self, text: str) -> dict[str, Any]:
        """Copy text to clipboard."""
        if not text:
            raise ValueError("text is required")
        try:
            if IS_WINDOWS:
                CF_UNICODETEXT = 13
                user32, kernel32 = _win_clipboard_apis()

                if not user32.OpenClipboard(None):
                    raise RuntimeError("OpenClipboard failed")
                try:
                    user32.EmptyClipboard()
                    data = text.encode("utf-16le") + b"\x00\x00"
                    hGlobalMem = kernel32.GlobalAlloc(0x0002, len(data))
                    lpGlobalMem = kernel32.GlobalLock(hGlobalMem)
                    ctypes.memmove(lpGlobalMem, data, len(data))
                    kernel32.GlobalUnlock(hGlobalMem)
                    user32.SetClipboardData(CF_UNICODETEXT, hGlobalMem)
                finally:
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
                CF_UNICODETEXT = 13
                user32, kernel32 = _win_clipboard_apis()

                if not user32.OpenClipboard(None):
                    raise RuntimeError("OpenClipboard failed")
                try:
                    handle = user32.GetClipboardData(CF_UNICODETEXT)
                    if not handle:
                        return {"text": "", "summary": "Clipboard empty"}
                    size = kernel32.GlobalSize(handle)
                    lpwcstr = kernel32.GlobalLock(handle)
                    if not lpwcstr:
                        return {"text": "", "summary": "Clipboard empty"}
                    try:
                        raw = ctypes.create_string_buffer(size)
                        ctypes.memmove(raw, lpwcstr, size)
                    finally:
                        kernel32.GlobalUnlock(handle)
                finally:
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
                user32, _ = _win_clipboard_apis()
                if not user32.OpenClipboard(None):
                    raise RuntimeError("OpenClipboard failed")
                try:
                    user32.EmptyClipboard()
                finally:
                    user32.CloseClipboard()
                return {"summary": "Clipboard cleared"}
            else:
                import pyperclip

                pyperclip.copy("")
                return {"summary": "Clipboard cleared"}
        except Exception as exc:
            logger.exception("clipboard.clear failed")
            raise RuntimeError(f"Failed to clear clipboard: {exc}") from exc
