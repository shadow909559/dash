"""Tests for briefing and end-of-day trend integration.

Verifies that the daily briefing and end-of-day summary include device
trends from the predictive history when available, and omit them when
there is insufficient history.
"""

from __future__ import annotations

import pytest

from dash_backend.predictive.history import SampleStore
from dash_backend.proactive.briefing import (
    _trend_lines,
    build_briefing,
    build_end_of_day,
    format_briefing,
    format_end_of_day,
)


# ── _trend_lines ──────────────────────────────────────────────────


def test_trend_lines_empty_when_no_history(tmp_path):
    store = SampleStore(path=tmp_path / "empty.json")
    lines = _trend_lines(store)
    assert lines == []


def test_trend_lines_empty_when_insufficient_samples(tmp_path):
    store = SampleStore(path=tmp_path / "few.json")
    for i in range(3):
        store.append({"ts": 1000 + i * 300, "cpu_pct": 50.0, "ram_pct": 80.0, "disk_free_gb": 100.0})
    lines = _trend_lines(store)
    assert lines == []


def test_trend_lines_shows_stable_ram(tmp_path):
    store = SampleStore(path=tmp_path / "stable.json")
    for i in range(10):
        store.append({"ts": 1000 + i * 7200, "ram_pct": 85.0, "disk_free_gb": 100.0})
    lines = _trend_lines(store)
    # RAM is stable at ~85%
    assert any("RAM" in l and "stable" in l for l in lines)


def test_trend_lines_shows_falling_disk(tmp_path):
    store = SampleStore(path=tmp_path / "disk.json")
    for i in range(10):
        store.append({"ts": 1000 + i * 7200, "ram_pct": 80.0, "disk_free_gb": 100.0 - i * 2})
    lines = _trend_lines(store)
    assert any("Disk" in l and "falling" in l for l in lines)


def test_trend_lines_shows_rising_ram(tmp_path):
    store = SampleStore(path=tmp_path / "ram.json")
    for i in range(10):
        store.append({"ts": 1000 + i * 7200, "ram_pct": 50.0 + i * 3, "disk_free_gb": 100.0})
    lines = _trend_lines(store)
    assert any("RAM" in l and "rising" in l for l in lines)


# ── format_briefing with trends and predictions ───────────────────


def test_format_briefing_includes_trends():
    text = format_briefing({
        "date": "Monday, 2026-09-07",
        "system": "ok",
        "project": "dash",
        "goals": ["- Ship [pending]"],
        "deadlines": [],
        "trends": ["RAM: stable at ~85% over 8 hours", "Disk: falling 100 -> 87 GB over 14 days"],
        "top_risk": {"title": "Disk is shrinking", "payload": {"severity": "warning", "horizon": "~5 days"}},
        "attention": [],
    })
    assert "Device trends:" in text
    assert "RAM: stable at ~85%" in text
    assert "Disk: falling 100 -> 87" in text
    assert "Top risk:" in text
    assert "Disk is shrinking" in text


def test_format_briefing_omits_trends_when_empty():
    text = format_briefing({
        "date": "x",
        "system": "ok",
        "project": "p",
        "goals": [],
        "deadlines": [],
        "trends": [],
        "top_risk": None,
        "attention": [],
    })
    assert "Device trends:" not in text
    assert "Top risk:" not in text


# ── format_end_of_day with trends ────────────────────────────────


def test_format_end_of_day_includes_trends():
    text = format_end_of_day({
        "window_hours": 24,
        "completed": {"goals": 1, "tasks": 3},
        "commits": [],
        "trends": ["RAM: stable at ~82% over 12 hours"],
    })
    assert "Device trends:" in text
    assert "RAM: stable at ~82%" in text


def test_format_end_of_day_omits_trends_when_empty():
    text = format_end_of_day({
        "window_hours": 24,
        "completed": {"goals": 0, "tasks": 0},
        "commits": [],
        "trends": [],
    })
    assert "Device trends:" not in text


# ── Integration: build_briefing returns trend/prediction sections ──


async def test_build_briefing_has_trend_sections():
    result = await build_briefing()
    assert "sections" in result
    assert "trends" in result["sections"]
    assert "top_risk" in result["sections"]
    assert isinstance(result["sections"]["trends"], list)
    assert isinstance(result["text"], str)
    # The text should always be valid (even if trends/top_risk are empty)
    assert "Briefing for" in result["text"]
