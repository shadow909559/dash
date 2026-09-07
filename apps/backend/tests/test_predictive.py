"""Tests for DASH Predictive Problem Detection (Ultimate spec, Part 8).

Covers the honesty contract (no trend claimed without enough history),
each pure predictor (RAM/disk trends, stale branches, dirty aging, repo
dormancy, stalled goals), engine sampling, and the REST endpoint.
"""

from __future__ import annotations

import time

import pytest

from dash_backend.context.engine import EnvironmentContext
from dash_backend.predictive.engine import PredictiveEngine
from dash_backend.predictive.history import SampleStore
from dash_backend.predictive.predictors import (
    _linear_fit,
    predict_dirty_aging,
    predict_disk_fill,
    predict_ram_exhaustion,
    predict_repo_dormancy,
    predict_stale_branches,
    predict_stalled_goals,
)


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolate_predictive_state(tmp_path, monkeypatch):
    """Keep endpoint tests from writing the real machine's predictive state."""
    monkeypatch.setenv("DASH_PREDICTIVE_STATE", str(tmp_path / "predictive_state.json"))


# ── Helpers ─────────────────────────────────────────────────────


def hourly_samples(key: str, values, start_ts: float, step_h: float = 1.0):
    """Build {ts, key: value} samples at `step_h` intervals from start_ts."""
    out = []
    for i, v in enumerate(values):
        out.append({"ts": start_ts + i * step_h * 3600.0, key: v})
    return out


def make_snap(device=None, project=None, activity=None) -> EnvironmentContext:
    return EnvironmentContext(device=device or {}, project=project or {}, activity=activity or {})


class FakeContextEngine:
    def __init__(self, snap: EnvironmentContext):
        self._snap = snap

    async def snapshot_async(self, session=None, user_id=None, refresh=False):
        return self._snap


def make_engine(snap: EnvironmentContext, tmp_path) -> PredictiveEngine:
    store = SampleStore(tmp_path / "predictive_state.json")
    return PredictiveEngine(store=store, context_engine=FakeContextEngine(snap))


# ── Trend-math honesty ─────────────────────────────────────────


def test_linear_fit_requires_enough_samples():
    now = time.time()
    few = hourly_samples("ram_pct", [50.0, 51.0, 52.0], now)
    assert _linear_fit(few, "ram_pct") is None  # only 3 samples


def test_linear_fit_requires_span():
    now = time.time()
    tight = hourly_samples("ram_pct", [50.0, 60.0, 70.0, 80.0], now, step_h=0.1)
    assert _linear_fit(tight, "ram_pct") is None  # 0.3h span < 6h minimum


def test_no_prediction_from_single_sample():
    now = time.time()
    one = [{"ts": now, "ram_pct": 99.0}]
    assert predict_ram_exhaustion(one) is None
    assert predict_disk_fill(one) is None


def test_flat_ram_history_never_predicts():
    now = time.time()
    flat = hourly_samples("ram_pct", [60.0] * 30, now)
    assert predict_ram_exhaustion(flat) is None


# ── RAM trend ───────────────────────────────────────────────────


def test_rising_ram_projects_exhaustion():
    now = time.time()
    rising = hourly_samples("ram_pct", [55 + i * 1.5 for i in range(25)], now)
    pred = predict_ram_exhaustion(rising)
    assert pred is not None
    assert pred.id == "ram_trend_exhaustion"
    assert pred.severity in ("high", "warning", "info")
    assert 0.0 < pred.likelihood <= 1.0
    assert pred.evidence  # what DASH actually observed
    assert "projected" in pred.message  # framed as projection, not fact


def test_falling_ram_history_no_prediction():
    now = time.time()
    falling = hourly_samples("ram_pct", [90 - i * 1.2 for i in range(20)], now)
    assert predict_ram_exhaustion(falling) is None


# ── Disk trend ──────────────────────────────────────────────────


def test_shrinking_disk_projects_fill():
    now = time.time()
    # Free space drops from 120 GB to 40 GB over 30 days.
    days = 30
    vals = [120 - (i * (80.0 / (24 * days))) for i in range(24 * days)]
    shrink = hourly_samples("disk_free_gb", vals, now - days * 86400)
    pred = predict_disk_fill(shrink)
    assert pred is not None
    assert pred.id == "disk_fill_projection"
    assert pred.horizon != "unknown"
    assert "projected below" in pred.message


def test_growing_free_disk_no_prediction():
    now = time.time()
    days = 14
    vals = [40 + (i * (80.0 / (24 * days))) for i in range(24 * days)]
    grow = hourly_samples("disk_free_gb", vals, now - days * 86400)
    assert predict_disk_fill(grow) is None


# ── Stale branches ──────────────────────────────────────────────


def test_stale_branches_detected():
    branch_info = [
        ("main", "2026-09-01"),
        ("feature/auth", "2020-05-01"),
        ("feature/old-work", "2019-11-11"),
    ]
    proj = {"repo_name": "dash", "branch": "main", "repo_root": None}
    pred = predict_stale_branches(proj, branch_info=branch_info)
    assert pred is not None
    assert pred.id == "stale_branches"
    assert pred.category == "project"
    assert "feature/auth" in pred.message
    # Current branch (main) is excluded even though old.
    assert pred.evidence[0].startswith("feature/")


