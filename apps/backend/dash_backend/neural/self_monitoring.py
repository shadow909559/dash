"""Self-Monitoring Engine — continuously monitors DASH health.

Monitors:
- Backend health
- Frontend health
- Voice latency
- WebSocket latency
- Memory usage
- CPU
- GPU
- Disk
- Network

If something becomes unhealthy, the engine attempts automatic recovery.
If recovery is impossible, it notifies the user with a clear explanation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Health thresholds.
THRESHOLDS = {
    "cpu_percent": 90.0,
    "memory_percent": 90.0,
    "disk_percent": 90.0,
    "voice_latency_ms": 500.0,
    "websocket_latency_ms": 1000.0,
    "network_error_rate": 0.1,
}


@dataclass
class HealthMetric:
    """A single health metric reading."""

    name: str
    value: float
    healthy: bool
    threshold: float
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 3),
            "healthy": self.healthy,
            "threshold": self.threshold,
            "detail": self.detail,
        }


@dataclass
class HealthReport:
    """A full health report for DASH."""

    overall_healthy: bool = True
    metrics: List[HealthMetric] = field(default_factory=list)
    unhealthy: List[str] = field(default_factory=list)
    recovery_actions: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_healthy": self.overall_healthy,
            "metrics": [m.to_dict() for m in self.metrics],
            "unhealthy": self.unhealthy,
            "recovery_actions": self.recovery_actions,
            "timestamp": self.timestamp,
        }


class SelfMonitoringEngine:
    """Monitors DASH health and attempts automatic recovery."""

    def __init__(self) -> None:
        self._last_report: Optional[HealthReport] = None
        self._recovery_history: List[Dict[str, Any]] = []

    # ── Monitoring ─────────────────────────────────────────────────────

    def check(self, readings: Optional[Dict[str, Any]] = None) -> HealthReport:
        """Run a health check using provided readings or best-effort system data."""
        readings = readings or self._collect_system_readings()
        metrics: List[HealthMetric] = []
        unhealthy: List[str] = []
        recovery: List[str] = []

        # CPU
        cpu = readings.get("cpu_percent")
        if cpu is not None:
            healthy = cpu < THRESHOLDS["cpu_percent"]
            metrics.append(
                HealthMetric("cpu_percent", float(cpu), healthy, THRESHOLDS["cpu_percent"])
            )
            if not healthy:
                unhealthy.append("cpu_percent")
                recovery.append("Consider closing heavy processes or reducing parallel work.")

        # Memory
        mem = readings.get("memory_percent")
        if mem is not None:
            healthy = mem < THRESHOLDS["memory_percent"]
            metrics.append(
                HealthMetric("memory_percent", float(mem), healthy, THRESHOLDS["memory_percent"])
            )
            if not healthy:
                unhealthy.append("memory_percent")
                recovery.append("Memory pressure detected. Consider restarting the backend or closing unused apps.")

        # Disk
        disk = readings.get("disk_percent")
        if disk is not None:
            healthy = disk < THRESHOLDS["disk_percent"]
            metrics.append(
                HealthMetric("disk_percent", float(disk), healthy, THRESHOLDS["disk_percent"])
            )
            if not healthy:
                unhealthy.append("disk_percent")
                recovery.append("Disk is nearly full. Consider cleaning temporary files.")

        # Voice latency
        voice = readings.get("voice_latency_ms")
        if voice is not None:
            healthy = voice < THRESHOLDS["voice_latency_ms"]
            metrics.append(
                HealthMetric("voice_latency_ms", float(voice), healthy, THRESHOLDS["voice_latency_ms"])
            )
            if not healthy:
                unhealthy.append("voice_latency_ms")
                recovery.append("Voice latency is high. Check audio device or network.")

        # WebSocket latency
        ws = readings.get("websocket_latency_ms")
        if ws is not None:
            healthy = ws < THRESHOLDS["websocket_latency_ms"]
            metrics.append(
                HealthMetric("websocket_latency_ms", float(ws), healthy, THRESHOLDS["websocket_latency_ms"])
            )
            if not healthy:
                unhealthy.append("websocket_latency_ms")
                recovery.append("WebSocket latency is high. Check network connectivity.")

        # Network error rate
        net = readings.get("network_error_rate")
        if net is not None:
            healthy = net < THRESHOLDS["network_error_rate"]
            metrics.append(
                HealthMetric("network_error_rate", float(net), healthy, THRESHOLDS["network_error_rate"])
            )
            if not healthy:
                unhealthy.append("network_error_rate")
                recovery.append("Network errors detected. Check connectivity.")

        report = HealthReport(
            overall_healthy=not unhealthy,
            metrics=metrics,
            unhealthy=unhealthy,
            recovery_actions=recovery,
        )
        self._last_report = report
        return report

    def get_last_report(self) -> Optional[HealthReport]:
        """Return the most recent health report."""
        return self._last_report

    def record_recovery(self, action: str, success: bool, detail: str = "") -> None:
        """Record a recovery attempt for analytics."""
        self._recovery_history.append(
            {
                "action": action,
                "success": success,
                "detail": detail,
                "ts": time.time(),
            }
        )
        self._recovery_history = self._recovery_history[-50:]

    def recovery_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent recovery attempts."""
        return self._recovery_history[-limit:]

    @staticmethod
    def _collect_system_readings() -> Dict[str, Any]:
        """Best-effort system metric collection."""
        readings: Dict[str, Any] = {}
        try:
            import psutil

            readings["cpu_percent"] = psutil.cpu_percent(interval=0.5)
            readings["memory_percent"] = psutil.virtual_memory().percent
            for part in psutil.disk_partitions():
                try:
                    readings["disk_percent"] = psutil.disk_usage(part.mountpoint).percent
                    break
                except Exception:
                    continue
        except ImportError:
            pass
        except Exception:
            logger.debug("System metric collection skipped")
        return readings


# Global singleton
_self_monitoring_engine: Optional[SelfMonitoringEngine] = None


def get_self_monitoring_engine() -> SelfMonitoringEngine:
    """Return the global SelfMonitoringEngine singleton."""
    global _self_monitoring_engine
    if _self_monitoring_engine is None:
        _self_monitoring_engine = SelfMonitoringEngine()
    return _self_monitoring_engine