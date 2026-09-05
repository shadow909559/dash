"""Battery monitoring with fallback."""

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


def _get_battery_extended_info() -> dict[str, Any]:
    """Get extended battery info via WMI on Windows: health, design capacity, etc."""
    result: dict[str, Any] = {}
    if platform.system() != "Windows":
        return result
    try:
        import subprocess
        # Get battery info via WMIC
        output_result = subprocess.run(
            ["wmic", "path", "Win32_Battery", "get", "*", "/format:csv"],
            capture_output=True, text=True, timeout=5
        )
        output = output_result.stdout
        lines = output.strip().splitlines()
        if len(lines) < 2:
            return result
        header = lines[0].split(",")
        values = lines[1].split(",")
        data = {}
        for i, h in enumerate(header):
            h = h.strip()
            if i < len(values):
                data[h] = values[i].strip()

        # Parse relevant fields
        if "DesignCapacity" in data and data["DesignCapacity"]:
            result["design_capacity_mwh"] = int(data["DesignCapacity"])
            result["design_capacity_wh"] = round(int(data["DesignCapacity"]) / 1000, 1)
        if "FullChargeCapacity" in data and data["FullChargeCapacity"]:
            result["full_charge_capacity_mwh"] = int(data["FullChargeCapacity"])
            result["full_charge_capacity_wh"] = round(int(data["FullChargeCapacity"]) / 1000, 1)
        if "EstimatedChargeRemaining" in data and data["EstimatedChargeRemaining"]:
            result["estimated_charge_remaining"] = int(data["EstimatedChargeRemaining"])
        if "BatteryStatus" in data and data["BatteryStatus"]:
            status = int(data["BatteryStatus"])
            result["battery_status_code"] = status
            # 1=Discharging, 2=AC power, 3=Fully Charged, 4=Low, 5=Critical, 6=Charging, 7=Charging High
            status_map = {
                1: "discharging", 2: "ac_power", 3: "fully_charged",
                4: "low", 5: "critical", 6: "charging", 7: "charging_high"
            }
            result["battery_status"] = status_map.get(status, f"unknown_{status}")
        if "Chemistry" in data and data["Chemistry"]:
            result["chemistry"] = data["Chemistry"]
        if "Manufacturer" in data and data["Manufacturer"]:
            result["manufacturer"] = data["Manufacturer"]
        if "Name" in data and data["Name"]:
            result["name"] = data["Name"]

        # Calculate health percentage if possible
        if "design_capacity_mwh" in result and "full_charge_capacity_mwh" in result:
            design = result["design_capacity_mwh"]
            full = result["full_charge_capacity_mwh"]
            if design and design > 0:
                result["health_percent"] = round((full / design) * 100, 1)
    except Exception:
        logger.debug("WMI battery extended info failed")
    return result


def get_battery_info() -> dict[str, Any]:
    """Return battery stats: percent, charging, remaining time, health, design capacity.

    Returns None values gracefully when battery is unavailable (desktop).
    """
    result: dict[str, Any] = {
        "percent": None,
        "charging": None,
        "remaining_seconds": None,
        "remaining_minutes": None,
        "plugged_in": None,
        "health_percent": None,
        "design_capacity_mwh": None,
        "design_capacity_wh": None,
        "full_charge_capacity_mwh": None,
        "full_charge_capacity_wh": None,
        "manufacturer": None,
        "chemistry": None,
        "battery_status": None,
    }

    # Get extended WMI info first
    extended = _get_battery_extended_info()
    result.update({k: v for k, v in extended.items() if k in result})

    # Get basic info from psutil
    if not _HAS_PSUTIL or _psutil is None:
        return result

    try:
        battery = _psutil.sensors_battery()
        if battery is not None:
            result["percent"] = round(battery.percent, 1)
            result["charging"] = battery.power_plugged
            result["plugged_in"] = battery.power_plugged

            # secsleft can be psutil.POWER_TIME_UNLIMITED (-1), psutil.POWER_TIME_UNKNOWN (-2)
            if battery.secsleft is not None and battery.secsleft > 0:
                result["remaining_seconds"] = battery.secsleft
                result["remaining_minutes"] = round(battery.secsleft / 60, 1)
    except (AttributeError, OSError):
        # sensors_battery may not be available on all platforms
        pass
    except Exception:
        logger.exception("Failed to collect battery info")

    return result