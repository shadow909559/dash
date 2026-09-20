"""Soak analysis tests (decisions.md #64): the timeline/verdict logic of
scripts/soak_schedule.py, proven hermetically — no backend, no waiting.

The soak runner is a long-horizon integration script (10 real minutes);
what CAN be fast-tested is the honest accounting that decides PASS/FAIL:
every minute is classified OK / X2 / MISS_HARD / MISS_GRACE /
EXPECTED_DOWN, source!=scheduled never contaminates the timeline, and the
verdict fails only on double-fires or hard misses. All datetimes here are
passed as UTC with local_tz=UTC, so boundary keys equal UTC minutes.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "soak_schedule",
    Path(__file__).resolve().parents[1] / "scripts" / "soak_schedule.py",
)
soak = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(soak)

UTC = timezone.utc
BASE = datetime(2026, 9, 14, 22, 0, 0, tzinfo=UTC)  # first boundary minute


def _fire(minute_offset: int, second: int = 2, exec_id: str | None = None) -> dict:
    """A scheduled fire at BASE + N minutes (UTC started_at, as the API returns)."""
    ts = BASE + timedelta(minutes=minute_offset, seconds=second)
    return {
        "id": exec_id or f"exec_{minute_offset:03d}",
        "started_at": ts.isoformat(),
        "source": "scheduled",
    }


READY0 = BASE - timedelta(minutes=1)  # first boot ready before the window


def test_clean_run_every_minute_fires_once() -> None:
    fires = [_fire(i, exec_id=f"e{i}") for i in range(10)]
    report = soak.analyze_soak(fires, down_windows=[], first_ready=READY0, local_tz=UTC)
    assert report["verdict"] == "CLEAN"
    assert len(report["minutes"]) == 10
    assert all(m["status"] == "OK" and m["fires"] == 1 for m in report["minutes"])
    assert report["summary"]["ok"] == 10
    assert report["minutes"][0]["exec_ids"] == ["e0"]


def test_double_fire_in_one_minute_fails_the_run() -> None:
    fires = [_fire(0), _fire(0, second=40, exec_id="dup"), _fire(1), _fire(2)]
    report = soak.analyze_soak(fires, down_windows=[], first_ready=READY0, local_tz=UTC)
    assert report["verdict"] == "FAILED"
    x2 = [m for m in report["minutes"] if m["status"] == "X2"]
    assert len(x2) == 1 and x2[0]["fires"] == 2
    assert x2[0]["exec_ids"] == ["exec_000", "dup"]
    assert report["summary"]["double"] == 1
    # The innocent minutes stay OK.
    assert [m["status"] for m in report["minutes"]] == ["X2", "OK", "OK"]


def test_hard_miss_when_backend_was_up() -> None:
    fires = [_fire(0), _fire(1), _fire(3)]  # minute 2 missing, backend up
    report = soak.analyze_soak(fires, down_windows=[], first_ready=READY0, local_tz=UTC)
    assert report["verdict"] == "FAILED"
    miss = [m for m in report["minutes"] if m["status"] == "MISS_HARD"]
    assert len(miss) == 1
    assert miss[0]["minute"] == (BASE + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
    assert report["summary"]["miss_hard"] == 1


def test_expected_down_minute_is_not_a_failure() -> None:
    fires = [_fire(0), _fire(2)]  # minute 1 falls inside the restart gap
    gap_start = BASE + timedelta(minutes=1)
    down = [(gap_start, gap_start + timedelta(seconds=45))]
    report = soak.analyze_soak(fires, down_windows=down, first_ready=READY0, local_tz=UTC)
    assert report["verdict"] == "CLEAN"
    statuses = [m["status"] for m in report["minutes"]]
    assert statuses == ["OK", "EXPECTED_DOWN", "OK"]
    assert report["summary"]["expected_down"] == 1


def test_no_fires_at_all_is_its_own_verdict() -> None:
    report = soak.analyze_soak([], down_windows=[], first_ready=BASE, local_tz=UTC)
    assert report["verdict"] == "NO_FIRES"
    assert report["minutes"] == []


def test_post_restart_grace_miss_is_visible_not_fatal() -> None:
    # Minute 1 has no fire; the restart became ready 4s before that
    # boundary — within GRACE_S, so ~! instead of a hard miss.
    fires = [_fire(0), _fire(2)]
    gap_end = BASE + timedelta(minutes=1) - timedelta(seconds=4)
    down = [(gap_end - timedelta(seconds=30), gap_end)]
    report = soak.analyze_soak(fires, down_windows=down, first_ready=READY0, local_tz=UTC)
    statuses = [m["status"] for m in report["minutes"]]
    assert statuses == ["OK", "MISS_GRACE", "OK"]
    assert report["verdict"] == "CLEAN_WITH_GRACE_MISS"


def test_tz_aware_inputs_are_normalized_not_fatal() -> None:
    """The runner passes tz-aware datetimes; the analysis must not raise
    on aware/naive subtraction (bug found by self-review before first run)."""
    fires = [_fire(0), _fire(2)]
    down = [
        (
            (BASE + timedelta(minutes=1)).replace(tzinfo=UTC),
            (BASE + timedelta(minutes=1, seconds=45)).replace(tzinfo=UTC),
        )
    ]
    report = soak.analyze_soak(
        fires, down_windows=down, first_ready=READY0.replace(tzinfo=UTC), local_tz=UTC
    )
    assert report["verdict"] == "CLEAN"
    assert report["summary"]["expected_down"] == 1


def test_wrong_source_never_enters_the_timeline() -> None:
    all_runs = [
        _fire(0),
        _fire(1),
        {**_fire(2), "source": "webhook"},
        {**_fire(3), "source": "manual"},
    ]
    fires = [f for f in all_runs if f.get("source") == "scheduled"]
    report = soak.analyze_soak(fires, down_windows=[], first_ready=READY0, local_tz=UTC)
    assert report["verdict"] == "CLEAN"
    assert len(report["minutes"]) == 2  # webhook/manual runs are invisible here


def test_render_timeline_marks_every_state() -> None:
    fires = [
        _fire(0),
        _fire(1), _fire(1, second=40, exec_id="dup"),
        # minute 2: backend down; minute 3: UP and silent -> MISS_HARD
        _fire(4),
    ]
    down = [(BASE + timedelta(minutes=2), BASE + timedelta(minutes=2, seconds=40))]
    report = soak.analyze_soak(fires, down_windows=down, first_ready=READY0, local_tz=UTC)
    text = soak.render_timeline(report)
    assert "X2" in text and "DOUBLE FIRE" in text
    assert "--" in text and "backend down" in text
    assert "!!" in text
    assert "Verdict: FAILED" in text
    assert "Summary:" in text
