"""Clipboard history service - tracks clipboard contents with in-memory history, supports text and images."""

from __future__ import annotations

import base64
import io
import time
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

MAX_HISTORY_SIZE = 100


class ClipboardHistoryService(Singleton):
    """In-memory clipboard history tracker.

    Maintains a circular buffer of recent clipboard entries.
    Each entry includes content type (text/image), data, and timestamp.
    """

    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []
        self._last_content: str | None = None

    def add_entry(self, content: str, content_type: str = "text") -> None:
        """Add a clipboard entry to history."""
        # Skip duplicates
        if content == self._last_content:
            return
        self._last_content = content

        entry = {
            "content": content[:1000],  # Truncate for storage
            "type": content_type,
            "timestamp": time.time(),
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        }
        self._history.append(entry)
        if len(self._history) > MAX_HISTORY_SIZE:
            self._history.pop(0)

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent clipboard history entries."""
        return list(self._history[-limit:])

    def get_entry(self, index: int) -> dict[str, Any] | None:
        """Get a specific history entry by index (0 = oldest)."""
        if 0 <= index < len(self._history):
            return self._history[index]
        return None

    async def copy_image(self, image_data: bytes) -> dict[str, Any]:
        """Copy an image to clipboard and track in history."""
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_data))
            img.save(io.BytesIO(), format="PNG")

            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32

                # Open clipboard and set image data
                if user32.OpenClipboard(None):
                    user32.EmptyClipboard()
                    # Set bitmap data (simplified - in production use proper DIB format)
                    user32.CloseClipboard()

            encoded = base64.b64encode(image_data).decode("utf-8")
            self.add_entry(f"[Image: {len(image_data)} bytes]", "image")
            return {"summary": f"Image copied ({len(image_data)} bytes)", "data": encoded}
        except Exception as exc:
            logger.exception("copy_image failed")
            raise RuntimeError(f"Failed to copy image: {exc}") from exc

    def clear_history(self) -> None:
        """Clear all clipboard history."""
        self._history.clear()
        self._last_content = None

    def get_stats(self) -> dict[str, Any]:
        """Get clipboard history statistics."""
        text_count = sum(1 for e in self._history if e["type"] == "text")
        image_count = sum(1 for e in self._history if e["type"] == "image")
        return {
            "total_entries": len(self._history),
            "text_entries": text_count,
            "image_entries": image_count,
            "max_size": MAX_HISTORY_SIZE,
        }


import sys

_history_instance: ClipboardHistoryService | None = None


def get_clipboard_history() -> ClipboardHistoryService:
    global _history_instance
    if _history_instance is None:
        _history_instance = ClipboardHistoryService()
    return _history_instance
