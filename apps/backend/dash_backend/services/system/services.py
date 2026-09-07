"""Windows Services monitor."""

from __future__ import annotations

import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def get_services() -> list[dict[str, Any]]:
    """Return list of Windows services with status and startup type.

    Each entry: name, display_name, status, start_type, description, pid.
    """
    services: list[dict[str, Any]] = []

    if platform.system() != "Windows":
        return services

    try:
        import subprocess
        output = subprocess.check_output(
            ["sc", "query", "type=", "service", "state=", "all"],
            timeout=10, text=True
        )
        # Parse sc query output
        current: dict[str, Any] = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("SERVICE_NAME"):
                if current:
                    services.append(current)
                current = {"name": line.split(":")[-1].strip()}
            elif "DISPLAY_NAME" in line:
                current["display_name"] = line.split(":")[-1].strip()
            elif "STATE" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    state_part = parts[-1].strip()
                    # Format: "4  RUNNING" or "1  STOPPED"
                    state_codes = {"1": "stopped", "2": "start_pending", "3": "stop_pending",
                                   "4": "running", "5": "continue_pending", "6": "pause_pending", "7": "paused"}
                    code = state_part.split()[0] if state_part.split() else ""
                    current["status"] = state_codes.get(code, state_part)
            elif "START_TYPE" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    start_part = parts[-1].strip()
                    start_codes = {"1": "boot", "2": "system", "3": "automatic",
                                   "4": "manual", "5": "disabled"}
                    code = start_part.split()[0] if start_part.split() else ""
                    current["start_type"] = start_codes.get(code, start_part)
            elif "PID" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    pid_str = parts[-1].strip()
                    try:
                        current["pid"] = int(pid_str) if pid_str != "0" else None
                    except ValueError:
                        current["pid"] = None

        if current:
            services.append(current)

    except Exception:
        logger.exception("Failed to enumerate services")

    return services


def get_services_summary() -> dict[str, int]:
    """Return summary counts of services by status and start type."""
    summary: dict[str, int] = {
        "running": 0,
        "stopped": 0,
        "automatic": 0,
        "manual": 0,
        "disabled": 0,
        "total": 0,
    }
    services = get_services()
    summary["total"] = len(services)
    for svc in services:
        status = svc.get("status", "")
        if status == "running":
            summary["running"] += 1
        elif status == "stopped":
            summary["stopped"] += 1
        start_type = svc.get("start_type", "")
        if start_type == "automatic":
            summary["automatic"] += 1
        elif start_type == "manual":
            summary["manual"] += 1
        elif start_type == "disabled":
            summary["disabled"] += 1
    return summary