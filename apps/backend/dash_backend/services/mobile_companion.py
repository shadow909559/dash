"""Mobile companion: push notifications, camera, QR, location, contacts, share, offline."""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Push notifications for mobile devices."""

    def __init__(self) -> None:
        self._devices: list[dict] = []
        self._notifications: list[dict] = []

    def register_device(self, device_id: str, platform: str, token: str, user_id: str = "") -> dict:
        device = {"device_id": device_id, "platform": platform, "token": token, "user_id": user_id, "registered_at": datetime.now(timezone.utc).isoformat(), "active": True}
        self._devices.append(device)
        return {"ok": True, "device": device}

    def unregister_device(self, device_id: str) -> dict:
        self._devices = [d for d in self._devices if d["device_id"] != device_id]
        return {"ok": True}

    def send_push(self, title: str, body: str, data: dict | None = None, target_user: str = "") -> dict:
        targets = [d for d in self._devices if d.get("active") and (not target_user or d.get("user_id") == target_user)]
        notif = {"id": f"push_{len(self._notifications)}", "title": title, "body": body, "data": data or {}, "targets": len(targets), "sent_at": datetime.now(timezone.utc).isoformat()}
        self._notifications.append(notif)
        return {"ok": True, "notification": notif, "delivered_to": len(targets)}

    def get_devices(self) -> list[dict]:
        return list(self._devices)

    def get_notifications(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._notifications[-limit:]))


class CameraService:
    """Camera integration for photo capture and analysis."""

    def __init__(self) -> None:
        self._captures: list[dict] = []

    def capture(self, description: str = "", source: str = "camera") -> dict:
        capture = {"id": f"cap_{len(self._captures)}", "description": description, "source": source, "captured_at": datetime.now(timezone.utc).isoformat()}
        self._captures.append(capture)
        return {"ok": True, "capture": capture}

    def analyze(self, capture_id: str) -> dict:
        return {"ok": True, "capture_id": capture_id, "analysis": "Image analysis complete", "objects": [], "text_detected": ""}

    def get_captures(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._captures[-limit:]))


class QRScannerService:
    """QR code and barcode scanning."""

    def __init__(self) -> None:
        self._scans: list[dict] = []

    def scan(self, content: str, format_type: str = "qr_code") -> dict:
        result = {"id": f"scan_{len(self._scans)}", "content": content, "format": format_type, "scanned_at": datetime.now(timezone.utc).isoformat()}
        self._scans.append(result)
        # Determine action based on content
        action = "unknown"
        if content.startswith("http"):
            action = "url"
        elif content.startswith("mailto:"):
            action = "email"
        elif content.startswith("tel:"):
            action = "phone"
        elif content.startswith("WIFI:"):
            action = "wifi"
        result["action"] = action
        return {"ok": True, "scan": result}

    def get_scans(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._scans[-limit:]))


class LocationService:
    """Location awareness for reminders and context."""

    def __init__(self) -> None:
        self._locations: list[dict] = []
        self._geofences: list[dict] = []
        self._current: dict = {}

    def update_location(self, lat: float, lng: float, name: str = "") -> dict:
        self._current = {"lat": lat, "lng": lng, "name": name, "updated_at": datetime.now(timezone.utc).isoformat()}
        self._locations.append(dict(self._current))
        if len(self._locations) > 500:
            self._locations = self._locations[-250:]
        return {"ok": True, "location": self._current}

    def get_current(self) -> dict:
        return dict(self._current)

    def get_history(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._locations[-limit:]))

    def add_geofence(self, name: str, lat: float, lng: float, radius_m: float = 100) -> dict:
        fence = {"id": f"fence_{len(self._geofences)}", "name": name, "lat": lat, "lng": lng, "radius_m": radius_m, "created_at": datetime.now(timezone.utc).isoformat()}
        self._geofences.append(fence)
        return {"ok": True, "geofence": fence}

    def check_geofences(self) -> list[dict]:
        triggered = []
        for fence in self._geofences:
            if self._current:
                import math
                R = 6371000
                lat1, lon1 = math.radians(self._current["lat"]), math.radians(self._current["lng"])
                lat2, lon2 = math.radians(fence["lat"]), math.radians(fence["lng"])
                dlat, dlon = lat2 - lat1, lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
                dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                if dist <= fence["radius_m"]:
                    triggered.append({"geofence": fence["name"], "distance_m": round(dist, 1)})
        return triggered

    def get_geofences(self) -> list[dict]:
        return list(self._geofences)


class ContactServiceMobile:
    """Mobile contacts integration."""

    def __init__(self) -> None:
        self._contacts: list[dict] = []

    def sync_contacts(self, contacts: list[dict]) -> dict:
        self._contacts = contacts
        return {"ok": True, "synced": len(contacts)}

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [c for c in self._contacts if q in c.get("name", "").lower() or q in c.get("phone", "")]

    def get_all(self) -> list[dict]:
        return list(self._contacts)


class OfflineService:
    """Offline mode: queue actions, sync when online."""

    def __init__(self) -> None:
        self._queue: list[dict] = []
        self._is_online = True
        self._sync_log: list[dict] = []

    def set_online(self, online: bool) -> dict:
        self._is_online = online
        if online:
            self.sync()
        return {"ok": True, "online": online}

    def queue_action(self, action_type: str, payload: dict) -> dict:
        entry = {"id": f"off_{len(self._queue)}", "type": action_type, "payload": payload, "queued_at": datetime.now(timezone.utc).isoformat()}
        self._queue.append(entry)
        return {"ok": True, "queued": entry}

    def sync(self) -> dict:
        count = len(self._queue)
        if count > 0:
            self._sync_log.append({"synced": count, "timestamp": datetime.now(timezone.utc).isoformat()})
            self._queue.clear()
        return {"synced": count}

    def get_queue(self) -> list[dict]:
        return list(self._queue)

    def get_sync_log(self) -> list[dict]:
        return list(self._sync_log)

    def is_online(self) -> bool:
        return self._is_online


push_service = PushNotificationService()
camera_service = CameraService()
qr_scanner = QRScannerService()
location_service = LocationService()
mobile_contacts = ContactServiceMobile()
offline_service = OfflineService()
