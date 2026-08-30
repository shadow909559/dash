"""Device monitor - USB, Bluetooth, Audio, Displays, Printers, Cameras."""

from __future__ import annotations

import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def get_devices() -> dict[str, Any]:
    """Return detected devices grouped by type.

    Returns: usb_devices, bluetooth_devices, audio_devices, microphones,
             cameras, displays, printers.
    """
    result: dict[str, Any] = {
        "usb_devices": [],
        "bluetooth_devices": [],
        "audio_devices": [],
        "microphones": [],
        "cameras": [],
        "displays": [],
        "printers": [],
    }

    if platform.system() != "Windows":
        return result

    try:
        import subprocess

        # USB devices via WMIC
        try:
            usb_output_result = subprocess.run(
                ["wmic", "path", "Win32_USBControllerDevice", "get", "Dependent", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            usb_output = usb_output_result.stdout
            for line in usb_output.splitlines():
                if "Win32_PnPEntity" in line:
                    parts = line.split("=")
                    if len(parts) >= 2:
                        name = parts[-1].strip().replace('"', '')
                        result["usb_devices"].append({"name": name})
        except Exception:
            pass

        # Audio devices
        try:
            audio_output_result = subprocess.run(
                ["wmic", "path", "Win32_SoundDevice", "get", "Name,Status", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            audio_output = audio_output_result.stdout
            lines = audio_output.strip().splitlines()
            for line in lines[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        result["audio_devices"].append({
                            "name": parts[1] if len(parts) > 1 else None,
                            "status": parts[2] if len(parts) > 2 else None,
                        })
        except Exception:
            pass

        # Displays / monitors
        try:
            display_output_result = subprocess.run(
                ["wmic", "path", "Win32_DesktopMonitor", "get", "Name,MonitorType,Status", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            display_output = display_output_result.stdout
            lines = display_output.strip().splitlines()
            for line in lines[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        result["displays"].append({
                            "name": parts[1] if len(parts) > 1 else None,
                            "monitor_type": parts[2] if len(parts) > 2 else None,
                            "status": parts[3] if len(parts) > 3 else None,
                        })
        except Exception:
            pass

        # Printers
        try:
            printer_output_result = subprocess.run(
                ["wmic", "path", "Win32_Printer", "get", "Name,Status,Default", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            printer_output = printer_output_result.stdout
            lines = printer_output.strip().splitlines()
            for line in lines[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        result["printers"].append({
                            "name": parts[1] if len(parts) > 1 else None,
                            "status": parts[2] if len(parts) > 2 else None,
                            "is_default": parts[3].strip() == "TRUE" if len(parts) > 3 else False,
                        })
        except Exception:
            pass

        # Cameras via WMIC
        try:
            camera_output_result = subprocess.run(
                ["wmic", "path", "Win32_PnPEntity", "where", "ConfigManagerErrorCode=0",
                 "get", "Name", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            camera_output = camera_output_result.stdout
            for line in camera_output.splitlines():
                if "camera" in line.lower() or "webcam" in line.lower() or "imaging" in line.lower():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        result["cameras"].append({"name": parts[-1].strip()})
        except Exception:
            pass

        # Bluetooth devices
        try:
            bt_output_result = subprocess.run(
                ["wmic", "path", "Win32_PnPEntity", "where",
                 "PNPClass='Bluetooth' OR PNPClass='Bluetooth Radio'",
                 "get", "Name,Status", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            bt_output = bt_output_result.stdout
            lines = bt_output.strip().splitlines()
            for line in lines[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        result["bluetooth_devices"].append({
                            "name": parts[1] if len(parts) > 1 else None,
                            "status": parts[2] if len(parts) > 2 else None,
                        })
        except Exception:
            pass

        # Microphones (audio recording devices)
        try:
            mic_output_result = subprocess.run(
                ["wmic", "path", "Win32_PnPEntity", "where",
                 "PNPClass='AudioEndpoint' OR PNPClass='Microphone'",
                 "get", "Name,Status", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            mic_output = mic_output_result.stdout
            lines = mic_output.strip().splitlines()
            for line in lines[1:]:
                if line.strip() and ("microphone" in line.lower() or "mic" in line.lower()):
                    parts = line.split(",")
                    if len(parts) >= 2:
                        result["microphones"].append({
                            "name": parts[1] if len(parts) > 1 else None,
                            "status": parts[2] if len(parts) > 2 else None,
                        })
        except Exception:
            pass

    except Exception:
        logger.exception("Failed to enumerate devices")

    return result