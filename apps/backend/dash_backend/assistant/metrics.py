"""Assistant metrics (spec #45/#114/#115).

Real measurements only: every latency sample is recorded by the code
path that did the work (chat round-trip, STT, intent, TTS first-audio,
meeting ingest, approval resolve). Ring buffers are bounded, summaries
report avg/median/p95/p99 — never claimed, always measured. Values are
durations in milliseconds; no message content or secrets are recorded.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_MAX_SAMPLES = 500

_lock = threading.Lock()
_latencies: dict[str, deque[float]] = {}
_counters: dict[str, int] = {}
_errors: dict[str, int] = {}


def observe_latency(kind: str, ms: float) -> None:
    """Record one latency sample in milliseconds."""
    if not isinstance(ms, (int, float)) or ms < 0:
        return
    with _lock:
        buf = _latencies.setdefault(kind, deque(maxlen=_MAX_SAMPLES))
        buf.append(float(ms))


def incr_counter(kind: str, n: int = 1) -> None:
    with _lock:
        _counters[kind] = _counters.get(kind, 0) + n


def incr_error(kind: str) -> None:
    with _lock:
        _errors[kind] = _errors.get(kind, 0) + 1


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1,
              max(0, round(pct / 100.0 * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def summary() -> dict[str, Any]:
    """avg / median / p95 / p99 per latency kind, plus counters and
    error counts. This is the numbers endpoint — no invented values."""
    out: dict[str, Any] = {"generated_at": time.time(), "latency": {},
                           "counters": {}, "errors": {}}
    with _lock:
        for kind, buf in _latencies.items():
            vals = sorted(buf)
            n = len(vals)
            out["latency"][kind] = {
                "n": n,
                "avg_ms": round(sum(vals) / n, 1) if n else 0.0,
                "median_ms": round(_percentile(vals, 50), 1),
                "p95_ms": round(_percentile(vals, 95), 1),
                "p99_ms": round(_percentile(vals, 99), 1),
            }
        out["counters"] = dict(_counters)
        out["errors"] = dict(_errors)
    return out


def reset() -> None:
    """Test isolation only."""
    with _lock:
        _latencies.clear()
        _counters.clear()
        _errors.clear()
