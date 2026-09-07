"""Desktop Vision - Screen capture and understanding for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DesktopVision:
    def __init__(self):
        self._capture_quality = 80
    
    async def capture_screen(self, monitor: int = 0) -> Optional[bytes]:
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            import io
            buf = io.BytesIO()
            screenshot.save(buf, format='PNG', quality=self._capture_quality)
            return buf.getvalue()
        except Exception as exc:
            logger.warning("Screen capture failed: %s", exc)
            return None
    
    async def capture_region(self, x: int, y: int, width: int, height: int) -> Optional[bytes]:
        try:
            import pyautogui
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            import io
            buf = io.BytesIO()
            screenshot.save(buf, format='PNG')
            return buf.getvalue()
        except Exception:
            return None
    
    async def get_active_window_screenshot(self) -> Optional[bytes]:
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active:
                return await self.capture_region(
                    active.left, active.top, active.width, active.height
                )
            return await self.capture_screen()
        except Exception:
            return await self.capture_screen()
    
    def set_quality(self, quality: int) -> None:
        self._capture_quality = max(10, min(100, quality))


_desktop_vision: Optional[DesktopVision] = None


def get_desktop_vision() -> DesktopVision:
    global _desktop_vision
    if _desktop_vision is None:
        _desktop_vision = DesktopVision()
    return _desktop_vision
