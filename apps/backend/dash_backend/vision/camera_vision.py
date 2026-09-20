"""Camera Vision - Camera capture and analysis for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CaptureResult:
    """The outcome of one capture attempt, honestly labeled.

    ``frame`` is JPEG bytes on success. On failure, ``error`` names the
    actual cause (OpenCV missing / no device / device busy / unknown) and
    ``hint`` says what to do about it — the caller never has to guess why
    it failed, and never receives fake frame data.
    """

    frame: Optional[bytes] = None
    error: Optional[str] = None
    hint: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.frame is not None and self.error is None


class CameraVision:
    def __init__(self):
        self._camera_id = 0
        self._active = False

    async def capture_result(self, camera_id: int = 0) -> CaptureResult:
        """Capture one frame, with a named cause when it fails."""
        try:
            import cv2
        except Exception:
            return CaptureResult(
                frame=None,
                error="opencv not installed",
                hint="pip install opencv-python, then restart DASH",
            )
        try:
            # Blocking device I/O must not stall the event loop.
            return await asyncio.to_thread(self._capture_blocking, cv2, camera_id)
        except Exception as exc:
            logger.warning("Camera capture failed: %s", exc)
            return CaptureResult(
                frame=None, error=f"capture failed: {exc}",
                hint="check that no other app is using the camera",
            )

    @staticmethod
    def _capture_blocking(cv2, camera_id: int) -> CaptureResult:
        cap = cv2.VideoCapture(camera_id)
        try:
            if not cap.isOpened():
                return CaptureResult(
                    frame=None,
                    error="no camera available (device absent or busy)",
                    hint="connect a camera or free it from other apps",
                )
            ret, frame = cap.read()
            if not ret or frame is None:
                return CaptureResult(
                    frame=None,
                    error="camera opened but returned no frame",
                    hint="the device may be busy or warming up — retry",
                )
            success, buffer = cv2.imencode(".jpg", frame)
            if not success:
                return CaptureResult(
                    frame=None, error="frame could not be encoded to jpeg",
                    hint="retry capture",
                )
            return CaptureResult(frame=buffer.tobytes())
        finally:
            cap.release()

    # ── Legacy shim: boolean-style capture for existing callers ─────────

    async def capture(self, camera_id: int = 0) -> Optional[bytes]:
        result = await self.capture_result(camera_id)
        return result.frame

    async def start_stream(self, camera_id: int = 0) -> bool:
        self._camera_id = camera_id
        self._active = True
        return True

    async def stop_stream(self) -> None:
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active


_camera_vision: Optional[CameraVision] = None


def get_camera_vision() -> CameraVision:
    global _camera_vision
    if _camera_vision is None:
        _camera_vision = CameraVision()
    return _camera_vision
