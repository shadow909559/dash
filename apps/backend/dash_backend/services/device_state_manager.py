"""Offline-first Device State Manager.

Works with local SQLite database when offline, and syncs to AWS DynamoDB
when network is available. All Windows tasks work locally without network.

Architecture:
- Local SQLite: Always available, zero latency
- AWS DynamoDB: Synced when online, provides cloud relay
- Auto-sync: Detects network state and syncs automatically
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Local database path
LOCAL_DB_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "DASH"
LOCAL_DB_PATH = LOCAL_DB_DIR / "device_states.db"

# DynamoDB table name
DYNAMODB_TABLE = "dash-device-states"

# Sync interval (seconds)
SYNC_INTERVAL = 30


class DeviceStateManager:
    """Offline-first device state manager with cloud sync."""

    def __init__(self):
        self._local_db = None
        self._aws = None
        self._sync_task = None
        self._network_available = False
        self._initialized = False

    async def initialize(self):
        """Initialize local database and check AWS connectivity."""
        if self._initialized:
            return

        # Create local SQLite database
        LOCAL_DB_DIR.mkdir(parents=True, exist_ok=True)
        self._local_db = sqlite3.connect(str(LOCAL_DB_PATH))
        self._local_db.row_factory = sqlite3.Row

        # Create tables if they don't exist
        self._local_db.execute("""
            CREATE TABLE IF NOT EXISTS device_states (
                device_id TEXT PRIMARY KEY,
                name TEXT,
                platform TEXT,
                status TEXT DEFAULT 'offline',
                local_ip TEXT,
                mac_address TEXT,
                tunnel_url TEXT,
                capabilities TEXT DEFAULT '[]',
                last_seen TEXT,
                updated_at TEXT,
                cloud_synced INTEGER DEFAULT 0
            )
        """)

        self._local_db.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT,
                device_id TEXT,
                timestamp TEXT,
                success INTEGER,
                error TEXT
            )
        """)

        self._local_db.commit()

        # Check AWS connectivity
        try:
            from dash_backend.services.aws_free_tier import get_aws_free_tier
            self._aws = get_aws_free_tier()
            self._network_available = True
            logger.info("AWS Free Tier services available")
        except Exception as e:
            logger.warning(f"AWS not available: {e}")
            self._network_available = False

        self._initialized = True

        # Start background sync
        self._sync_task = asyncio.create_task(self._background_sync())

    async def _background_sync(self):
        """Background task that syncs local state to DynamoDB."""
        while True:
            try:
                await asyncio.sleep(SYNC_INTERVAL)
                if self._network_available and self._aws:
                    await self._sync_to_cloud()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background sync error: {e}")

    async def _sync_to_cloud(self):
        """Sync unsynced local changes to DynamoDB."""
        try:
            # Get unsynced items
            cursor = self._local_db.execute(
                "SELECT * FROM device_states WHERE cloud_synced = 0"
            )
            unsynced = [dict(row) for row in cursor.fetchall()]

            for item in unsynced:
                # Ensure DynamoDB table exists
                await self._aws.ensure_dynamodb_table(DYNAMODB_TABLE)

                # Convert capabilities from JSON string
                if isinstance(item.get("capabilities"), str):
                    try:
                        item["capabilities"] = json.loads(item["capabilities"])
                    except json.JSONDecodeError:
                        item["capabilities"] = []

                # Put to DynamoDB
                success = await self._aws.dynamodb_put(DYNAMODB_TABLE, item)

                if success:
                    # Mark as synced
                    self._local_db.execute(
                        "UPDATE device_states SET cloud_synced = 1 WHERE device_id = ?",
                        (item["device_id"],)
                    )
                    # Log sync
                    self._local_db.execute(
                        "INSERT INTO sync_log (operation, device_id, timestamp, success) VALUES (?, ?, ?, ?)",
                        ("sync_to_cloud", item["device_id"], datetime.now(timezone.utc).isoformat(), 1)
                    )
                else:
                    self._local_db.execute(
                        "INSERT INTO sync_log (operation, device_id, timestamp, success, error) VALUES (?, ?, ?, ?, ?)",
                        ("sync_to_cloud", item["device_id"], datetime.now(timezone.utc).isoformat(), 0, "DynamoDB put failed")
                    )

            self._local_db.commit()

            if unsynced:
                logger.info(f"Synced {len(unsynced)} device states to DynamoDB")

        except Exception as e:
            logger.error(f"Cloud sync failed: {e}")

    async def register_device(self, device_id: str, name: str, platform: str,
                              local_ip: str = "", mac_address: str = "",
                              tunnel_url: str = "", capabilities: List[str] = None) -> Dict:
        """Register a device (works offline, syncs when online)."""
        await self.initialize()

        now = datetime.now(timezone.utc).isoformat()
        capabilities = capabilities or []

        # Store locally
        self._local_db.execute("""
            INSERT OR REPLACE INTO device_states
            (device_id, name, platform, status, local_ip, mac_address, tunnel_url,
             capabilities, last_seen, updated_at, cloud_synced)
            VALUES (?, ?, ?, 'online', ?, ?, ?, ?, ?, ?, 0)
        """, (device_id, name, platform, local_ip, mac_address, tunnel_url,
              json.dumps(capabilities), now, now))
        self._local_db.commit()

        # Try to sync to cloud immediately
        if self._network_available and self._aws:
            try:
                await self._aws.ensure_dynamodb_table(DYNAMODB_TABLE)
                await self._aws.dynamodb_put(DYNAMODB_TABLE, {
                    "device_id": device_id,
                    "name": name,
                    "platform": platform,
                    "status": "online",
                    "local_ip": local_ip,
                    "mac_address": mac_address,
                    "tunnel_url": tunnel_url,
                    "capabilities": capabilities,
                    "last_seen": now,
                    "updated_at": now,
                })
                self._local_db.execute(
                    "UPDATE device_states SET cloud_synced = 1 WHERE device_id = ?",
                    (device_id,)
                )
                self._local_db.commit()
            except Exception as e:
                logger.warning(f"Cloud sync failed: {e}")

        return {"ok": True, "device_id": device_id, "synced": self._network_available}

    async def update_heartbeat(self, device_id: str, state: Dict[str, Any] = None) -> Dict:
        """Update device heartbeat (works offline)."""
        await self.initialize()

        now = datetime.now(timezone.utc).isoformat()
        state = state or {}

        self._local_db.execute("""
            UPDATE device_states
            SET last_seen = ?, updated_at = ?, status = 'online', cloud_synced = 0
            WHERE device_id = ?
        """, (now, now, device_id))
        self._local_db.commit()

        return {"ok": True, "synced": self._network_available}

    async def get_pc_status(self) -> Dict:
        """Get PC status (works offline from local DB)."""
        await self.initialize()

        # Find the desktop device
        cursor = self._local_db.execute(
            "SELECT * FROM device_states WHERE platform = 'desktop' ORDER BY last_seen DESC LIMIT 1"
        )
        row = cursor.fetchone()

        if row:
            return {
                "status": row["status"],
                "device_id": row["device_id"],
                "name": row["name"],
                "tunnel_url": row["tunnel_url"] or "",
                "local_ip": row["local_ip"] or "",
                "mac_address": row["mac_address"] or "",
                "last_seen": row["last_seen"],
                "capabilities": json.loads(row["capabilities"]) if row["capabilities"] else [],
            }

        return {"status": "unknown", "device_id": "", "name": ""}

    async def get_device(self, device_id: str) -> Optional[Dict]:
        """Get specific device (works offline)."""
        await self.initialize()

        cursor = self._local_db.execute(
            "SELECT * FROM device_states WHERE device_id = ?", (device_id,)
        )
        row = cursor.fetchone()

        if row:
            return {
                "device_id": row["device_id"],
                "name": row["name"],
                "platform": row["platform"],
                "status": row["status"],
                "local_ip": row["local_ip"],
                "mac_address": row["mac_address"],
                "tunnel_url": row["tunnel_url"],
                "capabilities": json.loads(row["capabilities"]) if row["capabilities"] else [],
                "last_seen": row["last_seen"],
            }

        return None

    async def list_devices(self, platform: str = None, online_only: bool = False) -> List[Dict]:
        """List all devices (works offline)."""
        await self.initialize()

        query = "SELECT * FROM device_states WHERE 1=1"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        if online_only:
            query += " AND status = 'online'"

        cursor = self._local_db.execute(query, params)
        rows = cursor.fetchall()

        return [
            {
                "device_id": row["device_id"],
                "name": row["name"],
                "platform": row["platform"],
                "status": row["status"],
                "local_ip": row["local_ip"],
                "mac_address": row["mac_address"],
                "tunnel_url": row["tunnel_url"],
                "capabilities": json.loads(row["capabilities"]) if row["capabilities"] else [],
                "last_seen": row["last_seen"],
            }
            for row in rows
        ]

    async def register_tunnel(self, device_id: str, tunnel_url: str, service: str = "ollama") -> Dict:
        """Register tunnel URL (works offline, syncs when online)."""
        await self.initialize()

        now = datetime.now(timezone.utc).isoformat()

        self._local_db.execute("""
            UPDATE device_states
            SET tunnel_url = ?, updated_at = ?, cloud_synced = 0
            WHERE device_id = ?
        """, (tunnel_url, now, device_id))
        self._local_db.commit()

        # Try cloud sync
        if self._network_available and self._aws:
            try:
                await self._aws.dynamodb_update(DYNAMODB_TABLE, {"device_id": device_id}, {
                    "tunnel_url": tunnel_url,
                    "updated_at": now,
                })
                self._local_db.execute(
                    "UPDATE device_states SET cloud_synced = 1 WHERE device_id = ?",
                    (device_id,)
                )
                self._local_db.commit()
            except Exception as e:
                logger.warning(f"Cloud tunnel sync failed: {e}")

        return {"ok": True, "synced": self._network_available}

    async def trigger_wol(self, device_id: str, mac_address: str = None) -> Dict:
        """Trigger Wake-on-LAN (works offline via local network)."""
        await self.initialize()

        # Get device info
        device = await self.get_device(device_id)
        if not device:
            return {"ok": False, "error": "Device not found"}

        mac = mac_address or device.get("mac_address", "")
        if not mac:
            return {"ok": False, "error": "No MAC address"}

        # Try local WoL first
        try:
            import subprocess
            # Send WoL magic packet via PowerShell
            ps_cmd = f"""
            $mac = '{mac.Replace(':', '-')}'
            $target = [System.Net.IPAddress]::Parse('255.255.255.255')
            $udp = New-Object System.Net.Sockets.UdpClient
            $packet = [byte[]](@(0xFF) * 6 + ($mac.Split('-') | ForEach-Object {{ [Convert]::ToByte($_, 16) }}) * 16)
            $udp.Send($packet, $packet.Length, $target, 9)
            """
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=5)
            return {"ok": True, "method": "local", "mac_address": mac}
        except Exception as e:
            logger.warning(f"Local WoL failed: {e}")

        return {"ok": False, "error": str(e)}


# Singleton
_device_state_manager: Optional[DeviceStateManager] = None


def get_device_state_manager() -> DeviceStateManager:
    """Get the device state manager singleton."""
    global _device_state_manager
    if _device_state_manager is None:
        _device_state_manager = DeviceStateManager()
    return _device_state_manager
