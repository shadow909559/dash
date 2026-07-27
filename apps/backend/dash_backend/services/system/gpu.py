"""GPU monitoring with graceful fallback when GPUtil is unavailable."""

from __future__ import annotations

import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_HAS_GPUTIL = False

try:
    import GPUtil as _gputil

    _HAS_GPUTIL = True
except ImportError:
    _gputil = None  # type: ignore[assignment]
    logger.info("GPUtil not available – GPU metrics will be null")

# Try WMI on Windows for additional GPU info
_HAS_WMI = False
try:
    import wmi as _wmi  # type: ignore[import-untyped]

    _HAS_WMI = True
except ImportError:
    _wmi = None  # type: ignore[assignment]


def get_gpu_info() -> list[dict[str, Any]]:
    """Return GPU stats for each detected GPU.

    Returns an empty list if no GPU is detected or libraries are unavailable.
    Each GPU entry contains:
        - name, usage_percent, memory_total_mb, memory_used_mb, memory_free_mb,
          temperature_celsius, vram_total_mb, vram_used_mb, vram_free_mb,
          power_draw_watts, fan_speed_percent, driver_version, uuid
    """
    gpus: list[dict[str, Any]] = []

    # Try GPUtil first (NVIDIA GPUs via nvidia-smi)
    if _HAS_GPUTIL and _gputil is not None:
        try:
            nv_gpus = _gputil.getGPUs()  # type: ignore[attr-defined]
            for g in nv_gpus:
                gpu_info = {
                    "name": g.name,
                    "usage_percent": round(g.load * 100, 1) if hasattr(g, "load") else None,
                    "memory_total_mb": g.memoryTotal if hasattr(g, "memoryTotal") else None,
                    "memory_used_mb": g.memoryUsed if hasattr(g, "memoryUsed") else None,
                    "memory_free_mb": g.memoryFree if hasattr(g, "memoryFree") else None,
                    "temperature_celsius": g.temperature if hasattr(g, "temperature") else None,
                    "vram_total_mb": g.memoryTotal if hasattr(g, "memoryTotal") else None,
                    "vram_used_mb": g.memoryUsed if hasattr(g, "memoryUsed") else None,
                    "vram_free_mb": g.memoryFree if hasattr(g, "memoryFree") else None,
                    "power_draw_watts": None,
                    "fan_speed_percent": None,
                    "driver_version": g.driver if hasattr(g, "driver") else None,
                    "uuid": g.uuid if hasattr(g, "uuid") else None,
                }
                # Try to get power draw and fan speed from nvidia-smi directly
                try:
                    import subprocess
                    smi_out = subprocess.check_output(
                        ["nvidia-smi", f"--id={g.id}", "--query-gpu=power.draw,fan.speed", "--format=csv,noheader,nounits"],
                        timeout=5, text=True
                    ).strip()
                    if smi_out:
                        parts = smi_out.split(",")
                        if len(parts) >= 1 and parts[0].strip():
                            gpu_info["power_draw_watts"] = round(float(parts[0].strip()), 1)
                        if len(parts) >= 2 and parts[1].strip():
                            gpu_info["fan_speed_percent"] = round(float(parts[1].strip()), 1)
                except Exception:
                    pass
                gpus.append(gpu_info)
        except Exception:
            logger.debug("GPUtil returned no GPUs (likely no NVIDIA GPU)")

    # If we found GPUs via GPUtil, return them
    if gpus:
        return gpus

    # Fallback: try WMI on Windows for GPU info (AMD, Intel, etc.)
    if _HAS_WMI:
        try:
            wmi_conn = _wmi.WMI()  # type: ignore[attr-defined]
            for video in wmi_conn.Win32_VideoController():  # type: ignore[attr-defined]
                name = video.Name if hasattr(video, "Name") else None
                if name:
                    gpu_info = {
                        "name": name,
                        "usage_percent": None,  # WMI doesn't easily give real-time usage
                        "memory_total_mb": None,
                        "memory_used_mb": None,
                        "memory_free_mb": None,
                        "temperature_celsius": None,
                        "vram_total_mb": None,
                        "vram_used_mb": None,
                        "vram_free_mb": None,
                        "power_draw_watts": None,
                        "fan_speed_percent": None,
                        "driver_version": video.DriverVersion if hasattr(video, "DriverVersion") else None,
                        "adapter_ram_mb": None,
                    }
                    # Try to get adapter RAM
                    try:
                        if hasattr(video, "AdapterRAM") and video.AdapterRAM:
                            gpu_info["adapter_ram_mb"] = round(int(video.AdapterRAM) / (1024 * 1024), 1)
                    except (ValueError, TypeError):
                        pass
                    gpus.append(gpu_info)
        except Exception:
            logger.debug("WMI GPU detection failed")

    return gpus