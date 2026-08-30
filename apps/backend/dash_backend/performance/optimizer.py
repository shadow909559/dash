"""Performance Optimizer - System performance monitoring and optimization."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}
        self._thresholds: Dict[str, float] = {
            "desktop_control_ms": 50.0,
            "voice_ms": 100.0,
            "memory_search_ms": 20.0,
            "tool_execution_ms": 500.0,
        }
        self._callbacks: List[Callable] = []

    async def start(self) -> None:
        """Start the performance optimizer. Initialization is in __init__."""
        pass

    async def stop(self) -> None:
        """Stop the performance optimizer. Currently a no-op."""
        pass

    def record(self, metric: str, value: float) -> None:
        if metric not in self._metrics:
            self._metrics[metric] = []
        self._metrics[metric].append(value)
        if len(self._metrics[metric]) > 100:
            self._metrics[metric] = self._metrics[metric][-100:]
        threshold = self._thresholds.get(metric)
        if threshold and value > threshold:
            for cb in self._callbacks:
                try:
                    cb({"metric": metric, "value": value, "threshold": threshold, "exceeded": True})
                except Exception:
                    pass

    def average(self, metric: str) -> float:
        values = self._metrics.get(metric, [])
        if not values:
            return 0.0
        return sum(values) / len(values)

    def percentile(self, metric: str, p: float = 95.0) -> float:
        values = sorted(self._metrics.get(metric, []))
        if not values:
            return 0.0
        idx = int(len(values) * p / 100)
        return values[min(idx, len(values) - 1)]

    def set_threshold(self, metric: str, value: float) -> None:
        self._thresholds[metric] = value

    def on_violation(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def get_report(self) -> Dict[str, Any]:
        report = {}
        for metric in self._metrics:
            report[metric] = {
                "avg": round(self.average(metric), 2),
                "p95": round(self.percentile(metric, 95), 2),
                "p99": round(self.percentile(metric, 99), 2),
                "count": len(self._metrics[metric]),
            }
        return report

    def get_stats(self) -> Dict[str, Any]:
        return self.get_report()


_performance_optimizer: Optional[PerformanceOptimizer] = None


def get_performance_optimizer() -> PerformanceOptimizer:
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer
