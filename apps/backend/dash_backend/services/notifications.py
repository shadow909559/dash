"""NotificationService - show desktop notifications."""

from __future__ import annotations

import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


class NotificationService(Singleton):
    """Show desktop notifications."""

    async def show(
        self,
        title: str = "DASH",
        message: str = "",
        duration: int = 5,
    ) -> dict[str, Any]:
        """Show a desktop notification."""
        try:
            if IS_WINDOWS:
                import ctypes

                ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0)
                return {"summary": f"Notification shown: {title}"}
            else:
                # Try notify-send on Linux
                import subprocess

                subprocess.run(
                    ["notify-send", title, message],
                    capture_output=True,
                    timeout=duration,
                )
                return {"summary": f"Notification shown: {title}"}
        except Exception as exc:
            logger.exception("Failed to show notification")
            raise RuntimeError(f"Failed to show notification: {exc}") from exc
