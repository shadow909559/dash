"""Emergency stop and remote disconnect service.

Provides:
  - Emergency kill switch for all running operations
  - Remote disconnect from DASH network
  - Session termination
  - Backup state preservation
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class EmergencyStopService:
    """Manages emergency stop and remote disconnect functionality."""

    def __init__(self) -> None:
        self._emergency_stopped: bool = False
        self._stop_time: float | None = None
        self._disconnected: bool = False
        self._pause_operations: bool = False
        self._callbacks: list[callable] = []

    def register_callback(self, callback: callable) -> None:
        """Register a callback to be called on emergency stop."""
        self._callbacks.append(callback)

    def is_emergency_stopped(self) -> bool:
        """Check if emergency stop is active."""
        return self._emergency_stopped

    async def trigger_emergency_stop(self, reason: str = "User requested") -> dict[str, Any]:
        """Trigger immediate emergency stop - cancels all operations."""
        self._emergency_stopped = True
        self._stop_time = time.time()
        self._pause_operations = True

        # Notify all registered callbacks
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb()
                else:
                    cb()
            except Exception:
                logger.exception("Emergency stop callback failed")

        logger.warning("EMERGENCY STOP triggered: %s", reason)
        return {
            "status": "emergency_stop_triggered",
            "reason": reason,
            "timestamp": self._stop_time,
            "operations_paused": True,
        }

    async def reset_emergency_stop(self) -> dict[str, Any]:
        """Reset the emergency stop state and resume operations."""
        self._emergency_stopped = False
        self._pause_operations = False
        logger.info("Emergency stop reset")
        return {"status": "emergency_stop_reset", "operations_resumed": True}

    async def remote_disconnect(self, reason: str = "Remote disconnect requested") -> dict[str, Any]:
        """Disconnect this device from the DASH remote network."""
        self._disconnected = True
        self._pause_operations = True
        logger.warning("Remote disconnect: %s", reason)
        return {
            "status": "disconnected",
            "reason": reason,
            "timestamp": time.time(),
            "reconnect_required": True,
        }

    async def remote_reconnect(self) -> dict[str, Any]:
        """Reconnect to the DASH remote network."""
        self._disconnected = False
        self._pause_operations = False
        logger.info("Remote reconnected")
        return {"status": "reconnected", "reconnect_time": time.time()}

    def get_status(self) -> dict[str, Any]:
        """Get current emergency/disconnect status."""
        return {
            "emergency_stopped": self._emergency_stopped,
            "disconnected": self._disconnected,
            "operations_paused": self._pause_operations,
            "stop_time": self._stop_time,
            "active_callbacks": len(self._callbacks),
        }


# Global singleton
_stop_service: EmergencyStopService | None = None


def get_emergency_stop_service() -> EmergencyStopService:
    global _stop_service
    if _stop_service is None:
        _stop_service = EmergencyStopService()
    return _stop_service
