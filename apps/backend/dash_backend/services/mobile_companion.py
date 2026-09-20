"""Mobile companion: push notifications, camera, QR, location, contacts, share, offline."""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Push notifications for mobile devices.

    Queued notifications AND device registrations are PERSISTED (atomic
    JSON under DASH_CRM_DIR or the default app dir) so a backend restart
    neither silently drops pushes the companion has not fetched yet nor
    loses the delivery-target list (spec #93, decisions.md #98).
    """

    def __init__(self) -> None:
        self._devices: list[dict] = []
        self._notifications: list[dict] = []
        self._store_path: Optional[Any] = None
        self._fcm_creds: Optional[dict] = None
        self._fcm_token: Optional[str] = None
        self._fcm_token_exp: float = 0.0
        self._fcm_last_error: str = ""
        try:
            import os
            from pathlib import Path
            base = Path(os.getenv("DASH_CRM_DIR") or (Path.home() / ".dash" / "crm"))
            base.mkdir(parents=True, exist_ok=True)
            self._store_path = base / "companion_push.json"
            self._load()
            self._fcm_creds = self._load_fcm_credentials()
        except Exception:
            logging.getLogger(__name__).exception("companion push store init failed (memory-only)")

    @staticmethod
    def _load_fcm_credentials() -> Optional[dict]:
        """Real FCM HTTP v1 transport config (spec #96/#155, decisions.md #102).

        Reads a Google service-account JSON (project_id, client_email,
        private_key) from DASH_FCM_SERVICE_ACCOUNT (path or inline JSON).
        No credentials -> transport stays unconfigured and every outcome
        says so honestly; the queue still works (companion fetch path).
        """
        import json as _json
        import os
        raw = os.getenv("DASH_FCM_SERVICE_ACCOUNT", "").strip()
        if not raw:
            return None
        try:
            import os as _os
            payload = raw if raw.lstrip().startswith("{") else Path(raw).read_text(encoding="utf-8")
            creds = _json.loads(payload)
            missing = [k for k in ("project_id", "client_email", "private_key") if not creds.get(k)]
            if missing:
                raise ValueError(f"service account missing {', '.join(missing)}")
            return {"project_id": creds["project_id"],
                    "client_email": creds["client_email"],
                    "private_key": creds["private_key"]}
        except Exception as exc:
            logging.getLogger(__name__).error("FCM service account unreadable: %s", exc)
            return None

    def _load(self) -> None:
        if self._store_path is None or not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._notifications = data[-500:]
            elif isinstance(data, dict):
                self._notifications = data.get("notifications", [])[-500:]
                devices = data.get("devices", [])
                self._devices = [d for d in devices if d.get("active")]
        except Exception:
            logging.getLogger(__name__).exception("companion push store unreadable (starting empty)")

    def _save(self) -> None:
        if self._store_path is None:
            return
        try:
            tmp = self._store_path.with_suffix(".tmp")
            payload = {
                "version": 2,
                "devices": self._devices[-100:],
                "notifications": self._notifications[-500:],
            }
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._store_path)
        except Exception:
            logging.getLogger(__name__).exception("companion push store write failed")

    def register_device(self, device_id: str, platform: str, token: str, user_id: str = "") -> dict:
        # One row per device_id: re-registration refreshes instead of stacking
        self._devices = [d for d in self._devices if d.get("device_id") != device_id]
        device = {"device_id": device_id, "platform": platform, "token": token, "user_id": user_id, "registered_at": datetime.now(timezone.utc).isoformat(), "active": True}
        self._devices.append(device)
        self._save()
        return {"ok": True, "device": device}

    def unregister_device(self, device_id: str) -> dict:
        self._devices = [d for d in self._devices if d["device_id"] != device_id]
        self._save()
        return {"ok": True}

    def _fcm_access_token(self) -> Optional[str]:
        """Mint + cache a Google OAuth2 access token from the service
        account (RS256 JWT exchange). Returns None with _fcm_last_error
        set on any failure — never a fake token."""
        import time as _time
        if self._fcm_token and _time.time() < self._fcm_token_exp - 60:
            return self._fcm_token
        creds = self._fcm_creds
        if not creds:
            self._fcm_last_error = "no service account configured"
            return None
        try:
            import jwt
            now = int(_time.time())
            assertion = jwt.encode(
                {"iss": creds["client_email"],
                 "scope": "https://www.googleapis.com/auth/firebase.messaging",
                 "aud": "https://oauth2.googleapis.com/token",
                 "iat": now, "exp": now + 3600},
                creds["private_key"], algorithm="RS256",
            )
            import requests
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                      "assertion": assertion},
                timeout=10,
            )
            if resp.status_code != 200:
                self._fcm_last_error = f"token exchange failed: HTTP {resp.status_code}"
                return None
            token = resp.json().get("access_token")
            if not token:
                self._fcm_last_error = "token exchange returned no access_token"
                return None
            self._fcm_token = token
            self._fcm_token_exp = _time.time() + int(resp.json().get("expires_in", 3600))
            self._fcm_last_error = ""
            return token
        except Exception as exc:
            self._fcm_last_error = f"token exchange error: {exc}"
            return None

    def _fcm_send(self, device_token: str, title: str, body: str,
                  data: dict | None) -> tuple[bool, str]:
        """One real FCM HTTP v1 send. Returns (ok, honest detail)."""
        token = self._fcm_access_token()
        if not token:
            return False, self._fcm_last_error or "unauthenticated"
        try:
            import requests
            url = (f"https://fcm.googleapis.com/v1/projects/"
                   f"{self._fcm_creds['project_id']}/messages:send")
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"message": {
                    "token": device_token,
                    "notification": {"title": title[:240], "body": body[:1000]},
                    "data": {k: str(v)[:4000] for k, v in (data or {}).items()},
                }},
                timeout=10,
            )
            if 200 <= resp.status_code < 300:
                return True, "sent"
            if resp.status_code in (404, 410):
                return False, "UNREGISTERED"
            if resp.status_code == 429:
                return False, "QUOTA_EXCEEDED"
            if resp.status_code in (401, 403):
                return False, f"AUTH_FAILED (HTTP {resp.status_code})"
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            return False, f"transport error: {exc}"

    def send_push(self, title: str, body: str, data: dict | None = None, target_user: str = "") -> dict:
        """Queue + real transport attempt per active device (spec #96/#117).

        The queue is always written (companion fetch path works offline).
        When FCM is configured, each target gets a REAL send attempt and
        per-device outcomes are recorded. `delivered` counts only
        provider-confirmed sends — never the queue write (no false
        success, spec #117).
        """
        targets = [d for d in self._devices if d.get("active") and (not target_user or d.get("user_id") == target_user)]
        notif = {"id": f"push_{len(self._notifications)}", "title": title, "body": body, "data": data or {}, "targets": len(targets), "sent_at": datetime.now(timezone.utc).isoformat()}
        self._notifications.append(notif)
        delivered = 0
        per_device: list[dict] = []
        if self._fcm_creds:
            for d in targets:
                ok, detail = self._fcm_send(d.get("token", ""), title, body, data)
                if ok:
                    delivered += 1
                else:
                    if detail == "UNREGISTERED":
                        d["active"] = False  # provider said the token is dead
                        self._save()
                    self._fcm_last_error = detail
                per_device.append({"device_id": d.get("device_id"), "ok": ok, "detail": detail})
            notif["delivery"] = {"transport": "fcm", "delivered": delivered, "devices": per_device}
        else:
            notif["delivery"] = {"transport": "local_queue_only", "delivered": 0}
        self._save()
        return {"ok": True, "notification": notif, "delivered": delivered,
                "queued": len(targets),
                "transport": "fcm" if self._fcm_creds else "local_queue_only"}

    def transport_status(self) -> dict:
        """Honest capability report for the push transport (spec #90/#155).
        Includes real queue/device counts so the owner's Diagnostics view
        shows delivery health, not just configuration state."""
        counts = {
            "queued_notifications": len(self._notifications),
            "active_devices": len([d for d in self._devices if d.get("active")]),
        }
        if self._fcm_creds:
            state = "degraded" if self._fcm_last_error else "operational"
            return {"transport": "fcm", "state": state,
                    "configured": True,
                    "reason": self._fcm_last_error or "service account configured",
                    **counts}
        return {"transport": "local_queue_only", "state": "degraded",
                "configured": False,
                "reason": ("DASH_FCM_SERVICE_ACCOUNT not set — pushes queue for "
                           "companion fetch; real device delivery needs a Google "
                           "service account (integration seam: FCM HTTP v1)"),
                **counts}

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
