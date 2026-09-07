"""Event log collector - System errors, warnings, critical events."""

from __future__ import annotations

import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def get_event_logs(
    max_entries: int = 100,
    log_name: str = "System",
    levels: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return recent event log entries from Windows.

    Args:
        max_entries: Maximum number of entries to return.
        log_name: Log name to read (System, Application, Security).
        levels: Filter by level (Error, Warning, Critical, Information).

    Returns:
        List of event log entries with time, level, source, message, event_id.
    """
    entries: list[dict[str, Any]] = []

    if platform.system() != "Windows":
        return entries

    try:
        import subprocess
        import xml.etree.ElementTree as ET

        # Use wevtutil to query event logs
        cmd = ["wevtutil", "qe", log_name, f"/c:{max_entries}", "/rd:true", "/format:xml"]
        if levels:
            level_filters = []
            level_map = {"Error": "2", "Warning": "3", "Critical": "1", "Information": "4"}
            for level in levels:
                if level in level_map:
                    level_filters.append(f"Level={level_map[level]}")
            if level_filters:
                xpath = f'*[System[{" or ".join(level_filters)}]]'
                cmd.append(f"/q:{xpath}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout

        # Parse XML output
        try:
            root = ET.fromstring(output)
            for event_elem in root.findall(".//{http://schemas.microsoft.com/win/2004/08/events/event}Event"):
                system = event_elem.find("{http://schemas.microsoft.com/win/2004/08/events/event}System")
                if system is None:
                    continue

                event_id_elem = system.find("{http://schemas.microsoft.com/win/2004/08/events/event}EventID")
                level_elem = system.find("{http://schemas.microsoft.com/win/2004/08/events/event}Level")
                time_elem = system.find("{http://schemas.microsoft.com/win/2004/08/events/event}TimeCreated")
                provider_elem = system.find("{http://schemas.microsoft.com/win/2004/08/events/event}Provider")

                event_data = event_elem.find("{http://schemas.microsoft.com/win/2004/08/events/event}EventData")
                message = ""
                if event_data is not None:
                    for data in event_data:
                        if data.text:
                            message += data.text + " "

                level_num = int(level_elem.text) if level_elem is not None and level_elem.text else 0
                level_map = {1: "Critical", 2: "Error", 3: "Warning", 4: "Information"}
                level_str = level_map.get(level_num, f"Level_{level_num}")

                entry = {
                    "event_id": int(event_id_elem.text) if event_id_elem is not None and event_id_elem.text else None,
                    "level": level_str,
                    "time_created": time_elem.get("SystemTime") if time_elem is not None else None,
                    "provider": provider_elem.get("Name") if provider_elem is not None else None,
                    "message": message.strip()[:500] if message else None,
                    "log_name": log_name,
                }
                entries.append(entry)
        except ET.ParseError:
            pass

    except Exception:
        logger.debug("Failed to query event log %s", log_name)

    return entries


def get_system_errors(max_entries: int = 50) -> list[dict[str, Any]]:
    """Return recent system errors and critical events."""
    return get_event_logs(
        max_entries=max_entries,
        log_name="System",
        levels=["Error", "Critical"],
    )


def get_application_errors(max_entries: int = 50) -> list[dict[str, Any]]:
    """Return recent application errors and warnings."""
    return get_event_logs(
        max_entries=max_entries,
        log_name="Application",
        levels=["Error", "Warning", "Critical"],
    )


def get_event_summary() -> dict[str, Any]:
    """Return summary of recent events across logs."""
    system_errors = get_system_errors(max_entries=20)
    app_errors = get_application_errors(max_entries=20)

    return {
        "system_errors": system_errors,
        "application_errors": app_errors,
        "total_system_errors": len(system_errors),
        "total_application_errors": len(app_errors),
        "critical_count": sum(1 for e in system_errors + app_errors if e.get("level") == "Critical"),
        "error_count": sum(1 for e in system_errors + app_errors if e.get("level") == "Error"),
        "warning_count": sum(1 for e in system_errors + app_errors if e.get("level") == "Warning"),
    }