def test_no_stale_branches_when_all_recent():
    branch_info = [(f"b{i}", "2026-09-06") for i in range(3)]
    assert predict_stale_branches({"repo_name": "r", "branch": "b0"}, branch_info=branch_info) is None


def test_no_branch_info_no_prediction():
    assert predict_stale_branches({"repo_name": "r", "branch": "main"}) is None


# ── Dirty-work aging ────────────────────────────────────────────


def test_dirty_aging_fires_after_hours():
    now = time.time()
    repo = {"repo_name": "dash", "branch": "main", "changed_files": 4}
    prev = {"branch": "main", "changed_files": 4, "dirty_since": now - 48 * 3600}
    pred = predict_dirty_aging(repo, prev, now=now)
    assert pred is not None
    assert pred.id == "dirty_work_aging"
    assert pred.severity == "warning"
    assert "2 day(s)" in pred.horizon or "48 hour" in pred.horizon


def test_dirty_aging_requires_observation_history():
    now = time.time()
    repo = {"repo_name": "dash", "branch": "main", "changed_files": 4}
    assert predict_dirty_aging(repo, None, now=now) is None


def test_dirty_aging_not_yet_risky():
    now = time.time()
    repo = {"repo_name": "dash", "branch": "main", "changed_files": 4}
    prev = {"branch": "main", "changed_files": 4, "dirty_since": now - 3600}
    assert predict_dirty_aging(repo, prev, now=now) is None


def test_clean_tree_no_aging():
    now = time.time()
    repo = {"repo_name": "dash", "branch": "main", "changed_files": 0}
    prev = {"branch": "main", "changed_files": 0, "dirty_since": now - 3600}
    assert predict_dirty_aging(repo, prev, now=now) is None


# ── Repo dormancy ───────────────────────────────────────────────


def test_dormant_repo_detected():
    proj = {"repo_name": "old", "branch": "main", "changed_files": 0, "last_commit": "a1b2c3d done | 2026-06-01"}
    pred = predict_repo_dormancy(proj)
    assert pred is not None
    assert pred.id == "repo_dormant"
    assert "dormant" in pred.title


def test_active_repo_not_dormant():
    proj = {"repo_name": "dash", "branch": "main", "changed_files": 0, "last_commit": "a1b2c3d | 2026-09-06"}
    assert predict_repo_dormancy(proj) is None


def test_dirty_repo_not_dormant():
    proj = {"repo_name": "old", "branch": "main", "changed_files": 3, "last_commit": "a1b2c3d | 2026-06-01"}
    assert predict_repo_dormancy(proj) is None


# ── Stalled goals ───────────────────────────────────────────────


def test_stalled_goals_detected():
    rows = [
        {"name": "Ship DASH", "status": "running", "created_at": "2026-08-01T10:00:00"},
        {"name": "Cleanup", "status": "pending", "created_at": "2026-08-20T10:00:00"},
    ]
    pred = predict_stalled_goals(rows)
    assert pred is not None
    assert pred.id == "goals_stalled"
    assert "Ship DASH" in pred.message
    assert "2 goal(s)" in pred.title


def test_no_stalled_rows_no_prediction():
    assert predict_stalled_goals([]) is None


# ── Engine sampling + orchestration ────────────────────────────


async def test_engine_records_sample_even_without_trend(tmp_path):
    snap = make_snap(device={"ram_pct": 60.0, "disk_free_gb": 50.0, "cpu_pct": 30.0})
    engine = make_engine(snap, tmp_path)
    result = await engine.analyze()
    assert result["count"] == 0  # single sample -> no trend claims
    assert len(engine._store.samples()) == 1


async def test_engine_never_raises_on_empty_snapshot(tmp_path):
    engine = make_engine(make_snap(), tmp_path)
    result = await engine.analyze()
    assert "count" in result and "predictions" in result


async def test_engine_predictions_are_honest_dicts(tmp_path):
    now = time.time()
    # Pre-seed enough history for a disk projection, then analyze a snapshot
    # that records the latest point.
    store = SampleStore(tmp_path / "predictive_state.json")
    days = 20
    vals = [110 - (i * (80.0 / (24 * days))) for i in range(24 * days)]
    for s in hourly_samples("disk_free_gb", vals, now - days * 86400):
        store.append(s)
    engine = PredictiveEngine(store=store, context_engine=FakeContextEngine(make_snap(device={"disk_free_gb": 30.0, "ram_pct": 70.0})))
    result = await engine.analyze()
    ids = {p["id"] for p in result["predictions"]}
    assert "disk_fill_projection" in ids
    for p in result["predictions"]:
        assert {"id", "category", "title", "message", "severity", "likelihood", "action", "horizon", "confident", "evidence"} <= set(p.keys())


# ── REST endpoint ──────────────────────────────────────────────


async def test_risks_endpoint_requires_auth(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as bare:
        resp = await bare.get("/api/v1/predictive/risks")
        assert resp.status_code == 401


async def test_risks_endpoint_returns_structure(client):
    resp = await client.get("/api/v1/predictive/risks")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert isinstance(data["predictions"], list)
    assert data["count"] == len(data["predictions"])
