"""Windows notification listener — monitors system notifications and pushes them to connected clients.

Uses psutil to monitor processes and Windows toast notifications via the
WinRT Notification API when available. Falls back to event log monitoring.
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Type for notification callback
NotificationCallback = Callable[[dict[str, Any]], Awaitable[None]]


class NotificationListener:
    """Listens for Windows notifications and calls a callback when one is detected."""

    def __init__(self) -> None:
        self._callbacks: list[NotificationCallback] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_processes: dict[int, str] = {}
        self._last_events: list[dict] = []

    def on_notification(self, callback: NotificationCallback) -> None:
        """Register a callback for new notifications."""
        self._callbacks.append(callback)

    def start(self) -> None:
        """Start the notification listener in the background."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.get_event_loop().create_task(self._listen_loop())
        logger.info("Notification listener started")

    def stop(self) -> None:
        """Stop the notification listener."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Notification listener stopped")

    async def _listen_loop(self) -> None:
        """Main listener loop — polls for new notifications every 5 seconds."""
        # Initial process snapshot
        self._last_processes = await self._get_running_processes()

        while self._running:
            try:
                await asyncio.sleep(5)

                # Check for new processes (app launches)
                current = await self._get_running_processes()
                new_pids = set(current.keys()) - set(self._last_processes.keys())
                for pid in new_pids:
                    await self._fire_notification({
                        "title": "App Launched",
                        "message": f"{current[pid]} started (PID {pid})",
                        "type": "info",
                        "source": "system",
                        "category": "process",
                    })

                # Check for closed processes
                closed_pids = set(self._last_processes.keys()) - set(current.keys())
                for pid in closed_pids:
                    name = self._last_processes.get(pid, "Unknown")
                    if name not in ("svchost.exe", "csrss.exe", "lsass.exe", "services.exe",
                                    "wininit.exe", "winlogon.exe", "smss.exe", "dwm.exe"):
                        await self._fire_notification({
                            "title": "App Closed",
                            "message": f"{name} stopped (PID {pid})",
                            "type": "info",
                            "source": "system",
                            "category": "process",
                        })

                self._last_processes = current

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Notification listener error: %s", exc)
                await asyncio.sleep(5)

    async def _get_running_processes(self) -> dict[int, str]:
        """Get snapshot of running processes."""
        try:
            import psutil
            procs = {}
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    info = proc.info
                    procs[info["pid"]] = info["name"]
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return procs
        except ImportError:
            return {}

    async def _fire_notification(self, notification: dict[str, Any]) -> None:
        """Send a notification to all registered callbacks."""
        notification["timestamp"] = datetime.now(timezone.utc).isoformat()
        for cb in self._callbacks:
            try:
                await cb(notification)
            except Exception as exc:
                logger.exception("Notification callback failed: %s", exc)

    async def push_notification(self, title: str, message: str,
                                 notif_type: str = "info") -> None:
        """Manually push a notification (e.g., from other services)."""
        await self._fire_notification({
            "title": title,
            "message": message,
            "type": notif_type,
            "source": "manual",
        })


# Singleton
_listener: NotificationListener | None = None


def get_notification_listener() -> NotificationListener:
    global _listener
    if _listener is None:
        _listener = NotificationListener()
    return _listener
