"""Trusted device list service for managing authorized remote connections."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class TrustedDeviceService:
    """Manages a list of trusted devices that can connect remotely.

    Persists device trust information to a JSON file.
    """

    def __init__(self, storage_path: str | None = None) -> None:
        if storage_path:
            self._storage = Path(storage_path)
        else:
            self._storage = Path(os.getenv("DASH_TRUSTED_DEVICES_FILE", Path.cwd() / "trusted_devices.json"))
        self._devices: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load trusted devices from disk."""
        try:
            if self._storage.exists():
                with open(self._storage, "r") as f:
                    self._devices = json.load(f)
        except Exception:
            logger.exception("Failed to load trusted devices")
            self._devices = {}

    def _save(self) -> None:
        """Save trusted devices to disk."""
        try:
            with open(self._storage, "w") as f:
                json.dump(self._devices, f, indent=2, default=str)
        except Exception:
            logger.exception("Failed to save trusted devices")

    def add_device(
        self,
        device_id: str,
        name: str = "",
        device_type: str = "unknown",
        public_key: str = "",
        ip_address: str = "",
    ) -> dict[str, Any]:
        """Register a device as trusted."""
        self._devices[device_id] = {
            "device_id": device_id,
            "name": name or device_id,
            "device_type": device_type,
            "public_key": public_key,
            "ip_address": ip_address,
            "trusted_at": time.time(),
            "last_seen": time.time(),
            "enabled": True,
        }
        self._save()
        logger.info("Added trusted device: %s (%s)", name, device_id)
        return self._devices[device_id]

    def remove_device(self, device_id: str) -> bool:
        """Remove a trusted device."""
        if device_id in self._devices:
            del self._devices[device_id]
            self._save()
            logger.info("Removed trusted device: %s", device_id)
            return True
        return False

    def is_trusted(self, device_id: str) -> bool:
        """Check if a device is in the trusted list and enabled."""
        device = self._devices.get(device_id)
        return device is not None and device.get("enabled", False)

    def update_last_seen(self, device_id: str) -> None:
        """Update the last_seen timestamp for a device."""
        if device_id in self._devices:
            self._devices[device_id]["last_seen"] = time.time()
            self._save()

    def set_enabled(self, device_id: str, enabled: bool) -> bool:
        """Enable or disable a trusted device."""
        if device_id in self._devices:
            self._devices[device_id]["enabled"] = enabled
            self._save()
            return True
        return False

    def list_devices(self) -> list[dict[str, Any]]:
        """List all trusted devices."""
        return list(self._devices.values())

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        """Get details for a specific device."""
        return self._devices.get(device_id)

    def get_stats(self) -> dict[str, Any]:
        """Get trust device statistics."""
        return {
            "total_devices": len(self._devices),
            "enabled_devices": sum(1 for d in self._devices.values() if d.get("enabled")),
            "storage_path": str(self._storage),
        }


# Global singleton
_trusted_service: TrustedDeviceService | None = None


def get_trusted_device_service() -> TrustedDeviceService:
    """Get or create the global TrustedDeviceService instance."""
    global _trusted_service
    if _trusted_service is None:
        _trusted_service = TrustedDeviceService()
    return _trusted_service
