"""Analytics, activity dashboard, token tracker, cost tracker, and performance profiler."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Token & Cost Tracker ───────────────────────────────────────────────────

_PRICING: dict[str, dict] = {
    "openai": {"input": 0.003, "output": 0.015},  # per 1K tokens
    "anthropic": {"input": 0.008, "output": 0.024},
    "ollama": {"input": 0.0, "output": 0.0},
    "groq": {"input": 0.00059, "output": 0.00079},
    "gemini": {"input": 0.00125, "output": 0.005},
    "deepseek": {"input": 0.0014, "output": 0.0028},
}


class TokenTracker:
    """Track token usage and costs per provider, per day."""

    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._daily: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"input": 0, "output": 0, "cost": 0.0, "requests": 0}))

    def record(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> dict:
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        pricing = _PRICING.get(provider, _PRICING["openai"])
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000

        entry = {
            "timestamp": now.isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 6),
        }
        self._entries.append(entry)

        daily = self._daily[day][provider]
        daily["input"] += input_tokens
        daily["output"] += output_tokens
        daily["cost"] = round(daily["cost"] + cost, 6)
        daily["requests"] += 1

        return entry

    def get_today(self) -> dict:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        providers = dict(self._daily.get(day, {}))
        total_cost = sum(p.get("cost", 0) for p in providers.values())
        total_input = sum(p.get("input", 0) for p in providers.values())
        total_output = sum(p.get("output", 0) for p in providers.values())
        return {
            "date": day,
            "total_tokens": total_input + total_output,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_cost": round(total_cost, 4),
            "by_provider": providers,
        }

    def get_week(self) -> list[dict]:
        result = []
        today = datetime.now(timezone.utc).date()
        for i in range(7):
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            providers = dict(self._daily.get(day, {}))
            total_cost = sum(p.get("cost", 0) for p in providers.values())
            result.append({
                "date": day,
                "total_cost": round(total_cost, 4),
                "by_provider": providers,
            })
        return list(reversed(result))

    def get_month(self) -> list[dict]:
        result = []
        today = datetime.now(timezone.utc).date()
        for i in range(30):
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            providers = dict(self._daily.get(day, {}))
            total_cost = sum(p.get("cost", 0) for p in providers.values())
            result.append({"date": day, "total_cost": round(total_cost, 4)})
        return list(reversed(result))

    def get_total_cost(self) -> float:
        return round(sum(e.get("cost", 0) for e in self._entries), 4)

    def get_budget_status(self, monthly_limit: float = 50.0) -> dict:
        month_cost = sum(
            e.get("cost", 0) for e in self._entries
            if e.get("timestamp", "").startswith(datetime.now(timezone.utc).strftime("%Y-%m"))
        )
        return {
            "spent": round(month_cost, 4),
            "limit": monthly_limit,
            "remaining": round(max(0, monthly_limit - month_cost), 4),
            "percentage": round((month_cost / monthly_limit * 100) if monthly_limit > 0 else 0, 1),
            "alert": month_cost > monthly_limit * 0.8,
        }


# ── Activity Dashboard ─────────────────────────────────────────────────────

class ActivityDashboard:
    """Track user activity, productivity metrics, and usage patterns."""

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._daily_stats: dict[str, dict] = {}

    def record_event(self, event_type: str, detail: str = "", metadata: dict | None = None) -> None:
        now = datetime.now(timezone.utc)
        self._events.append({
            "type": event_type,
            "detail": detail,
            "metadata": metadata or {},
            "timestamp": now.isoformat(),
        })
        if len(self._events) > 10000:
            self._events = self._events[-5000:]

    def get_recent(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._events[-limit:]))

    def get_daily_summary(self) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_events = [e for e in self._events if e.get("timestamp", "").startswith(today)]

        type_counts: dict[str, int] = defaultdict(int)
        for e in today_events:
            type_counts[e["type"]] += 1

        return {
            "date": today,
            "total_events": len(today_events),
            "by_type": dict(type_counts),
            "hourly_distribution": self._hourly_distribution(today_events),
        }

    def get_weekly_summary(self) -> dict:
        result = []
        today = datetime.now(timezone.utc).date()
        for i in range(7):
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            day_events = [e for e in self._events if e.get("timestamp", "").startswith(day)]
            result.append({
                "date": day,
                "total_events": len(day_events),
                "types": list(set(e["type"] for e in day_events)),
            })
        return {"days": list(reversed(result))}

    @staticmethod
    def _hourly_distribution(events: list[dict]) -> dict[str, int]:
        hours: dict[str, int] = defaultdict(int)
        for e in events:
            try:
                h = e["timestamp"][11:13]
                hours[h] += 1
            except (IndexError, KeyError):
                pass
        return dict(hours)

    def get_productivity_score(self) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_events = [e for e in self._events if e.get("timestamp", "").startswith(today)]
        tasks = sum(1 for e in today_events if e["type"] in ("task_complete", "goal_complete"))
        messages = sum(1 for e in today_events if e["type"] == "message_sent")
        code_actions = sum(1 for e in today_events if e["type"] in ("code_edit", "code_review", "code_test"))
        score = min(100, tasks * 10 + messages * 2 + code_actions * 5)
        return {
            "date": today,
            "score": score,
            "tasks_completed": tasks,
            "messages_sent": messages,
            "code_actions": code_actions,
        }


# ── Performance Profiler ───────────────────────────────────────────────────

class PerformanceProfiler:
    """Track response times, identify slow operations, and measure performance."""

    def __init__(self) -> None:
        self._measurements: list[dict] = []
        self._active: dict[str, float] = {}

    def start(self, operation: str) -> None:
        self._active[operation] = time.perf_counter()

    def end(self, operation: str) -> dict:
        start = self._active.pop(operation, None)
        if start is None:
            return {"ok": False, "reason": "Operation not started"}
        duration_ms = (time.perf_counter() - start) * 1000
        entry = {
            "operation": operation,
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._measurements.append(entry)
        if len(self._measurements) > 5000:
            self._measurements = self._measurements[-2500:]
        return entry

    def get_slow_operations(self, threshold_ms: float = 1000) -> list[dict]:
        slow = [m for m in self._measurements if m["duration_ms"] > threshold_ms]
        return sorted(slow, key=lambda x: x["duration_ms"], reverse=True)[:50]

    def get_stats(self, operation: Optional[str] = None) -> dict:
        relevant = self._measurements
        if operation:
            relevant = [m for m in relevant if m["operation"] == operation]
        if not relevant:
            return {"count": 0}
        durations = [m["duration_ms"] for m in relevant]
        return {
            "operation": operation or "all",
            "count": len(durations),
            "avg_ms": round(sum(durations) / len(durations), 2),
            "min_ms": round(min(durations), 2),
            "max_ms": round(max(durations), 2),
            "p50_ms": round(sorted(durations)[len(durations) // 2], 2),
            "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0], 2),
            "p99_ms": round(sorted(durations)[int(len(durations) * 0.99)] if len(durations) > 1 else durations[0], 2),
        }

    def get_operations_summary(self) -> list[dict]:
        ops: dict[str, list[float]] = defaultdict(list)
        for m in self._measurements:
            ops[m["operation"]].append(m["duration_ms"])
        result = []
        for op, durations in ops.items():
            result.append({
                "operation": op,
                "count": len(durations),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "max_ms": round(max(durations), 2),
            })
        return sorted(result, key=lambda x: x["avg_ms"], reverse=True)

    def clear(self) -> dict:
        count = len(self._measurements)
        self._measurements.clear()
        return {"ok": True, "cleared": count}


# ── Error Log Viewer ───────────────────────────────────────────────────────

class ErrorLogViewer:
    """Structured error log with filtering and search."""

    def __init__(self) -> None:
        self._errors: list[dict] = []

    def log(self, level: str, message: str, source: str = "", stack: str = "", metadata: dict | None = None) -> None:
        entry = {
            "level": level,
            "message": message,
            "source": source,
            "stack": stack,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._errors.append(entry)
        if len(self._errors) > 5000:
            self._errors = self._errors[-2500:]

    def get_errors(self, level: Optional[str] = None, source: Optional[str] = None,
                    search: Optional[str] = None, limit: int = 100) -> list[dict]:
        result = self._errors
        if level:
            result = [e for e in result if e["level"] == level]
        if source:
            result = [e for e in result if source.lower() in e.get("source", "").lower()]
        if search:
            q = search.lower()
            result = [e for e in result if q in e.get("message", "").lower() or q in e.get("source", "").lower()]
        return list(reversed(result[-limit:]))

    def get_stats(self) -> dict:
        levels: dict[str, int] = defaultdict(int)
        sources: dict[str, int] = defaultdict(int)
        for e in self._errors:
            levels[e["level"]] += 1
            sources[e.get("source", "unknown")] += 1
        return {
            "total": len(self._errors),
            "by_level": dict(levels),
            "by_source": dict(sources),
            "recent_critical": len([e for e in self._errors[-100:] if e["level"] == "critical"]),
        }

    def clear(self) -> dict:
        count = len(self._errors)
        self._errors.clear()
        return {"ok": True, "cleared": count}


# Singletons
token_tracker = TokenTracker()
activity_dashboard = ActivityDashboard()
performance_profiler = PerformanceProfiler()
error_log_viewer = ErrorLogViewer()
