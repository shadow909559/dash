"""ADB Service - Android device control via ADB for DASH AI OS.

Provides a complete backend for phone control through the Android Debug
Bridge (ADB). All operations are backend-only (no UI yet) and integrate
with the existing DASH architecture.

Capabilities:
- Device discovery (USB + wireless/network ADB)
- Battery information
- Notifications
- Clipboard (read/write)
- Files (list, push, pull, delete)
- App launching
- SMS (permission-gated)
- Call status
- Location
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


class AdbService(Singleton):
    """Android device control via ADB.

    Wraps the `adb` command-line tool. All methods are async and safely
    handle missing/offline devices. Method names match the DASH phone
    control contract (battery, notifications, clipboard, files, apps,
    sms, call status, location).
    """

    def __init__(self) -> None:
        self._adb_path: Optional[str] = None
        self._connected_devices: Dict[str, Dict[str, Any]] = {}
        self._paired_emulators = set()

    # ────────────────────────────────────────────────────────
    # ADB binary discovery
    # ────────────────────────────────────────────────────────

    def _find_adb(self) -> Optional[str]:
        """Locate the adb executable.

        Checks PATH first, then common installation locations. Never
        assumes a hardcoded path is valid.
        """
        # 1. PATH lookup
        found = shutil.which("adb")
        if found:
            return found

        # 2. Android SDK locations
        candidates: List[str] = []
        env_sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if env_sdk:
            candidates.append(str(Path(env_sdk) / "platform-tools" / "adb"))
            if IS_WINDOWS:
                candidates.append(str(Path(env_sdk) / "platform-tools" / "adb.exe"))

        # Common default install locations
        if IS_WINDOWS:
            home = Path.home()
            candidates.extend([
                str(home / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"),
                r"C:\Android\platform-tools\adb.exe",
                r"C:\Program Files\Android\platform-tools\adb.exe",
            ])
        else:
            candidates.extend([
                str(Path.home() / "Android" / "Sdk" / "platform-tools" / "adb"),
                "/usr/bin/adb",
                "/usr/local/bin/adb",
                "/opt/android/platform-tools/adb",
            ])

        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

        return None

    async def _adb(self, args: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run an adb command and return parsed result."""
        if not self._adb_path:
            self._adb_path = self._find_adb()
        if not self._adb_path:
            return {
                "ok": False,
                "error": "ADB not found. Install Android platform-tools or set ANDROID_HOME.",
            }

        try:
            proc = await asyncio.create_subprocess_exec(
                self._adb_path, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except asyncio.TimeoutError:
            return {"ok": False, "error": f"ADB command timed out after {timeout}s"}
        except Exception as exc:
            logger.exception("adb command failed")
            return {"ok": False, "error": str(exc)}

    # ────────────────────────────────────────────────────────
    # Device discovery
    # ────────────────────────────────────────────────────────

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover connected ADB devices (USB + wireless).

        Returns:
            List of device dicts with serial, state, transport, model.
        """
        result = await self._adb(["devices", "-l"])
        devices: List[Dict[str, Any]] = []
        if not result.get("ok"):
            return devices

        lines = result.get("stdout", "").splitlines()
        for line in lines[1:]:  # skip header
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            serial = parts[0]
            state = parts[1] if len(parts) > 1 else "unknown"
            info: Dict[str, Any] = {"serial": serial, "state": state}

            # Parse "device product:xxx model:yyy device:zzz" attributes
            for chunk in parts[2:]:
                if ":" in chunk:
                    key, _, value = chunk.partition(":")
                    if key in ("product", "model", "device", "transport_id"):
                        info[key] = value

            self._connected_devices[serial] = info
            devices.append(info)

        return devices

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Alias for discover_devices (cached state)."""
        if not self._connected_devices:
            await self.discover_devices()
        return list(self._connected_devices.values())

    async def connect_wireless(self, host: str, port: int = 5555) -> Dict[str, Any]:
        """Connect to a device over wireless ADB.

        Args:
            host: IP address or hostname
            port: ADB port (default 5555)

        Returns:
            Result dict.
        """
        result = await self._adb(["connect", f"{host}:{port}"], timeout=15)
        connected = result.get("ok") and "connected" in result.get("stdout", "").lower()
        if connected:
            serial = f"{host}:{port}"
            self._connected_devices[serial] = {
                "serial": serial, "state": "device", "transport": "wireless",
            }
        return {
            "ok": connected,
            "summary": result.get("stdout", "").strip() or result.get("stderr", "").strip(),
            "message": result.get("stdout", "").strip(),
        }

    async def disconnect_wireless(self, host: str, port: int = 5555) -> Dict[str, Any]:
        """Disconnect a wireless device."""
        result = await self._adb(["disconnect", f"{host}:{port}"], timeout=15)
        serial = f"{host}:{port}"
        self._connected_devices.pop(serial, None)
        return {
            "ok": result.get("ok", False),
            "summary": result.get("stdout", "").strip() or "disconnected",
        }

    async def pair_wireless(self, host: str, pairing_code: str, port: int = 37000) -> Dict[str, Any]:
        """Pair with a device over wireless ADB (Android 11+ pairing).

        Args:
            host: IP address
            pairing_code: 6-digit pairing code
            port: Pairing port (default 37000)

        Returns:
            Result dict.
        """
        result = await self._adb(
            ["pair", f"{host}:{port}", pairing_code], timeout=20,
        )
        ok = result.get("ok") and "successfully paired" in result.get("stdout", "").lower()
        return {
            "ok": ok,
            "summary": result.get("stdout", "").strip() or result.get("stderr", "").strip(),
        }

    # ────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────

    def _device_prefix(self, serial: Optional[str]) -> List[str]:
        """Return the device selector prefix for adb commands."""
        if serial:
            return ["-s", serial]
        return []

    async def _require_device(self, serial: Optional[str]) -> Optional[str]:
        """Ensure a device is available. Returns a usable serial or None."""
        if serial and serial in self._connected_devices:
            return serial
        devices = await self.discover_devices()
        for d in devices:
            if d.get("state") == "device":
                return d["serial"]
        return None

    # ────────────────────────────────────────────────────────
    # Battery
    # ────────────────────────────────────────────────────────

    async def get_battery(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Get battery information."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}

        result = await self._adb([*self._device_prefix(device), "shell", "dumpsys", "battery"])
        if not result.get("ok"):
            return {"ok": False, "error": result.get("stderr", "Failed to read battery")}

        text = result.get("stdout", "")
        battery: Dict[str, Any] = {}
        for line in text.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key in ("level", "status", "health", "temperature", "voltage",
                           "technology", "ac_powered", "usb_powered", "wireless_powered"):
                    battery[key] = value

        return {
            "ok": True,
            "battery": battery,
            "level": battery.get("level"),
            "is_charging": battery.get("ac_powered") == "true"
                       or battery.get("usb_powered") == "true"
                       or battery.get("wireless_powered") == "true",
        }

    # ────────────────────────────────────────────────────────
    # Notifications
    # ────────────────────────────────────────────────────────

    async def get_notifications(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Get recent notifications from the device.

        Uses `dumpsys notification`. Returns a list of notification dicts.
        """
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}

        result = await self._adb(
            [*self._device_prefix(device), "shell", "dumpsys", "notification", "--noredact"],
        )
        if not result.get("ok"):
            return {"ok": False, "error": "Failed to read notifications"}

        text = result.get("stdout", "")
        notifications: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("NotificationRecord"):
                if current:
                    notifications.append(current)
                current = {"id": None, "pkg": None, "title": None, "text": None}
                # parse id
                m = re.search(r"\[(\d+)\|", stripped)
                if m:
                    current["id"] = m.group(1)
            elif "pkg=" in stripped:
                m = re.search(r"pkg=(\S+)", stripped)
                if m:
                    current["pkg"] = m.group(1)
            elif stripped.startswith("android.title="):
                current["title"] = stripped.split("=", 1)[1].strip()
            elif stripped.startswith("android.text="):
                current["text"] = stripped.split("=", 1)[1].strip()
        if current:
            notifications.append(current)

        return {"ok": True, "notifications": notifications[:50], "count": len(notifications)}

    async def clear_notifications(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Clear all notifications on the device."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "shell", "cmd", "notification", "-c", "ALL"],
        )
        return {"ok": result.get("ok", False), "summary": "Notifications cleared"}

    # ────────────────────────────────────────────────────────
    # Clipboard
    # ────────────────────────────────────────────────────────

    async def read_clipboard(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Read the device clipboard text."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "shell", "cmd", "clipboard", "get"],
        )
        text = result.get("stdout", "").strip() if result.get("ok") else ""
        return {"ok": result.get("ok", False), "text": text}

    async def write_clipboard(self, text: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Set the device clipboard text."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        # Use service call to set clipboard (works on most devices)
        result = await self._adb(
            [*self._device_prefix(device), "shell", "cmd", "clipboard", "set", text],
        )
        return {
            "ok": result.get("ok", False),
            "summary": "Clipboard set" if result.get("ok") else "Failed to set clipboard",
        }

    # ────────────────────────────────────────────────────────
    # Files
    # ────────────────────────────────────────────────────────

    async def list_files(self, path: str = "/sdcard", serial: Optional[str] = None) -> Dict[str, Any]:
        """List files in a directory on the device."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "shell", "ls", "-la", path],
        )
        files: List[Dict[str, Any]] = []
        for line in result.get("stdout", "").splitlines():
            line = line.strip()
            if not line or line.startswith("total"):
                continue
            parts = line.split(None, 8)
            if len(parts) >= 9:
                files.append({
                    "permissions": parts[0],
                    "links": parts[1],
                    "owner": parts[2],
                    "group": parts[3],
                    "size": parts[4],
                    "month": parts[5],
                    "day": parts[6],
                    "time": parts[7],
                    "name": parts[8],
                })
            elif len(parts) >= 1:
                files.append({"name": parts[-1]})
        return {"ok": result.get("ok", False), "path": path, "files": files}

    async def push_file(self, local_path: str, device_path: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Push a local file to the device."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        if not os.path.exists(local_path):
            return {"ok": False, "error": f"Local file not found: {local_path}"}
        result = await self._adb(
            [*self._device_prefix(device), "push", local_path, device_path],
        )
        return {
            "ok": result.get("ok", False),
            "summary": result.get("stdout", "").strip() or "File pushed",
        }

    async def pull_file(self, device_path: str, local_path: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Pull a file from the device to the local machine."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "pull", device_path, local_path],
        )
        return {
            "ok": result.get("ok", False),
            "summary": result.get("stdout", "").strip() or "File pulled",
        }

    async def delete_file(self, device_path: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Delete a file on the device."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "shell", "rm", "-f", device_path],
        )
        return {"ok": result.get("ok", False), "summary": f"Deleted {device_path}"}

    # ────────────────────────────────────────────────────────
    # App launching
    # ────────────────────────────────────────────────────────

    async def list_apps(self, serial: Optional[str] = None, package_hint: str = "") -> Dict[str, Any]:
        """List installed packages on the device.

        Args:
            serial: Device serial
            package_hint: Optional filter substring
        """
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "shell", "pm", "list", "packages", "-3"],
        )
        packages = []
        for line in result.get("stdout", "").splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkg = line.split(":", 1)[1]
                if not package_hint or package_hint.lower() in pkg.lower():
                    packages.append(pkg)
        return {"ok": result.get("ok", False), "packages": packages}

    async def open_app(self, package: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Launch an app by package name.

        First attempts to resolve the launch activity, then starts it.
        """
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}

        # Resolve launch activity
        resolve = await self._adb(
            [*self._device_prefix(device), "shell", "cmd", "package", "resolve-activity",
             "--brief", package],
        )
        activity = None
        if resolve.get("ok"):
            for line in resolve.get("stdout", "").splitlines():
                line = line.strip()
                if "/" in line:
                    activity = line
                    break

        if activity:
            result = await self._adb(
                [*self._device_prefix(device), "shell", "am", "start", "-n", activity],
            )
        else:
            result = await self._adb(
                [*self._device_prefix(device), "shell", "monkey", "-p", package, "-c",
                 "android.intent.category.LAUNCHER", "1"],
            )
        return {
            "ok": result.get("ok", False),
            "summary": f"Launched {package}" if result.get("ok") else "Failed to launch app",
        }

    async def close_app(self, package: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Force-stop an app on the device."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "shell", "am", "force-stop", package],
        )
        return {"ok": result.get("ok", False), "summary": f"Stopped {package}"}

    # ────────────────────────────────────────────────────────
    # SMS (permission-gated)
    # ────────────────────────────────────────────────────────

    async def send_sms(self, phone_number: str, message: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Send an SMS (requires permission; uses `am start` SMS intent).

        NOTE: This requires the user to grant SMS permission. The command
        opens the SMS composer; actual send requires user confirmation
        unless a privileged SMS app is available.
        """
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}

        # Escape the message for the intent URI
        encoded = message.replace(" ", "%20").replace("\n", "%0A")
        result = await self._adb([
            *self._device_prefix(device),
            "shell", "am", "start", "-a", "android.intent.action.SENDTO",
            "-d", f"smsto:{phone_number}", "--es", "sms_body", message,
        ])
        return {
            "ok": result.get("ok", False),
            "summary": f"SMS composer opened for {phone_number} (user confirmation required)",
        }

    async def list_sms(self, serial: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """List recent SMS messages (requires SMS read permission)."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb([
            *self._device_prefix(device),
            "shell", "content", "query", "--uri",
            "content://sms/inbox", "--projection", "address,body,date,type",
            "--limit", str(limit),
        ])
        messages = []
        for line in result.get("stdout", "").splitlines():
            line = line.strip()
            if line.startswith("Row:"):
                parts = line.split(",")
                msg = {}
                for part in parts[1:]:
                    if "=" in part:
                        k, _, v = part.partition("=")
                        msg[k.strip()] = v.strip()
                messages.append(msg)
        return {"ok": result.get("ok", False), "messages": messages[:limit]}

    # ────────────────────────────────────────────────────────
    # Call status
    # ────────────────────────────────────────────────────────

    async def get_call_status(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Get current telephony call status."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "shell", "dumpsys", "telephony.registry"],
        )
        text = result.get("stdout", "")
        status = "idle"
        call_state = None
        m = re.search(r"mCallState=(\d+)", text)
        if m:
            state_map = {"0": "idle", "1": "ringing", "2": "offhook"}
            call_state = state_map.get(m.group(1), m.group(1))
        return {
            "ok": result.get("ok", False),
            "call_state": call_state or "unknown",
            "status": call_state or "unknown",
        }

    # ────────────────────────────────────────────────────────
    # Location
    # ────────────────────────────────────────────────────────

    async def get_location(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Get device location (requires location permission).

        Returns last known location if available.
        """
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        result = await self._adb(
            [*self._device_prefix(device), "shell", "dumpsys", "location"],
        )
        text = result.get("stdout", "")
        lat = lng = None
        m = re.search(r"last known location.*?Location\[.*?(-?[\d.]+),(-?[\d.]+)", text)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
        return {
            "ok": result.get("ok", False),
            "location": {"latitude": lat, "longitude": lng} if lat is not None else None,
        }

    # ────────────────────────────────────────────────────────
    # Screen
    # ────────────────────────────────────────────────────────

    async def screenshot(self, local_path: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Capture a screenshot and save it locally."""
        device = await self._require_device(serial)
        if not device:
            return {"ok": False, "error": "No device connected"}
        device_path = "/sdcard/dash_screen.png"
        capture = await self._adb(
            [*self._device_prefix(device), "shell", "screencap", "-p", device_path],
        )
        if not capture.get("ok"):
            return {"ok": False, "error": "Failed to capture screen"}
        pull = await self._adb(
            [*self._device_prefix(device), "pull", device_path, local_path],
        )
        await self._adb(
            [*self._device_prefix(device), "shell", "rm", "-f", device_path],
        )
        return {
            "ok": pull.get("ok", False),
            "summary": "Screenshot saved" if pull.get("ok") else "Screenshot failed",
            "path": local_path if pull.get("ok") else None,
        }


# Global singleton
_adb_service: Optional[AdbService] = None


def get_adb_service() -> AdbService:
    """Get or create the global AdbService singleton."""
    global _adb_service
    if _adb_service is None:
        _adb_service = AdbService()
    return _adb_service
