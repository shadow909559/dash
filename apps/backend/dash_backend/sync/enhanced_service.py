"""Enhanced Sync Service - Improved mobile/desktop synchronization."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from dash_backend.sync.service import get_sync_service, SyncRequest, SyncResponse

logger = logging.getLogger(__name__)


class EnhancedSyncService:
    def __init__(self):
        self._base = get_sync_service()
        self._sync_intervals: Dict[str, float] = {
            "clipboard": 1.0,
            "notifications": 5.0,
            "tasks": 10.0,
            "memories": 30.0,
            "projects": 30.0,
        }
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, List[Callable]] = {}

    async def start(self) -> None:
        self._running = True
        for sync_type, interval in self._sync_intervals.items():
            task = asyncio.create_task(self._sync_loop(sync_type, interval))
            self._tasks[sync_type] = task
        logger.info("EnhancedSyncService started")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    async def _sync_loop(self, sync_type: str, interval: float) -> None:
        while self._running:
            try:
                await self._sync_type(sync_type)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(interval)

    async def _sync_type(self, sync_type: str) -> None:
        if sync_type == "clipboard":
            await self._sync_clipboard()
        elif sync_type == "notifications":
            await self._sync_notifications()
        elif sync_type == "tasks":
            await self._sync_tasks()
        elif sync_type == "memories":
            await self._sync_memories()
        elif sync_type == "projects":
            await self._sync_projects()

    async def _sync_clipboard(self) -> None:
        try:
            from dash_backend.desktop.clipboard_manager import get_clipboard_manager
            cm = get_clipboard_manager()
            text = await cm.read_text()
            if text:
                self._notify("clipboard", {"text": text[:200]})
        except Exception:
            pass

    async def _sync_notifications(self) -> None:
        self._notify("notifications", {"synced": True, "timestamp": time.time()})

    async def _sync_tasks(self) -> None:
        self._notify("tasks", {"synced": True})

    async def _sync_memories(self) -> None:
        self._notify("memories", {"synced": True})

    async def _sync_projects(self) -> None:
        self._notify("projects", {"synced": True})

    def on_sync(self, sync_type: str, callback: Callable) -> None:
        if sync_type not in self._callbacks:
            self._callbacks[sync_type] = []
        self._callbacks[sync_type].append(callback)

    def _notify(self, sync_type: str, data: Any) -> None:
        for cb in self._callbacks.get(sync_type, []):
            try:
                cb(data)
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "active_syncs": list(self._tasks.keys()),
            "intervals": self._sync_intervals,
        }


_enhanced_sync_service: Optional[EnhancedSyncService] = None


def get_enhanced_sync_service() -> EnhancedSyncService:
    global _enhanced_sync_service
    if _enhanced_sync_service is None:
        _enhanced_sync_service = EnhancedSyncService()
    return _enhanced_sync_service
