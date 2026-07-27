"""CPU and RAM monitoring with graceful fallback."""

from __future__ import annotations

import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

_HAS_PSUTIL = False
_HAS_CPUINFO = False

try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    logger.info("psutil not available – CPU/RAM metrics will be limited")

try:
    import cpuinfo as _cpuinfo

    _HAS_CPUINFO = True
except ImportError:
    _cpuinfo = None  # type: ignore[assignment]
    logger.info("py-cpuinfo not available – CPU frequency info will be limited")


def get_cpu_info() -> dict[str, Any]:
    """Return CPU stats: percent, cores, threads, frequency, temperature, voltage."""
    result: dict[str, Any] = {
        "percent": None,
        "percent_per_core": [],
        "cores_physical": None,
        "cores_logical": None,
        "frequency_current_mhz": None,
        "frequency_max_mhz": None,
        "frequency_min_mhz": None,
        "temperature_celsius": None,
        "voltage": None,
        "brand": None,
        "architecture": None,
    }

    try:
        if _HAS_PSUTIL and _psutil is not None:
            # Percent (non-blocking first call returns 0.0, so we do a short interval)
            result["percent"] = _psutil.cpu_percent(interval=0.1)
            result["percent_per_core"] = _psutil.cpu_percent(interval=0.1, percpu=True)
            result["cores_physical"] = _psutil.cpu_count(logical=False)
            result["cores_logical"] = _psutil.cpu_count(logical=True)

            # Frequency
            freq = _psutil.cpu_freq()
            if freq is not None:
                result["frequency_current_mhz"] = round(freq.current, 1) if freq.current else None
                result["frequency_max_mhz"] = round(freq.max, 1) if freq.max else None
                result["frequency_min_mhz"] = round(freq.min, 1) if freq.min else None

            # Temperature (cross-platform, may be empty)
            try:
                temps = _psutil.sensors_temperatures()
                if temps:
                    # Pick first available sensor
                    for name, entries in temps.items():
                        if entries:
                            result["temperature_celsius"] = round(entries[0].current, 1)
                            break
            except (AttributeError, OSError):
                pass

            # Voltage (Windows-specific via WMI)
            if platform.system() == "Windows":
                try:
                    import subprocess
                    output_result = subprocess.run(
                        ["wmic", "cpu", "get", "CurrentVoltage", "/format:csv"],
                        capture_output=True, text=True, timeout=5
                    )
                    output = output_result.stdout
                    lines = output.strip().splitlines()
                    for line in lines:
                        if "CurrentVoltage" not in line and line.strip():
                            parts = line.split(",")
                            if len(parts) >= 2 and parts[-1].strip():
                                voltage_raw = int(parts[-1].strip())
                                # WMIC reports voltage in tenths of volts
                                result["voltage"] = round(voltage_raw / 10.0, 2)
                                break
                except Exception:
                    pass
    except Exception:
        logger.exception("Failed to collect CPU info")

    # Brand / architecture from cpuinfo
    try:
        if _HAS_CPUINFO and _cpuinfo is not None:
            info = _cpuinfo.get_cpu_info()  # type: ignore[attr-defined]
            result["brand"] = info.get("brand_raw", None)
            result["architecture"] = info.get("arch", None)
    except Exception:
        logger.exception("Failed to get cpuinfo")

    # Fallback architecture
    if result["architecture"] is None:
        try:
            result["architecture"] = platform.machine()
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# RAM
# ---------------------------------------------------------------------------


def get_ram_info() -> dict[str, Any]:
    """Return RAM stats: used, free, total, percent, cached, committed, swap."""
    result: dict[str, Any] = {
        "total_bytes": None,
        "used_bytes": None,
        "free_bytes": None,
        "percent": None,
        "total_gb": None,
        "used_gb": None,
        "free_gb": None,
        "cached_bytes": None,
        "cached_gb": None,
        "committed_bytes": None,
        "committed_gb": None,
        "swap_total_bytes": None,
        "swap_used_bytes": None,
        "swap_free_bytes": None,
        "swap_total_gb": None,
        "swap_used_gb": None,
        "swap_free_gb": None,
        "swap_percent": None,
    }

    if not _HAS_PSUTIL or _psutil is None:
        return result

    try:
        mem = _psutil.virtual_memory()
        result["total_bytes"] = mem.total
        result["used_bytes"] = mem.used
        result["free_bytes"] = mem.available
        result["percent"] = mem.percent
        result["total_gb"] = round(mem.total / (1024**3), 2)
        result["used_gb"] = round(mem.used / (1024**3), 2)
        result["free_gb"] = round(mem.available / (1024**3), 2)
        result["cached_bytes"] = getattr(mem, "cached", None)
        if result["cached_bytes"] is not None:
            result["cached_gb"] = round(result["cached_bytes"] / (1024**3), 2)
        # Windows-specific: committed memory
        result["committed_bytes"] = getattr(mem, "committed", None)
        if result["committed_bytes"] is not None:
            result["committed_gb"] = round(result["committed_bytes"] / (1024**3), 2)
    except Exception:
        logger.exception("Failed to collect RAM info")

    # Swap memory
    try:
        swap = _psutil.swap_memory()
        result["swap_total_bytes"] = swap.total
        result["swap_used_bytes"] = swap.used
        result["swap_free_bytes"] = swap.free
        result["swap_total_gb"] = round(swap.total / (1024**3), 2) if swap.total else None
        result["swap_used_gb"] = round(swap.used / (1024**3), 2) if swap.used else None
        result["swap_free_gb"] = round(swap.free / (1024**3), 2) if swap.free else None
        result["swap_percent"] = swap.percent
    except Exception:
        logger.exception("Failed to collect swap info")

    return result