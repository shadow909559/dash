"""Template-instantiation tests (decisions.md #48).

One-click instantiation of the 6 builder templates into editable custom
workflows: deep-copied nodes/edges (template code-seeded dicts must never
be shared with an editable copy), automatic name dedup across repeated
instantiations, templates remaining pristine, and the HTTP route.
"""

from __future__ import annotations

import pytest

from dash_backend.services.workflow_builder import WorkflowEngine


@pytest.fixture()
def eng(tmp_path) -> WorkflowEngine:
    return WorkflowEngine(state_path=tmp_path / "wf_state.json")


def _template(eng: WorkflowEngine) -> dict:
    templates = eng.list_templates()
    assert templates, "engine must seed templates"
    return templates[0]


def test_instantiate_creates_editable_custom_workflow(eng: WorkflowEngine) -> None:
    tmpl = _template(eng)
    result = eng.instantiate_template(tmpl["id"])
    assert result["ok"] is True
    wf = result["workflow"]
    assert wf["is_template"] is False
    assert wf["name"] == tmpl["name"]
    assert wf["instantiated_from"] == tmpl["id"]
    assert len(wf["nodes"]) == len(tmpl["nodes"])
    assert wf["run_count"] == 0


def test_instantiate_is_deep_copy(eng: WorkflowEngine) -> None:
    """Editing an instantiated copy must never mutate the template."""
    tmpl = _template(eng)
    result = eng.instantiate_template(tmpl["id"])
    wf = result["workflow"]
    if tmpl["nodes"]:
        wf["nodes"][0]["config"]["HACKED"] = "yes"
        eng.update(wf["id"], nodes=wf["nodes"])
        fresh = eng.get(tmpl["id"])
        assert all("HACKED" not in n.get("config", {}) for n in fresh["nodes"]), (
            "template node dicts were shared with the copy — shallow copy bug"
        )


def test_instantiate_dedups_names(eng: WorkflowEngine) -> None:
    tmpl = _template(eng)
    n1 = eng.instantiate_template(tmpl["id"])["workflow"]["name"]
    n2 = eng.instantiate_template(tmpl["id"])["workflow"]["name"]
    n3 = eng.instantiate_template(tmpl["id"])["workflow"]["name"]
    assert n1 == tmpl["name"]
    assert n2 == f"{tmpl['name']} (2)"
    assert n3 == f"{tmpl['name']} (3)"


def test_instantiate_with_custom_name_still_dedups(eng: WorkflowEngine) -> None:
    tmpl = _template(eng)
    r1 = eng.instantiate_template(tmpl["id"], name="My Version")
    r2 = eng.instantiate_template(tmpl["id"], name="My Version")
    assert r1["workflow"]["name"] == "My Version"
    assert r2["workflow"]["name"] == "My Version (2)"


def test_templates_remain_pristine_after_instantiation(eng: WorkflowEngine) -> None:
    tmpl = _template(eng)
    count_before = len(eng.list_templates())
    for _ in range(3):
        eng.instantiate_template(tmpl["id"])
    assert len(eng.list_templates()) == count_before
    fresh = eng.get(tmpl["id"])
    assert fresh["is_template"] is True
    # Pristine identity: templates are never copies, never renamed, never re-counted.
    assert "instantiated_from" not in fresh
    assert len(fresh["nodes"]) == len(tmpl["nodes"])
    assert fresh["nodes"] == tmpl["nodes"]


def test_list_all_excludes_templates(eng: WorkflowEngine) -> None:
    """Regression: /enhanced/workflows used to include templates, so the
    desktop dropdown listed every template twice (merged from both endpoints).
    Custom listing must contain no template records (names may legitimately
    collide — the first instantiation reuses the template's name)."""
    eng.instantiate_template(eng.list_templates()[0]["id"])
    all_ids = [w["id"] for w in eng.list_all()]
    tmpl_ids = {t["id"] for t in eng.list_templates()}
    assert not tmpl_ids & set(all_ids)
    assert all(not w["is_template"] for w in eng.list_all())


def test_instantiate_unknown_template_fails_cleanly(eng: WorkflowEngine) -> None:
    result = eng.instantiate_template("nope")
    assert result == {"ok": False, "reason": "Template not found"}


def test_duplicate_also_deep_copies(eng: WorkflowEngine) -> None:
    """duplicate() had the same shallow-copy hazard; lock the fix in."""
    created = eng.create(
        "orig",
        nodes=[{"id": "n1", "type": "trigger", "config": {"a": "1"}, "x": 0, "y": 0}],
        edges=[{"from": "n1", "to": "n2"}],
        description="",
        category="custom",
    )
    wf_id = created["workflow"]["id"]
    copy_result = eng.duplicate(wf_id)
    dup = copy_result["workflow"]
    dup["nodes"][0]["config"]["MUTATED"] = "yes"
    original = eng.get(wf_id)
    assert "MUTATED" not in original["nodes"][0]["config"]


@pytest.mark.asyncio
async def test_instantiate_route(client, monkeypatch, tmp_path) -> None:
    """The HTTP route instantiates and returns the editable workflow."""
    import dash_backend.services.workflow_builder as wb

    eng = WorkflowEngine(state_path=tmp_path / "route_state.json")
    monkeypatch.setattr(wb, "workflow_engine", eng)
    tmpl = eng.list_templates()[0]

    resp = await client.post(
        f"/api/v1/enhanced/workflows/templates/{tmpl['id']}/instantiate", json={}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["workflow"]["is_template"] is False

    # Appears in My Workflows.
    listing = await client.get("/api/v1/enhanced/workflows")
    names = [w["name"] for w in listing.json()["workflows"]]
    assert tmpl["name"] in names
