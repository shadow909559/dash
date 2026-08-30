"""System-level info: OS version, username, uptime, build, boot time."""

from __future__ import annotations

import getpass
import os
import platform
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_HAS_PSUTIL = False

try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _psutil = None  # type: ignore[assignment]

# Track boot time for uptime calculation
_boot_time: float | None = None


def _get_boot_time() -> float:
    """Get system boot time (epoch seconds)."""
    global _boot_time
    if _boot_time is not None:
        return _boot_time

    try:
        if _HAS_PSUTIL and _psutil is not None:
            _boot_time = _psutil.boot_time()
            return _boot_time
    except Exception:
        pass

    # Fallback
    _boot_time = time.time()
    return _boot_time


def get_system_info() -> dict[str, Any]:
    """Return system info: Windows version, username, uptime, platform details, build."""
    result: dict[str, Any] = {
        "os": None,
        "os_version": None,
        "os_release": None,
        "os_build": None,
        "architecture": None,
        "hostname": None,
        "username": None,
        "uptime_seconds": None,
        "uptime_formatted": None,
        "boot_time": None,
        "platform": None,
        "python_version": None,
    }

    try:
        result["os"] = platform.system()
        result["os_version"] = platform.version()
        result["os_release"] = platform.release()
        result["architecture"] = platform.machine()
        result["hostname"] = platform.node()
        result["platform"] = platform.platform()
        result["python_version"] = platform.python_version()
    except Exception:
        logger.exception("Failed to get platform info")

    # Username
    try:
        result["username"] = getpass.getuser()
    except Exception:
        try:
            result["username"] = os.environ.get("USERNAME") or os.environ.get("USER") or None
        except Exception:
            pass

    # Uptime and boot time
    try:
        boot = _get_boot_time()
        result["boot_time"] = boot
        uptime_secs = time.time() - boot
        result["uptime_seconds"] = round(uptime_secs, 1)
        days, rem = divmod(int(uptime_secs), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        result["uptime_formatted"] = " ".join(parts)
    except Exception:
        logger.exception("Failed to compute uptime")

    # Windows-specific: get Windows version from registry
    if platform.system() == "Windows":
        try:
            import subprocess
            cmd_result = subprocess.run(
                ["cmd", "/c", "ver"], capture_output=True, text=True, timeout=5
            )
            output = cmd_result.stdout.strip()
            if output:
                result["os_version"] = output
        except Exception:
            pass

        # Get Windows build number
        try:
            import subprocess
            wmic_result = subprocess.run(
                ["wmic", "os", "get", "BuildNumber,Version", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = wmic_result.stdout.strip()
            lines = output.splitlines()
            for line in lines:
                if "BuildNumber" not in line and line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        result["os_build"] = parts[-2].strip() if parts[-2].strip() else None
        except Exception:
            pass

    # Live resource metrics (psutil)
    try:
        import psutil as _psutil
        result["cpu_percent"] = _psutil.cpu_percent(interval=0.5)
        mem = _psutil.virtual_memory()
        result["memory_percent"] = round(mem.percent, 1)
        result["memory_total_gb"] = round(mem.total / (1024**3), 1)
        result["memory_used_gb"] = round(mem.used / (1024**3), 1)
        disk = _psutil.disk_usage("/")
        result["disk_percent"] = round(disk.percent, 1)
        result["disk_total_gb"] = round(disk.total / (1024**3), 1)
        result["disk_used_gb"] = round(disk.used / (1024**3), 1)
    except Exception:
        logger.debug("Failed to collect live resource metrics")

    # GPU metrics via nvidia-smi (NVIDIA GPUs)
    try:
        import subprocess
        result_gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,name", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result_gpu.returncode == 0 and result_gpu.stdout.strip():
            parts = result_gpu.stdout.strip().split(", ")
            if len(parts) >= 4:
                result["gpu_usage"] = float(parts[0])
                result["gpu_memory_used_mb"] = float(parts[1])
                result["gpu_memory_total_mb"] = float(parts[2])
                result["gpu_name"] = parts[3].strip()
    except Exception:
        pass  # No NVIDIA GPU or nvidia-smi not found

    return result