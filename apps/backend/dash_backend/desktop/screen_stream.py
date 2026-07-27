"""Live screen streaming service for remote desktop.

Captures screen frames, encodes as JPEG, and streams via WebSocket.
Supports multi-monitor, adjustable quality, and mouse/keyboard relay.
"""

from __future__ import annotations

import asyncio
import base64
import io
import mss
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ScreenStreamer:
    """Captures and streams screen frames to connected clients."""

    def __init__(self) -> None:
        self._sct: mss.mss | None = None
        self._quality: int = 70
        self._monitor: int = 0  # 0 = all monitors combined
        self._fps: int = 15
        self._running: bool = False
        self._frame_count: int = 0
        self._clients: dict[str, asyncio.Queue] = {}

    def _get_sct(self) -> mss.mss:
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def get_monitors(self) -> list[dict[str, Any]]:
        """Return list of available monitors with dimensions."""
        try:
            sct = self._get_sct()
            monitors = []
            for i, m in enumerate(sct.monitors):
                if i == 0:
                    continue  # Skip "all monitors" combined
                monitors.append({
                    "id": i,
                    "left": m["left"],
                    "top": m["top"],
                    "width": m["width"],
                    "height": m["height"],
                    "name": f"Monitor {i}",
                })
            return monitors
        except Exception as e:
            logger.error("Failed to enumerate monitors: %s", e)
            return []

    def set_quality(self, quality: int) -> None:
        """Set JPEG quality (1-100)."""
        self._quality = max(1, min(100, quality))

    def set_monitor(self, monitor_id: int) -> None:
        """Set which monitor to capture (0 = all)."""
        self._monitor = monitor_id

    def set_fps(self, fps: int) -> None:
        """Set target FPS (1-60)."""
        self._fps = max(1, min(60, fps))

    async def capture_frame(self) -> dict[str, Any] | None:
        """Capture a single frame and return as base64 JPEG."""
        try:
            sct = self._get_sct()
            monitor = sct.monitors[self._monitor] if self._monitor > 0 else sct.monitors[0]
            screenshot = sct.grab(monitor)

            # Convert to JPEG bytes
            from PIL import Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=self._quality, optimize=True)
            jpeg_bytes = buffer.getvalue()

            self._frame_count += 1
            return {
                "monitor": self._monitor,
                "width": screenshot.size[0],
                "height": screenshot.size[1],
                "data": base64.b64encode(jpeg_bytes).decode("utf-8"),
                "frame": self._frame_count,
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.debug("Frame capture failed: %s", e)
            return None

    async def stream_to_client(self, client_id: str, queue: asyncio.Queue) -> None:
        """Stream frames to a specific client queue."""
        self._clients[client_id] = queue
        self._running = True
        try:
            while self._running:
                frame = await self.capture_frame()
                if frame:
                    await queue.put(frame)
                await asyncio.sleep(1.0 / self._fps)
        except asyncio.CancelledError:
            pass
        finally:
            self._clients.pop(client_id, None)

    def stop(self) -> None:
        """Stop streaming."""
        self._running = False

    def get_stats(self) -> dict[str, Any]:
        """Get streaming statistics."""
        return {
            "fps": self._fps,
            "quality": self._quality,
            "monitor": self._monitor,
            "frame_count": self._frame_count,
            "active_clients": len(self._clients),
            "running": self._running,
        }


# Singleton
_streamer: ScreenStreamer | None = None


def get_screen_streamer() -> ScreenStreamer:
    global _streamer
    if _streamer is None:
        _streamer = ScreenStreamer()
    return _streamer