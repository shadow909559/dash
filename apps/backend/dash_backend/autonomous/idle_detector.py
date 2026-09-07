"""Idle Detector - Detect user idle time for autonomous actions."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class IdleDetector:
    def __init__(self, idle_threshold: float = 300.0, check_interval: float = 10.0):
        self._idle_threshold = idle_threshold
        self._check_interval = check_interval
        self._last_activity = time.time()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []

    async def start(self) -> None:
        self._running = True
        self._last_activity = time.time()
        self._task = asyncio.create_task(self._loop())
        logger.info("IdleDetector started (threshold=%ss)", self._idle_threshold)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def register_activity(self) -> None:
        self._last_activity = time.time()

    def on_idle(self, cb: Callable) -> None:
        self._callbacks.append(cb)

    async def _loop(self) -> None:
        was_idle = False
        while self._running:
            try:
                elapsed = time.time() - self._last_activity
                is_idle = elapsed > self._idle_threshold
                if is_idle and not was_idle:
                    for cb in self._callbacks:
                        try:
                            cb(elapsed)
                        except Exception:
                            pass
                was_idle = is_idle
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self._check_interval)


_idle_detector: Optional[IdleDetector] = None


def get_idle_detector() -> IdleDetector:
    global _idle_detector
    if _idle_detector is None:
        _idle_detector = IdleDetector()
    return _idle_detector
