"""Execution-history panel tests (decisions.md #47).

The Workflow Builder's history panel needs: per-workflow + all-workflow
routes (the literal one declared before the dynamic /{workflow_id} route —
FastAPI matches in declaration order), history that survives restarts via
the persisted ring buffer, and the ring-buffer cap. Engines are built with
an injected temp state path — no env vars, no module reloads, no touching
the real %LOCALAPPDATA% state file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dash_backend.services.workflow_builder import (
    MAX_PERSISTED_EXECUTIONS,
    WorkflowEngine,
)


@pytest.fixture()
def eng(tmp_path: Path) -> WorkflowEngine:
    """Isolated engine with its own temp state file."""
    return WorkflowEngine(state_path=tmp_path / "wf_state.json")


def _make_workflow(engine: WorkflowEngine, name: str = "hist test") -> dict:
    return engine.create(
        name,
        nodes=[{"id": "n1", "type": "trigger", "config": {"schedule": "* * * * *"}, "x": 0, "y": 0}],
        edges=[],
        description="d",
        category="custom",
    )


def test_execution_history_persists_across_engine_restart(eng: WorkflowEngine, tmp_path: Path) -> None:
    created = _make_workflow(eng)
    wf_id = created["workflow"]["id"]
    assert eng.execute(wf_id)["ok"] is True
    assert eng.execute(wf_id)["ok"] is True

    # Simulate a backend restart: a brand-new engine over the same file.
    engine2 = WorkflowEngine(state_path=tmp_path / "wf_state.json")
    history = engine2.get_executions(wf_id)
    assert len(history) == 2
    assert all(e["workflow_id"] == wf_id for e in history)
    assert history[0]["started_at"] >= history[1]["started_at"]  # newest first
    assert all(e["status"] == "completed" for e in history)


def test_execution_persists_workflow_run_count(eng: WorkflowEngine, tmp_path: Path) -> None:
    created = _make_workflow(eng)
    wf_id = created["workflow"]["id"]
    eng.execute(wf_id)
    eng.execute(wf_id)

    engine2 = WorkflowEngine(state_path=tmp_path / "wf_state.json")
    wf = engine2.get(wf_id)
    assert wf is not None
    assert wf["run_count"] == 2
    assert wf["last_run"] is not None


@pytest.mark.asyncio
async def test_history_panel_route_not_shadowed(client) -> None:
    """GET /enhanced/workflows/executions must reach the literal route, not
    be swallowed by /enhanced/workflows/{workflow_id} (declaration-order
    shadowing would 422 trying to parse 'executions' as a workflow id)."""
    resp = await client.get("/api/v1/enhanced/workflows/executions")
    assert resp.status_code == 200
    body = resp.json()
    assert "executions" in body
    assert isinstance(body["executions"], list)


@pytest.mark.asyncio
async def test_history_panel_route_limit_respected(client) -> None:
    """The literal route must honor its limit query parameter."""
    resp = await client.get("/api/v1/enhanced/workflows/executions?limit=5")
    assert resp.status_code == 200
    assert len(resp.json()["executions"]) <= 5


@pytest.mark.asyncio
async def test_per_workflow_history_route_works(client, eng, monkeypatch) -> None:
    """The route reads the engine singleton at call time; point that symbol
    at the test engine so the route and the fixture share one instance."""
    import dash_backend.services.workflow_builder as wb

    monkeypatch.setattr(wb, "workflow_engine", eng)
    created = _make_workflow(eng)
    wf_id = created["workflow"]["id"]
    eng.execute(wf_id)
    resp = await client.get(f"/api/v1/enhanced/workflows/{wf_id}/executions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["executions"]) == 1
    rec = body["executions"][0]
    assert rec["status"] == "completed"
    assert rec["nodes_executed"] == ["n1"]
    assert rec["duration_ms"] >= 0
    assert rec["workflow_name"] == "hist test"


def test_ring_buffer_trims_to_cap(tmp_path: Path) -> None:
    state = tmp_path / "wf_state.json"
    eng = WorkflowEngine(state_path=state)
    created = _make_workflow(eng)
    wf_id = created["workflow"]["id"]
    for i in range(MAX_PERSISTED_EXECUTIONS + 30):
        eng._executions.append({"id": f"e{i}", "workflow_id": wf_id})
    eng._save_custom()

    eng2 = WorkflowEngine(state_path=state)
    assert len(eng2._executions) == MAX_PERSISTED_EXECUTIONS
    # Newest kept: the trim drops the OLDEST entries.
    assert eng2._executions[0]["id"] == f"e{MAX_PERSISTED_EXECUTIONS + 29 - MAX_PERSISTED_EXECUTIONS + 1}"


def test_state_file_contains_executions_key(eng: WorkflowEngine, tmp_path: Path) -> None:
    created = _make_workflow(eng)
    eng.execute(created["workflow"]["id"])
    data = json.loads((tmp_path / "wf_state.json").read_text(encoding="utf-8"))
    assert "executions" in data
    assert len(data["executions"]) == 1
    assert data["executions"][0]["status"] == "completed"
