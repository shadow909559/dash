"""Cloud Relay — Supabase-backed device registry for hybrid DASH.

When DASH runs on Fly.io (cloud), this service persists device states
in Supabase so Android can discover the PC even when the local backend
is off.  The local backend's in-memory CompanionHub remains the primary
registry when running locally; this layer is additive.

Flow:
  1. PC boots → auto-connect registers with cloud → this service stores state
  2. PC starts tunnel → stores tunnel URL → Android can connect directly
  3. Android queries cloud → sees PC online → connects via tunnel URL
  4. Android asks to wake PC → stores WoL request → relay sends magic packet
  5. PC boots → repeats from step 1
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# How long before a device is considered stale (seconds)
STALE_THRESHOLD_SECONDS = 120  # 2 minutes


class CloudRelayService:
    """Manages device states in Supabase for the hybrid cloud architecture.

    Uses the existing dash_devices table. Extra fields (tunnel_url, mac_address,
    local_ip) are stored in the capabilities jsonb column.
    """

    def __init__(self) -> None:
        self._client = None
        self._table = "dash_devices"

    def _get_client(self):
        """Lazy-init the Supabase service-role client."""
        if self._client is not None:
            return self._client

        settings = get_settings()
        if not settings.supabase_enabled or not settings.supabase_url:
            return None

        try:
            from supabase import create_client

            key = settings.supabase_service_role_key or settings.supabase_publishable_key
            if key is None:
                logger.warning("No Supabase key available for cloud relay")
                return None

            self._client = create_client(
                settings.supabase_url,
                key.get_secret_value(),
            )
            return self._client
        except Exception as exc:
            logger.error("Failed to create Supabase client for cloud relay: %s", exc)
            return None

    # ── Device Registration ──────────────────────────────────────

    async def register_device(
        self,
        device_id: str,
        name: str = "DASH PC",
        platform: str = "desktop",
        local_ip: str = "",
        mac_address: str = "",
        tunnel_url: str = "",
        capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register or update a device in the cloud registry."""
        client = self._get_client()
        if client is None:
            return {"ok": False, "error": "Supabase not configured"}

        now = datetime.now(timezone.utc).isoformat()
        # Store extra fields in capabilities jsonb
        caps = capabilities or []
        caps_data = {
            "list": caps,
            "local_ip": local_ip,
            "mac_address": mac_address,
            "tunnel_url": tunnel_url,
        }

        # Map platform to Supabase-allowed device_type values
        device_type_map = {
            "desktop": "desktop_agent",
            "android": "mobile",
            "ios": "mobile",
            "browser": "browser",
        }
        device_type = device_type_map.get(platform, "other")

        # Get owner user_id from config
        settings = get_settings()
        user_id = settings.supabase_sync_owner_id or "46d1932b-98e1-4028-9401-5da6b84e98aa"

        row = {
            "user_id": user_id,
            "name": name,
            "device_type": device_type,
            "platform": platform,
            "status": "online",
            "capabilities": caps_data,
            "last_seen_at": now,
        }

        try:
            # Check if device already exists
            existing = client.table(self._table).select("id").eq(
                "name", name
            ).execute()

            if existing.data:
                # Update existing
                result = client.table(self._table).update(row).eq(
                    "id", existing.data[0]["id"]
                ).execute()
            else:
                # Insert new
                row["name"] = name
                result = client.table(self._table).insert(row).execute()

            logger.info("Cloud relay: registered device '%s' (%s)", device_id, name)
            return {"ok": True, "device": _extract_data(result)}
        except Exception as exc:
            logger.error("Cloud relay register failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── Heartbeat ────────────────────────────────────────────────

    async def heartbeat(
        self,
        device_id: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update device heartbeat timestamp and optional state."""
        client = self._get_client()
        if client is None:
            return {"ok": False, "error": "Supabase not configured"}

        now = datetime.now(timezone.utc).isoformat()
        update = {
            "last_seen_at": now,
            "status": "online",
        }

        try:
            # Find device by name (device_id is the install_id used as name)
            existing = client.table(self._table).select("id").eq(
                "name", device_id
            ).execute()

            if not existing.data:
                # Auto-register on first heartbeat
                return await self.register_device(device_id)

            client.table(self._table).update(update).eq(
                "id", existing.data[0]["id"]
            ).execute()

            return {"ok": True}
        except Exception as exc:
            logger.error("Cloud relay heartbeat failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── Tunnel URL Registration ──────────────────────────────────

    async def register_tunnel(
        self,
        device_id: str,
        tunnel_url: str,
        service: str = "ollama",
    ) -> dict[str, Any]:
        """Store the Cloudflare tunnel URL for a device."""
        client = self._get_client()
        if client is None:
            return {"ok": False, "error": "Supabase not configured"}

        try:
            existing = client.table(self._table).select("id, capabilities").eq(
                "name", device_id
            ).execute()
            if not existing.data:
                return {"ok": False, "error": "Device not found"}
            row = existing.data[0]
            caps = row.get("capabilities", {}) or {}
            caps["tunnel_url"] = tunnel_url
            caps["tunnel_service"] = service
            client.table(self._table).update({
                "capabilities": caps,
                "status": "online",
            }).eq("id", row["id"]).execute()

            logger.info("Cloud relay: tunnel registered for '%s' → %s", device_id, tunnel_url)
            return {"ok": True}
        except Exception as exc:
            logger.error("Cloud relay tunnel registration failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── Query Device Status ──────────────────────────────────────

    async def get_device(self, device_id: str) -> dict[str, Any] | None:
        """Get a single device's state."""
        client = self._get_client()
        if client is None:
            return None

        try:
            result = client.table(self._table).select("*").eq(
                "name", device_id
            ).execute()
            rows = _extract_data(result)
            if not rows:
                return None

            device = _normalize_device(rows[0])
            if device["is_stale"] and device["status"] == "online":
                # Auto-mark as stale
                await self._mark_offline(device_id)
                device["status"] = "offline"

            return device
        except Exception as exc:
            logger.error("Cloud relay get_device failed: %s", exc)
            return None

    async def list_devices(
        self,
        platform: str | None = None,
        online_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List all registered devices."""
        client = self._get_client()
        if client is None:
            return []

        try:
            query = client.table(self._table).select("*")
            if platform:
                # Map platform names to Supabase device_type values
                platform_map = {
                    "desktop": "desktop_agent",
                    "android": "mobile",
                    "ios": "mobile",
                }
                db_type = platform_map.get(platform, platform)
                query = query.eq("device_type", db_type)
            if online_only:
                query = query.eq("status", "online")

            result = query.execute()
            devices = [_normalize_device(d) for d in (_extract_data(result) or [])]

            return devices
        except Exception as exc:
            logger.error("Cloud relay list_devices failed: %s", exc)
            return []

    async def get_pc_status(self) -> dict[str, Any]:
        """Get the primary PC's status (the first desktop device)."""
        devices = await self.list_devices(platform="desktop")
        if not devices:
            return {
                "status": "not_registered",
                "message": "No PC registered with cloud relay",
            }

        pc = devices[0]
        return {
            "status": pc.get("status", "unknown"),
            "device_id": pc.get("device_id", ""),
            "name": pc.get("name", ""),
            "tunnel_url": pc.get("tunnel_url", ""),
            "local_ip": pc.get("local_ip", ""),
            "mac_address": pc.get("mac_address", ""),
            "is_stale": pc.get("is_stale", False),
            "last_seen_at": pc.get("last_seen_at"),
            "capabilities": pc.get("capabilities", []),
        }

    # ── WoL ──────────────────────────────────────────────────────

    async def request_wake(
        self,
        device_id: str,
        mac_address: str | None = None,
    ) -> dict[str, Any]:
        """Store a Wake-on-LAN request for a device.

        The actual WoL packet is sent by:
        1. A WoL relay on the same LAN (if available)
        2. The cloud backend tries to send to public IP (if port forwarding is set)
        """
        client = self._get_client()
        if client is None:
            return {"ok": False, "error": "Supabase not configured"}

        # Get MAC from device state if not provided
        if not mac_address:
            device = await self.get_device(device_id)
            if device:
                mac_address = device.get("mac_address", "")

        if not mac_address:
            return {"ok": False, "error": "No MAC address available for WoL"}

        now = datetime.now(timezone.utc).isoformat()
        try:
            # Log the WoL trigger (status stays online/offline)
            logger.info("Cloud relay: WoL packet sent for '%s'", device_id)

            logger.info("Cloud relay: WoL requested for '%s' (MAC: %s)", device_id, mac_address)

            # Try to send WoL packet to public IP (best-effort)
            from dash_backend.services.wol import send_wol
            wol_result = await send_wol(mac_address=mac_address, count=3)

            return {
                "ok": True,
                "mac_address": mac_address,
                "wol_result": wol_result,
                "note": "WoL packets sent. PC should boot within 30 seconds.",
            }
        except Exception as exc:
            logger.error("Cloud relay WoL failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── Device Removal ───────────────────────────────────────────

    async def remove_device(self, device_id: str) -> dict[str, Any]:
        """Remove a device from the cloud registry."""
        client = self._get_client()
        if client is None:
            return {"ok": False, "error": "Supabase not configured"}

        try:
            existing = client.table(self._table).select("id").eq(
                "name", device_id
            ).execute()
            if existing.data:
                client.table(self._table).delete().eq(
                    "id", existing.data[0]["id"]
                ).execute()
            logger.info("Cloud relay: removed device '%s'", device_id)
            return {"ok": True}
        except Exception as exc:
            logger.error("Cloud relay remove_device failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── Internal Helpers ─────────────────────────────────────────

    async def _mark_offline(self, device_id: str) -> None:
        """Mark a device as offline."""
        client = self._get_client()
        if client is None:
            return
        try:
            client.table(self._table).update({"status": "offline"}).eq(
                "name", device_id
            ).execute()
        except Exception:
            pass


# ── Module-level singleton ──────────────────────────────────────

_relay: CloudRelayService | None = None


def get_cloud_relay() -> CloudRelayService:
    """Return the process-wide cloud relay service."""
    global _relay
    if _relay is None:
        _relay = CloudRelayService()
    return _relay


# ── Helpers ─────────────────────────────────────────────────────

def _extract_data(result) -> list[dict[str, Any]]:
    """Extract data rows from a Supabase result."""
    if hasattr(result, "data"):
        return result.data or []
    if isinstance(result, dict):
        return result.get("data", [])
    return []


def _normalize_device(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a dash_devices row into a consistent format for the relay."""
    caps = raw.get("capabilities") or {}
    if isinstance(caps, list):
        caps = {"list": caps}

    return {
        "device_id": raw.get("name", ""),
        "id": raw.get("id"),
        "name": raw.get("name", ""),
        "platform": raw.get("device_type", raw.get("platform", "desktop")),
        "status": raw.get("status", "offline"),
        "local_ip": caps.get("local_ip", ""),
        "mac_address": caps.get("mac_address", ""),
        "tunnel_url": caps.get("tunnel_url", ""),
        "tunnel_service": caps.get("tunnel_service", ""),
        "capabilities": caps.get("list", []),
        "last_seen_at": raw.get("last_seen_at"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "is_stale": _is_stale(raw),
    }


def _is_stale(device: dict[str, Any]) -> bool:
    """Check if a device hasn't sent a heartbeat recently."""
    last_seen = device.get("last_seen_at") or device.get("last_heartbeat")
    if not last_seen:
        return True

    try:
        if isinstance(last_seen, str):
            dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        elif isinstance(last_seen, datetime):
            dt = last_seen
        else:
            return True

        age_seconds = (datetime.now(timezone.utc) - dt).total_seconds()
        return age_seconds > STALE_THRESHOLD_SECONDS
    except Exception:
        return True
