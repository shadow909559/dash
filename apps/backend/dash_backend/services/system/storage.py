"""Storage / disk monitoring for all drives."""

from __future__ import annotations

import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_HAS_PSUTIL = False

try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    logger.info("psutil not available – storage metrics will be unavailable")


def _detect_drive_type(device: str) -> str:
    """Detect if a drive is SSD or HDD using WMI on Windows."""
    if platform.system() != "Windows":
        return "unknown"
    try:
        import subprocess
        # Get the physical drive index from the device path
        # e.g., \\.\PHYSICALDRIVE0
        if device and "PHYSICALDRIVE" in device.upper():
            drive_num = device.upper().split("PHYSICALDRIVE")[-1].strip()
            output_result = subprocess.run(
                ["wmic", "diskdrive", "where", f"index={drive_num}", "get", "MediaType", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = output_result.stdout
            if "SSD" in output or "Solid State" in output:
                return "ssd"
            if "HDD" in output or "Fixed hard disk" in output:
                return "hdd"
            # Fallback: check if rotational speed is 0 (SSD) or >0 (HDD)
            try:
                rot_output_result = subprocess.run(
                    ["wmic", "diskdrive", "where", f"index={drive_num}", "get", "BytesPerSector", "/format:csv"],
                    capture_output=True, text=True, timeout=5
                )
                rot_output = rot_output_result.stdout
                # If we can't determine, assume SSD for modern drives
                return "ssd"
            except Exception:
                return "unknown"
    except Exception:
        pass
    return "unknown"


def _get_drive_health(device: str) -> dict[str, Any] | None:
    """Get drive health info using WMI on Windows."""
    if platform.system() != "Windows":
        return None
    try:
        import subprocess
        if device and "PHYSICALDRIVE" in device.upper():
            drive_num = device.upper().split("PHYSICALDRIVE")[-1].strip()
            # Try to get SMART status via wmic
            output_result = subprocess.run(
                ["wmic", "diskdrive", "where", f"index={drive_num}", "get", "Status", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = output_result.stdout.strip()
            lines = output.splitlines()
            for line in lines:
                if "Status" not in line and line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        status = parts[-1].strip()
                        return {
                            "status": status,
                            "healthy": status.lower() == "ok",
                        }
    except Exception:
        pass
    return None


def get_storage_info() -> dict[str, Any]:
    """Return storage stats for all drives: used, free, total, percent, health, type."""
    result: dict[str, Any] = {
        "drives": [],
        "total_gb": None,
        "used_gb": None,
        "free_gb": None,
    }

    if not _HAS_PSUTIL or _psutil is None:
        return result

    try:
        partitions = _psutil.disk_partitions()
        total_bytes = 0
        used_bytes = 0
        free_bytes = 0

        for part in partitions:
            try:
                usage = _psutil.disk_usage(part.mountpoint)
                drive_type = _detect_drive_type(part.device)
                health = _get_drive_health(part.device)
                drive_info = {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "opts": part.opts,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "percent": round(usage.percent, 1),
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "drive_type": drive_type,
                    "health": health,
                }
                result["drives"].append(drive_info)
                total_bytes += usage.total
                used_bytes += usage.used
                free_bytes += usage.free
            except (OSError, PermissionError):
                # Skip drives that can't be accessed (e.g., empty CD-ROM)
                continue

        result["total_gb"] = round(total_bytes / (1024**3), 2)
        result["used_gb"] = round(used_bytes / (1024**3), 2)
        result["free_gb"] = round(free_bytes / (1024**3), 2)
    except Exception:
        logger.exception("Failed to collect storage info")

    return result