"""Process monitoring – top processes by CPU / memory usage with search and sort."""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_HAS_PSUTIL = False

try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _psutil = None  # type: ignore[assignment]


def get_processes(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "cpu_percent",
    sort_desc: bool = True,
    search: str | None = None,
) -> dict[str, Any]:
    """Return process list with search, sort, and pagination.

    Each entry: pid, name, cpu_percent, memory_percent, memory_mb, status, username,
                created_at, cmdline, exe, num_threads.
    """
    result: dict[str, Any] = {
        "processes": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
    }

    if not _HAS_PSUTIL or _psutil is None:
        return result

    all_processes: list[dict[str, Any]] = []

    try:
        for proc in _psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent", "memory_info",
             "status", "username", "create_time", "cmdline", "exe", "num_threads"]
        ):
            try:
                info = proc.info
                mem_mb = None
                if info.get("memory_info"):
                    mem_mb = round(info["memory_info"].rss / (1024 * 1024), 1)

                p = {
                    "pid": info["pid"],
                    "name": info["name"] or "unknown",
                    "cpu_percent": info["cpu_percent"] or 0.0,
                    "memory_percent": round(info["memory_percent"] or 0.0, 1),
                    "memory_mb": mem_mb,
                    "status": info["status"] or "unknown",
                    "username": info["username"],
                    "created_at": info["create_time"],
                    "cmdline": " ".join(info["cmdline"]) if info.get("cmdline") else None,
                    "exe": info["exe"],
                    "num_threads": info["num_threads"],
                }
                # Apply search filter
                if search:
                    search_lower = search.lower()
                    if (p["name"] and search_lower in p["name"].lower()) or \
                       (p["cmdline"] and search_lower in p["cmdline"].lower()) or \
                       str(p["pid"]) == search:
                        all_processes.append(p)
                else:
                    all_processes.append(p)
            except (OSError, _psutil.NoSuchProcess, _psutil.AccessDenied):  # type: ignore[attr-defined]
                continue

        # Sort
        sort_key = sort_by if sort_by in ("cpu_percent", "memory_percent", "memory_mb", "pid", "name") else "cpu_percent"
        reverse = sort_desc
        if sort_key == "name":
            reverse = not sort_desc
        all_processes.sort(key=lambda p: p.get(sort_key) or 0, reverse=reverse)

        result["total"] = len(all_processes)

        # Paginate
        end = offset + limit
        result["processes"] = all_processes[offset:end]

    except Exception:
        logger.exception("Failed to collect process info")

    return result


def get_top_processes(limit: int = 10) -> list[dict[str, Any]]:
    """Return top processes sorted by CPU usage (descending) - legacy compatibility."""
    data = get_processes(limit=limit, sort_by="cpu_percent", sort_desc=True)
    return data["processes"]