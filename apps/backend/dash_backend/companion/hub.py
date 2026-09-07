"""Companion Hub — registry of connected Android companions.

The hub tracks devices that register via the WebSocket (or a lightweight
heartbeat endpoint). It keeps the desktop able to discover the phone and route
commands to it without manual IP entry. Best-effort, in-memory, thread-safe.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# A companion is considered stale if it hasn't pinged for this long.
STALE_AFTER_SECONDS = 60.0


@dataclass
class CompanionDevice:
    """A single connected Android companion."""

    id: str
    name: str = "DASH Companion"
    transport: str = "wifi"  # usb | wifi | local | relay
    host: str = ""
    platform: str = "android"
    last_seen: float = field(default_factory=time.time)
    capabilities: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_seen = time.time()

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.last_seen) > STALE_AFTER_SECONDS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "transport": self.transport,
            "host": self.host,
            "platform": self.platform,
            "last_seen": self.last_seen,
            "capabilities": self.capabilities,
            "state": self.state,
            "stale": self.is_stale,
        }


class CompanionHub:
    """Thread-safe registry of companion devices."""

    def __init__(self) -> None:
        self._devices: Dict[str, CompanionDevice] = {}
        self._lock = threading.Lock()
        self._prune_task: Optional[asyncio.Task] = None

    # ── Registration ────────────────────────────────────────────

    def register(self, device_id: str, **kwargs: Any) -> CompanionDevice:
        with self._lock:
            device = self._devices.get(device_id)
            if device is None:
                device = CompanionDevice(id=device_id, **kwargs)
                self._devices[device_id] = device
                logger.info("[Companion] Registered device '%s' (%s)", device_id, device.transport)
            else:
                device.name = kwargs.get("name", device.name)
                device.transport = kwargs.get("transport", device.transport)
                device.host = kwargs.get("host", device.host)
                device.capabilities = kwargs.get("capabilities", device.capabilities)
                device.touch()
                logger.info("[Companion] Device '%s' updated", device_id)
            return device

    def unregister(self, device_id: str) -> bool:
        with self._lock:
            existed = self._devices.pop(device_id, None) is not None
            if existed:
                logger.info("[Companion] Device '%s' unregistered", device_id)
            return existed

    def touch(self, device_id: str) -> bool:
        with self._lock:
            device = self._devices.get(device_id)
            if device is None:
                return False
            device.touch()
            return True

    # ── Query ───────────────────────────────────────────────────

    def get(self, device_id: str) -> Optional[CompanionDevice]:
        with self._lock:
            return self._devices.get(device_id)

    def list_devices(self) -> List[CompanionDevice]:
        with self._lock:
            return list(self._devices.values())

    def list_alive(self) -> List[CompanionDevice]:
        with self._lock:
            return [d for d in self._devices.values() if not d.is_stale]

    def count(self) -> int:
        with self._lock:
            return len(self._devices)

    # ── Async helpers ───────────────────────────────────────────

    async def _prune_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            stale = self.prune_stale()
            if stale:
                logger.info("[Companion] Pruned %d stale device(s)", stale)

    def prune_stale(self) -> int:
        with self._lock:
            stale_ids = [did for did, d in self._devices.items() if d.is_stale]
            for did in stale_ids:
                self._devices.pop(did, None)
            return len(stale_ids)

    def start_pruning(self) -> None:
        if self._prune_task is None or self._prune_task.done():
            self._prune_task = asyncio.ensure_future(self._prune_loop())

    def stop_pruning(self) -> None:
        if self._prune_task:
            self._prune_task.cancel()
            self._prune_task = None


_hub: Optional[CompanionHub] = None


def get_companion_hub() -> CompanionHub:
    global _hub
    if _hub is None:
        _hub = CompanionHub()
    return _hub
