"""Performance history - rolling history for CPU, GPU, RAM, Network, Battery, Temperature, Storage.

Stores data points in memory for: 1 minute, 5 minutes, 30 minutes, 1 hour.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Rolling history storage
# Each entry: {"timestamp": float, "value": float}
_MAX_ENTRIES = {
    "1m": 60,      # 60 seconds
    "5m": 300,     # 300 seconds (5 min)
    "30m": 1800,   # 1800 seconds (30 min)
    "1h": 3600,    # 3600 seconds (1 hour)
}


class PerformanceHistory:
    """Thread-safe rolling history storage for performance metrics."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, deque[dict[str, float]]]] = {
            "cpu": self._init_metric(),
            "ram": self._init_metric(),
            "gpu": self._init_metric(),
            "network": self._init_metric(),
            "battery": self._init_metric(),
            "temperature": self._init_metric(),
            "storage": self._init_metric(),
        }

    def _init_metric(self) -> dict[str, deque[dict[str, float]]]:
        return {key: deque(maxlen=val) for key, val in _MAX_ENTRIES.items()}

    def record(self, category: str, value: float) -> None:
        """Record a data point for a given category."""
        if category not in self._data:
            return
        now = time.time()
        entry: dict[str, float] = {"timestamp": now, "value": value}
        for period in self._data[category]:
            self._data[category][period].append(entry)

    def record_from_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Record multiple metrics from a system snapshot."""
        try:
            cpu = snapshot.get("cpu", {})
            if cpu.get("percent") is not None:
                self.record("cpu", float(cpu["percent"]))
            if cpu.get("temperature_celsius") is not None:
                self.record("temperature", float(cpu["temperature_celsius"]))
        except Exception:
            pass

        try:
            ram = snapshot.get("ram", {})
            if ram.get("percent") is not None:
                self.record("ram", float(ram["percent"]))
        except Exception:
            pass

        try:
            gpu_list = snapshot.get("gpu", [])
            if gpu_list and gpu_list[0].get("usage_percent") is not None:
                self.record("gpu", float(gpu_list[0]["usage_percent"]))
        except Exception:
            pass

        try:
            net = snapshot.get("network", {})
            if net.get("download_speed_mbps") is not None:
                self.record("network", float(net["download_speed_mbps"]))
        except Exception:
            pass

        try:
            bat = snapshot.get("battery", {})
            if bat.get("percent") is not None:
                self.record("battery", float(bat["percent"]))
        except Exception:
            pass

        try:
            storage = snapshot.get("storage", {})
            if storage.get("used_gb") is not None and storage.get("total_gb") is not None:
                total = float(storage["total_gb"])
                if total > 0:
                    storage_pct = (float(storage["used_gb"]) / total) * 100
                    self.record("storage", storage_pct)
        except Exception:
            pass

    def get_history(self, category: str, period: str = "5m") -> list[dict[str, float]]:
        """Get history for a given category and period.

        Args:
            category: cpu, ram, gpu, network, battery, temperature, storage
            period: 1m, 5m, 30m, 1h

        Returns:
            List of {"timestamp": float, "value": float} entries.
        """
        if category not in self._data:
            return []
        if period not in self._data[category]:
            return []
        return list(self._data[category][period])

    def get_all_history(self) -> dict[str, dict[str, list[dict[str, float]]]]:
        """Get all history data."""
        result: dict[str, dict[str, list[dict[str, float]]]] = {}
        for category, periods in self._data.items():
            result[category] = {}
            for period, entries in periods.items():
                result[category][period] = list(entries)
        return result

    def get_summary(self, category: str, period: str = "5m") -> dict[str, float | None]:
        """Get summary statistics for a category."""
        entries = self.get_history(category, period)
        if not entries:
            return {"min": None, "max": None, "avg": None, "current": None}

        values = [e["value"] for e in entries]
        return {
            "min": round(min(values), 1),
            "max": round(max(values), 1),
            "avg": round(sum(values) / len(values), 1),
            "current": round(values[-1], 1),
        }


# Singleton
_history: PerformanceHistory | None = None


def get_performance_history() -> PerformanceHistory:
    """Get the singleton PerformanceHistory instance."""
    global _history
    if _history is None:
        _history = PerformanceHistory()
    return _history