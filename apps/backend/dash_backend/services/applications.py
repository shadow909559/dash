"""ApplicationService - launch, close, kill, and restart applications."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


class ApplicationService(Singleton):
    """Manage application lifecycle."""

    async def launch(
        self, path: str, args: list[str] | None = None
    ) -> dict[str, Any]:
        """Launch an application."""
        if not path:
            raise ValueError("path is required")
        try:
            if IS_WINDOWS:
                os.startfile(path)
                return {"summary": f"Launched {path}"}
            else:
                cmd = [path] + (args or [])
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return {
                    "summary": f"Launched {path}",
                    "pid": proc.pid,
                }
        except Exception as exc:
            logger.exception("Failed to launch %s", path)
            raise RuntimeError(f"Failed to launch: {exc}") from exc

    async def close(self, name: str) -> dict[str, Any]:
        """Close an application by name."""
        if not name:
            raise ValueError("name is required")
        try:
            if IS_WINDOWS:
                subprocess.run(
                    ["taskkill", "/IM", name, "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                subprocess.run(
                    ["pkill", "-f", name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            return {"summary": f"Closed {name}"}
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Timed out closing {name}")
        except Exception as exc:
            logger.exception("Failed to close %s", name)
            raise RuntimeError(f"Failed to close: {exc}") from exc

    async def kill(self, name: str) -> dict[str, Any]:
        """Kill a process by name."""
        return await self.close(name)

    async def restart(
        self, name: str, path: str | None = None
    ) -> dict[str, Any]:
        """Restart an application."""
        await self.close(name)
        if path:
            await self.launch(path)
        return {"summary": f"Restarted {name}"}

    async def list_processes(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List running processes."""
        import psutil

        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if len(processes) >= limit:
                break
        return processes
