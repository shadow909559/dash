"""Daily Health Report — runs at 8am, summarizes yesterday's agent activity.

Checks:
  1. System health (CPU, RAM, disk, network)
  2. What goals the agent completed/failed yesterday
  3. Memory and experience statistics
  4. Service health (Ollama, backend, cloud relay)

Sends the report as a WebSocket broadcast and stores it as a memory.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def _time_of_day(hour: int) -> str:
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    else:
        return "evening"


async def generate_daily_report() -> dict[str, Any]:
    """Generate a comprehensive daily health report."""
    now = datetime.now(timezone.utc)
    local_now = now + timedelta(hours=5, minutes=30)  # IST
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start + timedelta(days=1)

    report: dict[str, Any] = {
        "timestamp": now.isoformat(),
        "greeting": f"Good {_time_of_day(local_now.hour)}, sir.",
        "date": local_now.strftime("%A, %B %d, %Y"),
        "sections": {},
    }

    # ── Section 1: System Health ──────────────────────────────
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        report["sections"]["system"] = {
            "cpu_percent": cpu,
            "ram_percent": ram.percent,
            "ram_used_gb": round(ram.used / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "status": "healthy" if cpu < 80 and ram.percent < 85 and disk.percent < 90 else "warning",
        }

        # Battery (laptop)
        battery = psutil.sensors_battery()
        if battery:
            report["sections"]["system"]["battery_percent"] = battery.percent
            report["sections"]["system"]["battery_plugged"] = battery.power_plugged
    except Exception as exc:
        report["sections"]["system"] = {"status": "error", "error": str(exc)}

    # ── Section 2: Yesterday's Agent Activity ─────────────────
    try:
        from dash_backend.autonomous.experience import get_experience_cache
        cache = get_experience_cache()
        await cache.load_from_db()

        goals_completed = 0
        goals_failed = 0
        tools_used = set()

        for exp in cache._experiences:
            ts = exp.timestamp
            if yesterday_start.timestamp() <= ts < yesterday_end.timestamp():
                if exp.success:
                    goals_completed += 1
                else:
                    goals_failed += 1
                for t in exp.tool_sequence:
                    if t.get("success"):
                        tools_used.add(t["tool"])

        report["sections"]["yesterday"] = {
            "goals_completed": goals_completed,
            "goals_failed": goals_failed,
            "tools_used": sorted(tools_used),
            "total_experiences": len(cache._experiences),
        }
    except Exception as exc:
        report["sections"]["yesterday"] = {"status": "error", "error": str(exc)}

    # ── Section 3: Memory Stats ───────────────────────────────
    try:
        from dash_backend.intelligence.memory_service import MemoryService
        svc = MemoryService()
        uid = "00000000-0000-0000-0000-000000000001"
        memories = await svc.get_user_memories(uid, limit=1000)
        report["sections"]["memory"] = {
            "total_memories": len(memories),
            "long_term": sum(1 for m in memories if getattr(m, 'memory_type', '') in ("long_term", "goal_outcome", "experience")),
            "short_term": sum(1 for m in memories if getattr(m, 'memory_type', '') == "short_term"),
        }
    except Exception as exc:
        report["sections"]["memory"] = {"status": "error", "error": str(exc)}

    # ── Section 4: Service Health ─────────────────────────────
    services = {}

    # Ollama
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", 11434))
        s.close()
        services["ollama"] = "running" if result == 0 else "stopped"
    except Exception:
        services["ollama"] = "error"

    # Backend (self-check — we're running so it's up)
    services["backend"] = "running"

    report["sections"]["services"] = services

    # ── Build Summary ─────────────────────────────────────────
    sys = report["sections"].get("system", {})
    yest = report["sections"].get("yesterday", {})

    summary_parts = []
    if sys.get("status") == "healthy":
        summary_parts.append(f"System healthy — CPU {sys.get('cpu_percent', '?')}%, RAM {sys.get('ram_percent', '?')}%, Disk {sys.get('disk_free_gb', '?')}GB free")
    elif sys.get("status") == "warning":
        summary_parts.append(f"System warning — CPU {sys.get('cpu_percent', '?')}%, RAM {sys.get('ram_percent', '?')}%, Disk {sys.get('disk_percent', '?')}% used")

    completed = yest.get("goals_completed", 0)
    failed = yest.get("goals_failed", 0)
    if completed or failed:
        summary_parts.append(f"Yesterday: {completed} goals completed, {failed} failed")
    else:
        summary_parts.append("No agent activity yesterday")

    ollama = services.get("ollama", "unknown")
    summary_parts.append(f"Ollama: {ollama}")

    report["summary"] = ". ".join(summary_parts) + "."

    return report


def _format_report_text(report: dict[str, Any]) -> str:
    """Format report as human-readable text for chat/TTS."""
    lines = [report.get("greeting", "Good morning, sir.")]
    lines.append(f"Today is {report.get('date', 'unknown')}.")

    sys = report.get("sections", {}).get("system", {})
    if sys.get("status") == "healthy":
        lines.append(f"System is healthy. CPU at {sys.get('cpu_percent', 0)}%, "
                      f"RAM at {sys.get('ram_percent', 0)}% with {sys.get('ram_total_gb', 0)}GB total, "
                      f"and {sys.get('disk_free_gb', 0)}GB free disk space.")
    elif sys.get("status") == "warning":
        lines.append(f"System needs attention. CPU at {sys.get('cpu_percent', 0)}%, "
                      f"RAM at {sys.get('ram_percent', 0)}%.")
    elif sys.get("status") == "error":
        lines.append(f"System health unavailable: {sys.get('error', 'unknown error')}.")

    bat = sys.get("battery_percent")
    if bat is not None:
        plugged = sys.get("battery_plugged", False)
        lines.append(f"Battery at {bat}%{' and charging' if plugged else ', consider charging'}.")

    yest = report.get("sections", {}).get("yesterday", {})
    completed = yest.get("goals_completed", 0)
    failed = yest.get("goals_failed", 0)
    if completed or failed:
        lines.append(f"Yesterday I completed {completed} tasks"
                      + (f" and {failed} failed" if failed else "") + ".")
        tools = yest.get("tools_used", [])
        if tools:
            lines.append(f"Tools used: {', '.join(tools[:5])}.")
    else:
        lines.append("No tasks were executed yesterday.")

    mem = report.get("sections", {}).get("memory", {})
    total = mem.get("total_memories", 0)
    if total:
        lines.append(f"I have {total} memories stored across sessions.")

    return " ".join(lines)
