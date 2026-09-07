"""Tests for the DASH Proactive Intelligence layer (DASH 2.0, sections 5-7).

Covers signal detectors over fake context snapshots, engine gating (disable,
quiet hours, importance threshold, cooldown), persistent state, and the
briefing/end-of-day formatting.
"""

from __future__ import annotations

import json
import time

import pytest

from dash_backend.context.engine import EnvironmentContext
from dash_backend.proactive.engine import ProactiveEngine, DEFAULT_CONFIG
from dash_backend.proactive.signals import detect_signals
from dash_backend.proactive.state import ProactiveState
from dash_backend.proactive.briefing import format_briefing, format_end_of_day


# ── Fixtures ─────────────────────────────────────────────────────


# Config base that is never in quiet hours (0<=hour<0 is always false).
NO_QUIET = {**DEFAULT_CONFIG, "quiet_hours_start": 0, "quiet_hours_end": 0}


def make_snap(device=None, project=None, activity=None) -> EnvironmentContext:
    return EnvironmentContext(device=device or {}, project=project or {}, activity=activity or {})


class FakeContextEngine:
    """Duck-typed stand-in: returns a fixed snapshot."""

    def __init__(self, snap: EnvironmentContext):
        self._snap = snap

    async def snapshot_async(self, session=None, user_id=None, refresh=False):
        return self._snap


def make_engine(snap: EnvironmentContext, tmp_path) -> ProactiveEngine:
    state = ProactiveState(tmp_path / "state.json")
    return ProactiveEngine(state=state, context_engine=FakeContextEngine(snap))


# ── Detectors ────────────────────────────────────────────────────


def test_system_health_signals():
    snap = make_snap(
        device={
            "platform": "x",
            "cpu_percent": 95.0,
            "ram_percent": 92.0,
            "disk_percent": 95.0,
            "ram_used_mb": 9000,
            "ram_total_mb": 10000,
            "disk_free_gb": 5.0,
        }
    )
    ids = {s.id for s in detect_signals(snap)}
    assert "system_cpu_critical" in ids
    assert "system_ram_critical" in ids
    assert "system_disk_critical" in ids


def test_moderate_usage_uses_lower_importance():
    snap = make_snap(device={"cpu_percent": 87.0, "ram_percent": 40.0})
    sigs = detect_signals(snap)
    by_id = {s.id: s for s in sigs}
    assert by_id["system_cpu_high"].importance == 0.6
    assert "system_ram_high" not in by_id


def test_uncommitted_work_signal():
    snap = make_snap(project={"repo_name": "dash", "branch": "main", "changed_files": 4, "last_commit": "ab12c34 x | 2026-09-05"})
    sigs = detect_signals(snap)
    uncommitted = [s for s in sigs if s.id == "uncommitted_work"]
    assert len(uncommitted) == 1
    assert "4" in uncommitted[0].message


def test_stale_project_signal():
    snap = make_snap(project={"repo_name": "old", "branch": "main", "changed_files": 0, "last_commit": "ab12c34 x | 2020-01-01"})
    ids = {s.id for s in detect_signals(snap)}
    assert "stale_project" in ids
    assert "uncommitted_work" not in ids


def test_active_goals_signal():
    snap = make_snap(
        activity={"recent_goals": [{"name": "Ship DASH", "status": "running"}, {"name": "Cleanup", "status": "completed"}]}
    )
    sigs = detect_signals(snap)
    goals = [s for s in sigs if s.id == "active_goals"]
    assert len(goals) == 1
    assert goals[0].payload["count"] == 1


def test_empty_snapshot_no_signals():
    assert detect_signals(make_snap()) == []


# ── Engine gating ────────────────────────────────────────────────


async def test_disabled_returns_nothing(tmp_path):
    engine = make_engine(make_snap(device={"cpu_percent": 99.0}), tmp_path)
    cfg = {**DEFAULT_CONFIG, "enabled": False}
    assert await engine.evaluate(config=cfg) == []


async def test_quiet_hours_returns_nothing(tmp_path):
    engine = make_engine(make_snap(device={"cpu_percent": 99.0}), tmp_path)
    cfg = {**DEFAULT_CONFIG, "quiet_hours_start": 0, "quiet_hours_end": 23}
    assert engine.in_quiet_hours(cfg) is True
    assert await engine.evaluate(config=cfg) == []


