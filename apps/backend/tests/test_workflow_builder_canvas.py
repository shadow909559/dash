"""Tests for the workflow builder canvas API: update route and persistence.

The desktop Workflow Builder canvas saves nodes/edges via PUT
/enhanced/workflows/{id}; custom workflows must survive an engine restart
(backend restart), while templates are re-seeded from code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dash_backend.services.workflow_builder import WorkflowEngine


@pytest.fixture()
def workflow_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point DASH_WORKFLOW_STATE at an isolated file for the whole test."""
    state = tmp_path / "workflow_state.json"
    monkeypatch.setenv("DASH_WORKFLOW_STATE", str(state))
    return state


def _fresh_engine() -> WorkflowEngine:
    """New engine instance reading the monkeypatched env at construct time.

    The env var stays set for the duration of the test (monkeypatch), so
    later create/update/delete calls persist to the same isolated file.
    """
    return WorkflowEngine()


# ── Engine-level: CRUD + persistence ───────────────────────────────────────


def test_create_and_reload_custom_workflow(workflow_state: Path) -> None:
    eng = _fresh_engine()
    res = eng.create("My Flow", nodes=[{"id": "n1", "type": "trigger", "config": {}}], edges=[])
    assert res["ok"] is True
    wf_id = res["workflow"]["id"]

    # State file exists and contains only the custom workflow
    data = json.loads(workflow_state.read_text(encoding="utf-8"))
    assert [w["id"] for w in data["custom_workflows"]] == [wf_id]

    # A brand-new engine (restart simulation) reloads it, plus templates
    eng2 = _fresh_engine()
    assert eng2.get(wf_id) is not None
    assert eng2.get(wf_id)["name"] == "My Flow"
    assert any(w["is_template"] for w in eng2.list_all())


def test_update_persists_canvas_edits(workflow_state: Path) -> None:
    eng = _fresh_engine()
    wf_id = eng.create("Draft", nodes=[], edges=[])["workflow"]["id"]

    nodes = [
        {"id": "n1", "type": "trigger", "config": {"schedule": "0 9 * * *"}, "x": 0, "y": 0},
        {"id": "n2", "type": "condition", "config": {"field": "cpu", "op": "gte", "value": 90}, "x": 240, "y": 0},
        {"id": "n3", "type": "action", "config": {"tool": "notification.send"}, "x": 480, "y": -80},
        {"id": "n4", "type": "action", "config": {"tool": "memory.create"}, "x": 480, "y": 80},
    ]
    edges = [
        {"from": "n1", "to": "n2"},
        {"from": "n2", "to": "n3", "condition": "true"},
        {"from": "n2", "to": "n4", "condition": "false"},
    ]
    res = eng.update(wf_id, nodes=nodes, edges=edges)
    assert res["ok"] is True

    eng2 = _fresh_engine()
    reloaded = eng2.get(wf_id)
    assert reloaded["nodes"] == nodes
    assert reloaded["edges"] == edges
    # if/else branch labels survive
    assert {e.get("condition") for e in reloaded["edges"]} == {"true", "false", None}


def test_update_and_delete_template_are_rejected(workflow_state: Path) -> None:
    eng = _fresh_engine()
    res = eng.update("daily_briefing", name="Hacked")
    assert res["ok"] is False
    assert eng.delete("daily_briefing")["ok"] is False


def test_delete_removes_custom_workflow_from_state(workflow_state: Path) -> None:
    eng = _fresh_engine()
    wf_id = eng.create("Doomed", nodes=[], edges=[])["workflow"]["id"]
    assert eng.delete(wf_id)["ok"] is True
    data = json.loads(workflow_state.read_text(encoding="utf-8"))
    assert all(w["id"] != wf_id for w in data["custom_workflows"])
    assert eng.get(wf_id) is None


def test_duplicate_persists_copy(workflow_state: Path) -> None:
    eng = _fresh_engine()
    eng.create("Original", nodes=[{"id": "n1", "type": "action", "config": {}}], edges=[])
    res = eng.duplicate(
        [w["id"] for w in eng.list_all() if not w["is_template"]][0], new_name="Copy"
    )
    assert res["ok"] is True
    data = json.loads(workflow_state.read_text(encoding="utf-8"))
    assert len([w for w in data["custom_workflows"]]) == 2


# ── Route-level: PUT /enhanced/workflows/{id} ──────────────────────────────


def test_update_route_exists_in_openapi(tmp_path: Path) -> None:
    from dash_backend.api.routes.enhanced_features import router

    put_routes = [
        r for r in router.routes
        if "PUT" in r.methods and "{workflow_id}" in r.path and "workflow" in r.path
    ]
    assert put_routes, "PUT /enhanced/workflows/{workflow_id} route missing"


def test_canvas_workflow_end_to_end(workflow_state: Path) -> None:
    """Full canvas flow: create → update with if/else graph → restart → run."""
    eng = _fresh_engine()
    wf_id = eng.create("If Else Demo", nodes=[], edges=[])["workflow"]["id"]

    eng.update(
        wf_id,
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"event": "email.received"}, "x": 0, "y": 40},
            {"id": "n2", "type": "condition", "config": {"field": "importance", "op": "gte", "value": 0.5}, "x": 240, "y": 40},
            {"id": "n3", "type": "action", "config": {"tool": "memory.create"}, "x": 480, "y": 0},
            {"id": "n4", "type": "action", "config": {"tool": "notification.send"}, "x": 480, "y": 120},
        ],
        edges=[
            {"from": "n1", "to": "n2"},
            {"from": "n2", "to": "n3", "condition": "true"},
            {"from": "n2", "to": "n4", "condition": "false"},
        ],
    )

    eng2 = _fresh_engine()
    run = eng2.execute(wf_id)
    assert run["ok"] is True
    assert run["execution"]["status"] == "completed"
    assert run["execution"]["nodes_executed"] == ["n1", "n2", "n3", "n4"]
