"""System Monitor Agent - Autonomous system health monitoring."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SystemMonitorAgent:
    def __init__(self, interval: float = 60.0):
        self._interval = interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []
        self._thresholds = {"cpu": 90.0, "memory": 90.0, "disk": 90.0, "battery": 20.0}

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("SystemMonitorAgent started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def on_alert(self, cb: Callable) -> None:
        self._callbacks.append(cb)

    def set_threshold(self, metric: str, value: float) -> None:
        if metric in self._thresholds:
            self._thresholds[metric] = value

    async def _loop(self) -> None:
        while self._running:
            try:
                import psutil
                alerts = []
                cpu = psutil.cpu_percent(interval=1)
                if cpu > self._thresholds["cpu"]:
                    alerts.append({"type": "cpu", "value": cpu, "threshold": self._thresholds["cpu"]})
                mem = psutil.virtual_memory()
                if mem.percent > self._thresholds["memory"]:
                    alerts.append({"type": "memory", "value": mem.percent, "threshold": self._thresholds["memory"]})
                for p in psutil.disk_partitions():
                    try:
                        u = psutil.disk_usage(p.mountpoint)
                        if u.percent > self._thresholds["disk"]:
                            alerts.append({"type": "disk", "value": u.percent, "threshold": self._thresholds["disk"], "mount": p.mountpoint})
                    except Exception:
                        continue
                bat = getattr(psutil, "sensors_battery", lambda: None)()
                if bat and bat.percent < self._thresholds["battery"] and not bat.power_plugged:
                    alerts.append({"type": "battery", "value": bat.percent, "threshold": self._thresholds["battery"]})
                for a in alerts:
                    for cb in self._callbacks:
                        try:
                            cb(a)
                        except Exception:
                            pass
            except ImportError:
                pass
            except Exception:
                pass
            await asyncio.sleep(self._interval)


_system_monitor_agent: Optional[SystemMonitorAgent] = None


def get_system_monitor_agent() -> SystemMonitorAgent:
    global _system_monitor_agent
    if _system_monitor_agent is None:
        _system_monitor_agent = SystemMonitorAgent()
    return _system_monitor_agent
