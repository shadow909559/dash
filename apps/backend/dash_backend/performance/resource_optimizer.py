"""Resource Optimizer - CPU, RAM, disk IO, and network call reduction."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResourceOptimizer:
    def __init__(self):
        self._debounce_timers: Dict[str, float] = {}
        self._throttle_intervals: Dict[str, float] = {}
        self._last_calls: Dict[str, float] = {}
        self._metrics = {"debounced": 0, "throttled": 0}

    def debounce(self, key: str, wait: float = 0.3) -> bool:
        now = asyncio.get_event_loop().time()
        last = self._debounce_timers.get(key, 0.0)
        if now - last < wait:
            self._metrics["debounced"] += 1
            return False
        self._debounce_timers[key] = now
        return True

    def throttle(self, key: str, interval: float = 1.0) -> bool:
        now = asyncio.get_event_loop().time()
        last = self._last_calls.get(key, 0.0)
        if now - last < interval:
            self._metrics["throttled"] += 1
            return False
        self._last_calls[key] = now
        return True

    def set_throttle_interval(self, key: str, interval: float) -> None:
        self._throttle_intervals[key] = interval

    def get_metrics(self) -> Dict[str, Any]:
        return {**self._metrics}


_resource_optimizer: Optional[ResourceOptimizer] = None


def get_resource_optimizer() -> ResourceOptimizer:
    global _resource_optimizer
    if _resource_optimizer is None:
        _resource_optimizer = ResourceOptimizer()
    return _resource_optimizer
