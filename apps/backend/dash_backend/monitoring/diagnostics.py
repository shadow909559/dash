"""DASH Diagnostics Service.

Aggregates health checks across the whole system: backend process, memory,
CPU, GPU, RAM, disk, network, voice, WebSocket, agents, and the Android
companion. Used by the developer-only health dashboard and automatic repair
routines.

This module is ADDITIVE and does not modify existing performance/security code.
"""

from __future__ import annotations

import gc
import os
import platform
import shutil
import time
from typing import Any, Dict, Optional

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

try:
    import psutil
    HAS_PSUTIL = True
except Exception:  # pragma: no cover
    HAS_PSUTIL = False


class DiagnosticsService:
    """Collects and aggregates system + DASH health metrics."""

    def __init__(self) -> None:
        self._start_time = time.time()

    # ── Resource helpers ────────────────────────────────────────

    def uptime(self) -> float:
        return time.time() - self._start_time

    def _cpu(self) -> Dict[str, Any]:
        if HAS_PSUTIL:
            return {
                "percent": psutil.cpu_percent(interval=0.1),
                "cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
                "load_avg": list(os.getloadavg()) if hasattr(os, "getloadavg") else [],
            }
        return {"percent": 0.0}

    def _memory(self) -> Dict[str, Any]:
        if HAS_PSUTIL:
            vm = psutil.virtual_memory()
            return {
                "total": vm.total,
                "used": vm.used,
                "available": vm.available,
                "percent": vm.percent,
            }
        return {"percent": 0.0}

    def _battery(self) -> Dict[str, Any]:
        if HAS_PSUTIL:
            try:
                batt = psutil.sensors_battery()
                if batt is not None:
                    return {
                        "percent": round(batt.percent, 1),
                        "plugged": bool(batt.power_plugged),
                        "available": True,
                    }
            except Exception:
                pass
        return {"available": False, "percent": None}

    def _gpu(self) -> Dict[str, Any]:
        # Best-effort: no direct GPU API in pure Python. Report 0 / unknown so
        # the dashboard can still show a GPU tile without hard-dependency.
        return {"available": False, "percent": 0.0, "note": "GPU metrics require a profiler build"}

    def _disk(self) -> Dict[str, Any]:
        if HAS_PSUTIL:
            try:
                usage = psutil.disk_usage(os.getcwd())
                return {
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
            except Exception:
                pass
        # Fallback using shutil
        try:
            usage = shutil.disk_usage(os.getcwd())
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception:
            return {"percent": 0.0}

    def _network(self) -> Dict[str, Any]:
        if HAS_PSUTIL:
            io = psutil.net_io_counters()
            return {
                "bytes_sent": io.bytes_sent,
                "bytes_recv": io.bytes_recv,
                "packets_sent": io.packets_sent,
                "packets_recv": io.packets_recv,
            }
        return {}

    def _python(self) -> Dict[str, Any]:
        return {
            "version": platform.python_version(),
            "platform": platform.platform(),
            "process": os.getpid(),
            "gc_objects": len(gc.get_objects()),
        }

    # ── Component health (best-effort, non-blocking) ────────────

    async def _backend_health(self) -> Dict[str, Any]:
        settings = get_settings()
        return {
            "status": "ok",
            "service": settings.app_name,
            "env": settings.env,
            "debug": settings.debug,
            "uptime": round(self.uptime(), 2),
        }

    async def _voice_health(self) -> Dict[str, Any]:
        # Voice is a separate service; report status via a lightweight probe.
        try:
            from dash_backend.voice.service import get_voice_service  # type: ignore
            svc = get_voice_service()
            status = "ok"
            details = {}
            if hasattr(svc, "is_ready"):
                try:
                    ready = svc.is_ready()
                    status = "ok" if ready else "degraded"
                    details["ready"] = bool(ready)
                except Exception:
                    pass
            return {"status": status, "details": details}
        except Exception:
            # Voice module may not expose a singleton; treat as unknown.
            return {"status": "unknown", "details": {"note": "voice service not probed"}}

    async def _agents_health(self) -> Dict[str, Any]:
        try:
            from dash_backend.agents.ecosystem import get_agent_registry
            registry = get_agent_registry()
            enabled = registry.enabled_keys()
            return {
                "status": "ok",
                "enabled_count": len(enabled),
                "enabled": enabled,
            }
        except Exception as exc:
            return {"status": "unknown", "details": {"error": str(exc)}}

    async def _android_health(self) -> Dict[str, Any]:
        try:
            from dash_backend.companion.hub import get_companion_hub
            hub = get_companion_hub()
            devices = hub.list_devices()
            return {
                "status": "ok" if devices else "idle",
                "connected": len(devices),
                "devices": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "last_seen": d.last_seen,
                    }
                    for d in devices
                ],
            }
        except Exception as exc:
            return {"status": "unknown", "details": {"error": str(exc)}}

    async def _websocket_health(self) -> Dict[str, Any]:
        # Best-effort: WS connection tracking is in the WS route; report counts if available.
        try:
            from dash_backend.api.routes.websocket import connection_manager  # type: ignore
            active = connection_manager.active_connections_count() if hasattr(
                connection_manager, "active_connections_count"
            ) else None
            return {"status": "ok", "active_connections": active}
        except Exception:
            return {"status": "unknown", "details": {"note": "ws manager not exposed"}}

    # ── Public API ──────────────────────────────────────────────

    async def summary(self) -> Dict[str, Any]:
        """Return a compact health summary for the health dashboard."""
        cpu = self._cpu()
        mem = self._memory()
        disk = self._disk()

        backend = await self._backend_health()
        voice = await self._voice_health()
        agents = await self._agents_health()
        android = await self._android_health()
        ws = await self._websocket_health()

        return {
            "status": "ok",
            "timestamp": time.time(),
            "components": {
                "backend": backend,
                "voice": voice,
                "websocket": ws,
                "agents": agents,
                "android": android,
            },
            "resources": {
                "cpu": cpu,
                "memory": mem,
                "gpu": self._gpu(),
                "disk": disk,
                "network": self._network(),
                "battery": self._battery(),
            },
            "python": self._python(),
        }

    async def diagnostics(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Return detailed diagnostics. Sensitive details gated by include_sensitive."""
        summary = await self.summary()
        summary["resources"]["memory"]["gc_objects"] = len(gc.get_objects())
        summary["kwargs"] = {"include_sensitive": include_sensitive}
        return summary


_service: Optional[DiagnosticsService] = None


def get_diagnostics_service() -> DiagnosticsService:
    """Return the singleton DiagnosticsService instance."""
    global _service
    if _service is None:
        _service = DiagnosticsService()
    return _service
