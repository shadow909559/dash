"""Camera Vision - Camera capture and analysis for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CameraVision:
    def __init__(self):
        self._camera_id = 0
        self._active = False
    
    async def capture(self, camera_id: int = 0) -> Optional[bytes]:
        try:
            import cv2
            cap = cv2.VideoCapture(camera_id)
            ret, frame = cap.read()
            cap.release()
            if ret:
                import io
                import cv2 as cv
                success, buffer = cv.imencode('.jpg', frame)
                if success:
                    return buffer.tobytes()
            return None
        except Exception as exc:
            logger.warning("Camera capture failed: %s", exc)
            return None
    
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
