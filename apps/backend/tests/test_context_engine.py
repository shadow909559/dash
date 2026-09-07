"""Tests for the DASH environment Context Engine (Phase 1).

Covers: real collectors (device via psutil, git on this repo), engine
assembly, the compact prompt block, cache/TTL behavior, change awareness,
and defensive failure handling.
"""

from __future__ import annotations

import os

import pytest

import dash_backend.context.engine as engine_mod
from dash_backend.context.engine import ContextEngine, EnvironmentContext
from dash_backend.context.collectors import (
    collect_device_context,
    collect_project_context,
    find_git_root,
)


# ── Real collectors ─────────────────────────────────────────────


def test_device_collector_returns_sane_shape():
    ctx = collect_device_context()
    assert isinstance(ctx, dict)
    assert "platform" in ctx
    # On this machine psutil is installed; keys should be populated.
    assert "cpu_percent" in ctx
    assert 0 <= ctx["cpu_percent"] <= 100
    assert "ram_percent" in ctx


def test_project_collector_on_real_repo():
    root = find_git_root(os.getcwd())
    assert root is not None, "tests should run inside the dash git repo"
    ctx = collect_project_context(str(root))
    assert ctx.get("repo_root") == str(root)
    assert ctx.get("repo_name")
    assert ctx.get("branch")
    assert "changed_files" in ctx
    assert ctx.get("last_commit")


def test_project_collector_on_missing_repo_returns_empty():
    ctx = collect_project_context(os.environ.get("TEMP", "/tmp"))
    assert ctx == {} or "repo_root" not in ctx


# ── Engine assembly & prompt block ─────────────────────────────


def test_snapshot_assembles_device_and_project():
    engine = ContextEngine()
    snap = engine.snapshot()
    assert isinstance(snap, EnvironmentContext)
    assert snap.device.get("platform")
    assert snap.project.get("repo_name")


def test_as_text_formats_block():
    snap = EnvironmentContext(
        device={
            "platform": "Windows-10",
            "cpu_percent": 12.5,
            "ram_percent": 40.0,
            "ram_used_mb": 8000,
            "ram_total_mb": 16384,
            "disk_percent": 60.0,
            "disk_free_gb": 120.0,
            "top_processes": [{"name": "chrome", "ram_mb": 500}],
        },
        project={
            "repo_name": "dash",
            "branch": "main",
            "changed_files": 3,
            "last_commit": "abc1234 fix thing",
            "commits_last_24h": 2,
        },
        activity={
            "recent_goals": [
                {"name": "Ship DASH 2.0", "status": "running"},
                {"name": "Clean downloads", "status": "completed"},
            ]
        },
    )
    text = snap.as_text()
    assert "[DEVICE]" in text
    assert "CPU: 12.5%" in text
    assert "[PROJECT] dash on branch main" in text
    assert "3 modified file(s)" in text
    assert "[ACTIVE GOALS] 1 active" in text


def test_cache_respected_and_refresh_bypasses(monkeypatch):
    calls = {"n": 0}

    def fake_device():
        calls["n"] += 1
        return {"platform": "fake"}

    monkeypatch.setattr(engine_mod.collectors, "collect_device_context", fake_device)
    engine = ContextEngine(device_ttl=60.0)
    engine.device()
    engine.device()
    assert calls["n"] == 1, "second call within TTL must hit the cache"
    engine.device(refresh=True)
    assert calls["n"] == 2, "refresh must bypass the cache"


async def test_snapshot_async_collects_activity(monkeypatch):
    async def fake_activity(session, user_id, hours):
        return {"recent_goals": [{"name": "g", "status": "pending"}]}

    monkeypatch.setattr(engine_mod.collectors, "collect_activity_context", fake_activity)
    engine = ContextEngine(activity_ttl=60.0)
    snap = await engine.snapshot_async(session=object(), user_id="u1")
    assert snap.activity["recent_goals"][0]["name"] == "g"


def test_context_block_sync_never_raises(monkeypatch):
    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(engine_mod.collectors, "collect_device_context", broken)
    monkeypatch.setattr(engine_mod.collectors, "collect_project_context", broken)
    engine = ContextEngine()
    assert engine.context_block_sync() == ""


# ── Change awareness ────────────────────────────────────────────


async def test_what_changed_since_without_db():
    engine = ContextEngine()
    result = await engine.what_changed_since()
    assert result["window_hours"] == 24
    assert "commits" in result
    assert "changed_files" in result
    assert result["goals_created"] == 0


# ── REST endpoint ───────────────────────────────────────────────


async def test_context_endpoint_requires_auth(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as bare:
        resp = await bare.get("/api/v1/context")
        assert resp.status_code == 401


async def test_context_endpoint_returns_snapshot(client):
    resp = await client.get("/api/v1/context")
    assert resp.status_code == 200
    data = resp.json()
    assert "device" in data
    assert "project" in data
    assert data["device"].get("platform")


async def test_context_brief_endpoint(client):
    resp = await client.get("/api/v1/context/brief")
    assert resp.status_code == 200
    assert "block" in resp.json()


async def test_what_changed_endpoint(client):
    resp = await client.get("/api/v1/context/what-changed?hours=24")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 24