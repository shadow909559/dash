"""Screen Capture - Capture screenshots and screen regions."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ScreenCapture:
    def __init__(self, quality: int = 80):
        self._quality = quality

    async def capture_full(self) -> Optional[bytes]:
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as exc:
            logger.warning("Screen capture failed: %s", exc)
            return None

    async def capture_region(self, x: int, y: int, width: int, height: int) -> Optional[bytes]:
        try:
            import pyautogui
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return None

    async def capture_window(self, title: str) -> Optional[bytes]:
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title)
            if windows:
                w = windows[0]
                return await self.capture_region(w.left, w.top, w.width, w.height)
            return None
        except Exception:
            return None

    def set_quality(self, quality: int) -> None:
        self._quality = max(10, min(100, quality))


_screen_capture: Optional[ScreenCapture] = None


def get_screen_capture() -> ScreenCapture:
    global _screen_capture
    if _screen_capture is None:
        _screen_capture = ScreenCapture()
    return _screen_capture
