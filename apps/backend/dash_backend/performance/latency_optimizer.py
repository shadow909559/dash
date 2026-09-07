"""Latency Optimizer - Target-specific latency optimization."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LatencyOptimizer:
    TARGETS = {
        "desktop_control": 0.050,
        "voice": 0.100,
        "memory_search": 0.020,
        "tool_execution": 0.100,
    }

    def __init__(self):
        self._latencies: Dict[str, List[float]] = {}
        self._running = False
        self._stats: Dict[str, Dict[str, float]] = {}

    async def start(self) -> None:
        self._running = True
        logger.info("LatencyOptimizer started with targets: %s", self.TARGETS)

    async def stop(self) -> None:
        self._running = False

    def record(self, operation: str, latency: float) -> None:
        if operation not in self._latencies:
            self._latencies[operation] = []
        self._latencies[operation].append(latency)
        if len(self._latencies[operation]) > 100:
            self._latencies[operation] = self._latencies[operation][-100:]

        target = self.TARGETS.get(operation)
        if target and latency > target:
            logger.warning("Latency target exceeded for %s: %.0fms (target: %.0fms)", operation, latency * 1000, target * 1000)

    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        if operation:
            latencies = self._latencies.get(operation, [])
            if not latencies:
                return {"operation": operation, "samples": 0}
            return {
                "operation": operation,
                "samples": len(latencies),
                "avg_ms": round(sum(latencies) / len(latencies) * 1000, 1),
                "min_ms": round(min(latencies) * 1000, 1),
                "max_ms": round(max(latencies) * 1000, 1),
                "p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 1) if len(latencies) > 20 else 0,
                "target_ms": self.TARGETS.get(operation, 0) * 1000,
            }
        return {op: self.get_stats(op) for op in self._latencies}


_latency_optimizer: Optional[LatencyOptimizer] = None


def get_latency_optimizer() -> LatencyOptimizer:
    global _latency_optimizer
    if _latency_optimizer is None:
        _latency_optimizer = LatencyOptimizer()
    return _latency_optimizer
