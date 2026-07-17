"""Simple in-process scheduler for automations.

This scheduler is intentionally lightweight: it runs inside the API
process, periodically polling enabled automations and executing them
when their schedule indicates they are due. For production, a dedicated
worker/cron system is recommended.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.session import AsyncSessionLocal
from dash_backend.automation import service
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class AutomationScheduler:
    """In-memory scheduler that periodically polls enabled automations."""

    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval
        self._task: Optional[asyncio.Task] = None
        # track last run times in-memory
        self._last_run: Dict[str, datetime] = {}
        self._stopping = False

    async def _run_once(self) -> None:
        async with AsyncSessionLocal() as session:  # type: AsyncSession
            try:
                autos = await service.fetch_enabled_automations(session)
            except Exception:
                logger.exception("Failed to fetch automations")
                return

            now = datetime.utcnow()
            for a in autos:
                try:
                    key = str(a.id)
                    last = self._last_run.get(key)
                    # Only 'interval' trigger is supported for automatic runs here.
                    if a.trigger_type == "interval":
                        try:
                            seconds = int(a.schedule)
                        except Exception:
                            logger.warning("Invalid interval for automation %s: %s", a.id, a.schedule)
                            continue

                        if last is None or (now - last) >= timedelta(seconds=seconds):
                            logger.info("Executing automation %s (interval=%s)", a.id, a.schedule)
                            res = await service.execute_automation(session, a)
                            logger.info("Automation %s result: %s", a.id, res.get("status"))
                            self._last_run[key] = now
                    elif a.trigger_type == "cron":
                        # Very small cron-like support: schedule "HH:MM" (UTC) daily
                        try:
                            hh, mm = a.schedule.split(":")
                            run_time = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
                        except Exception:
                            logger.warning("Invalid cron schedule for automation %s: %s", a.id, a.schedule)
                            continue

                        # If scheduled time is in the future for today, skip; otherwise if last run is before today at run_time, run
                        if now >= run_time:
                            last_run = last or datetime.min
                            if last_run < run_time:
                                logger.info("Executing cron automation %s scheduled at %s", a.id, a.schedule)
                                res = await service.execute_automation(session, a)
                                logger.info("Automation %s result: %s", a.id, res.get("status"))
                                self._last_run[key] = now
                        else:
                            # Not time yet
                            continue
                    else:
                        # Unsupported trigger types ignored
                        continue
                except Exception:
                    logger.exception("Failed to run automation %s", a.id)

    async def _loop(self) -> None:
        while not self._stopping:
            await self._run_once()
            await asyncio.sleep(self.poll_interval)

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._loop())
        logger.info("Automation scheduler started with poll interval %s seconds", self.poll_interval)

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Automation scheduler stopped")


# Singleton scheduler instance (import-safe)
_scheduler: Optional[AutomationScheduler] = None


def get_scheduler() -> AutomationScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutomationScheduler()
    return _scheduler
