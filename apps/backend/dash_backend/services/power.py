"""PowerService - system power operations: shutdown, restart, lock, sleep, hibernate, log off."""

from __future__ import annotations

import sys
import subprocess
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


class PowerService(Singleton):
    """Manage system power state."""

    async def shutdown(self, force: bool = False, timeout: int = 30) -> dict[str, Any]:
        """Shutdown the system."""
        try:
            if IS_WINDOWS:
                flag = "/f /t" if force else "/t"
                subprocess.run(
                    ["shutdown", "/s", flag, str(timeout)],
                    capture_output=True, timeout=10,
                )
                return {"summary": f"System will shutdown in {timeout} seconds"}
            else:
                subprocess.run(["shutdown", "-h", "+1"], capture_output=True, timeout=10)
                return {"summary": "System will shutdown in 1 minute"}
        except Exception as exc:
            logger.exception("shutdown failed")
            raise RuntimeError(f"Failed to shutdown: {exc}") from exc

    async def restart(self, force: bool = False, timeout: int = 30) -> dict[str, Any]:
        """Restart the system."""
        try:
            if IS_WINDOWS:
                flag = "/f /t" if force else "/t"
                subprocess.run(
                    ["shutdown", "/r", flag, str(timeout)],
                    capture_output=True, timeout=10,
                )
                return {"summary": f"System will restart in {timeout} seconds"}
            else:
                subprocess.run(["shutdown", "-r", "+1"], capture_output=True, timeout=10)
                return {"summary": "System will restart in 1 minute"}
        except Exception as exc:
            logger.exception("restart failed")
            raise RuntimeError(f"Failed to restart: {exc}") from exc

    async def lock(self) -> dict[str, Any]:
        """Lock the workstation."""
        try:
            if IS_WINDOWS:
                import ctypes
                ctypes.windll.user32.LockWorkStation()
                return {"summary": "Workstation locked"}
            else:
                return {"summary": "Lock not supported on this platform"}
        except Exception as exc:
            logger.exception("lock failed")
            raise RuntimeError(f"Failed to lock: {exc}") from exc

    async def sleep(self) -> dict[str, Any]:
        """Put the system to sleep."""
        try:
            if IS_WINDOWS:
                subprocess.run(
                    ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                    capture_output=True, timeout=10,
                )
                return {"summary": "System entering sleep mode"}
            else:
                return {"summary": "Sleep not supported on this platform"}
        except Exception as exc:
            logger.exception("sleep failed")
            raise RuntimeError(f"Failed to sleep: {exc}") from exc

    async def hibernate(self) -> dict[str, Any]:
        """Hibernate the system."""
        try:
            if IS_WINDOWS:
                subprocess.run(
                    ["rundll32.exe", "powrprof.dll,SetSuspendState", "1,1,0"],
                    capture_output=True, timeout=10,
                )
                return {"summary": "System entering hibernate mode"}
            else:
                return {"summary": "Hibernate not supported on this platform"}
        except Exception as exc:
            logger.exception("hibernate failed")
            raise RuntimeError(f"Failed to hibernate: {exc}") from exc

    async def logoff(self, force: bool = False) -> dict[str, Any]:
        """Log off the current user."""
        try:
            if IS_WINDOWS:
                flag = "/f" if force else ""
                subprocess.run(
                    ["shutdown", "/l", flag].strip().split(),
                    capture_output=True, timeout=10,
                )
                return {"summary": "User logged off"}
            else:
                return {"summary": "Logoff not supported on this platform"}
        except Exception as exc:
            logger.exception("logoff failed")
            raise RuntimeError(f"Failed to logoff: {exc}") from exc

    async def abort_shutdown(self) -> dict[str, Any]:
        """Abort a pending shutdown."""
        try:
            if IS_WINDOWS:
                subprocess.run(["shutdown", "/a"], capture_output=True, timeout=10)
                return {"summary": "Pending shutdown aborted"}
            else:
                return {"summary": "Abort not supported on this platform"}
        except Exception as exc:
            logger.exception("abort_shutdown failed")
            raise RuntimeError(f"Failed to abort: {exc}") from exc

