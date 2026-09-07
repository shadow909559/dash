"""Reminder Service - Autonomous reminder management."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Reminder:
    id: str = ""
    title: str = ""
    description: str = ""
    trigger_at: float = 0.0
    repeat_interval: Optional[float] = None
    is_active: bool = True
    created_at: float = 0.0
    last_fired: Optional[float] = None
    category: str = "general"


class ReminderService:
    def __init__(self):
        self._reminders: Dict[str, Reminder] = {}
        self._callbacks: List[Callable] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ReminderService started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def set(self, title: str, seconds: float, description: str = "",
                  repeat: Optional[float] = None, category: str = "general") -> str:
        rid = str(uuid.uuid4())
        self._reminders[rid] = Reminder(
            id=rid, title=title, description=description,
            trigger_at=time.time() + seconds, repeat_interval=repeat, category=category,
        )
        return rid

    async def cancel(self, reminder_id: str) -> bool:
        r = self._reminders.get(reminder_id)
        if r:
            r.is_active = False
            return True
        return False

    def on_reminder(self, cb: Callable) -> None:
        self._callbacks.append(cb)

    def list(self, active_only: bool = True) -> List[Reminder]:
        if active_only:
            return [r for r in self._reminders.values() if r.is_active]
        return list(self._reminders.values())

    async def _loop(self) -> None:
        while self._running:
            try:
                now = time.time()
                for r in list(self._reminders.values()):
                    if not r.is_active:
                        continue
                    if now >= r.trigger_at:
                        for cb in self._callbacks:
                            try:
                                cb(r)
                            except Exception:
                                pass
                        if r.repeat_interval:
                            r.trigger_at = now + r.repeat_interval
                        else:
                            r.is_active = False
                        r.last_fired = now
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5.0)


_reminder_service: Optional[ReminderService] = None


def get_reminder_service() -> ReminderService:
    global _reminder_service
    if _reminder_service is None:
        _reminder_service = ReminderService()
    return _reminder_service