async def test_importance_threshold_filters(tmp_path):
    snap = make_snap(device={"cpu_percent": 95.0, "ram_percent": 40.0})
    engine = make_engine(snap, tmp_path)
    strict = {**NO_QUIET, "importance_threshold": 0.8}
    results = await engine.evaluate(config=strict)
    assert [r["id"] for r in results] == ["system_cpu_critical"]


async def test_results_sorted_by_importance(tmp_path):
    snap = make_snap(
        device={"cpu_percent": 95.0, "ram_percent": 92.0},
        project={"repo_name": "dash", "branch": "main", "changed_files": 2, "last_commit": "a1 b | 2026-09-05"},
    )
    engine = make_engine(snap, tmp_path)
    results = await engine.evaluate(config=NO_QUIET)
    importances = [r["importance"] for r in results]
    assert importances == sorted(importances, reverse=True)
    assert results[0]["id"] == "system_cpu_critical"


async def test_cooldown_suppresses_repeat(tmp_path):
    snap = make_snap(project={"repo_name": "dash", "branch": "main", "changed_files": 2, "last_commit": "a1 b | 2026-09-05"})
    engine = make_engine(snap, tmp_path)
    cfg = {**NO_QUIET, "cooldown_minutes": 60}
    first = await engine.evaluate(config=cfg)
    assert [r["id"] for r in first] == ["uncommitted_work"]
    engine.record_shown("uncommitted_work", "title")
    assert await engine.evaluate(config=cfg) == []


async def test_evaluate_without_session_uses_default_config(tmp_path):
    snap = make_snap(project={"repo_name": "dash", "branch": "main", "changed_files": 1, "last_commit": "a1 b | 2026-09-05"})
    engine = make_engine(snap, tmp_path)
    results = await engine.evaluate(config=NO_QUIET)
    assert [r["id"] for r in results] == ["uncommitted_work"]


# ── State persistence ────────────────────────────────────────────


def test_state_persists_cooldown_and_history(tmp_path):
    path = tmp_path / "state.json"
    state = ProactiveState(path)
    assert state.last_shown("x") is None
    state.record_shown("x", "Some title")
    assert state.last_shown("x") is not None

    reloaded = ProactiveState(path)
    assert reloaded.last_shown("x") is not None
    hist = reloaded.history()
    assert hist[0]["id"] == "x"
    assert hist[0]["title"] == "Some title"


def test_state_survives_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")
    state = ProactiveState(path)
    assert state.last_shown("x") is None
    state.record_shown("x", "t")
    assert state.last_shown("x") is not None


# ── Briefing / end-of-day ────────────────────────────────────────


def test_format_briefing():
    text = format_briefing(
        {
            "date": "Monday, 2026-09-07",
            "system": "CPU 10% | RAM 50%",
            "project": "dash (branch main) — 2 modified file(s)",
            "goals": ["- Ship DASH [running]"],
            "attention": [{"title": "2 modified file(s) in dash"}],
        }
    )
    assert "Briefing for Monday" in text
    assert "CPU 10%" in text
    assert "- Ship DASH [running]" in text
    assert "Needs your attention" in text


def test_format_briefing_no_attention():
    text = format_briefing({"date": "x", "system": "ok", "project": "p", "goals": [], "attention": []})
    assert "Nothing needs your attention right now." in text


def test_format_end_of_day():
    text = format_end_of_day(
        {"window_hours": 24, "completed": {"goals": 2, "tasks": 5}, "commits": ["abc1234 feat: x", "def5678 fix: y"]}
    )
    assert "2 goal(s), 5 task(s)" in text
    assert "abc1234 feat: x" in text


async def test_build_briefing_without_db(tmp_path):
    engine = make_engine(make_snap(device={"cpu_percent": 40.0, "ram_percent": 40.0}), tmp_path)
    from dash_backend.proactive.briefing import build_briefing

    # Patch the singleton context engine used inside build_briefing.
    import dash_backend.proactive.briefing as briefing_mod

    orig = briefing_mod.get_context_engine
    briefing_mod.get_context_engine = lambda: engine._context_engine
    try:
        result = await build_briefing()
        assert "sections" in result
        assert "text" in result
        assert result["sections"]["date"]
    finally:
        briefing_mod.get_context_engine = orig