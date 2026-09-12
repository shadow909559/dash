"""TRUE/FALSE branch execution tests (decisions.md #50).

The engine previously walked nodes in list order and ignored edges — an
if/else flow executed BOTH branches. The engine now traverses the graph
from the trigger, evaluates condition nodes against the run's input_data,
and follows only the matching branch.

Canvas contract reminder: condition edges carry condition="true"/"false";
unconditional edges carry no condition key.
"""

from __future__ import annotations

import pytest

from dash_backend.services.workflow_builder import WorkflowEngine


@pytest.fixture()
def eng(tmp_path) -> WorkflowEngine:
    return WorkflowEngine(state_path=tmp_path / "wf_state.json")


def _node(nid: str, ntype: str, **config) -> dict:
    return {"id": nid, "type": ntype, "config": config, "x": 0, "y": 0}


def _build(eng: WorkflowEngine, nodes: list[dict], edges: list[dict]) -> str:
    created = eng.create("branch test", nodes=nodes, edges=edges)
    assert created["ok"] is True
    return created["workflow"]["id"]


def _run(eng: WorkflowEngine, nodes, edges, input_data=None) -> dict:
    wf_id = _build(eng, nodes, edges)
    return eng.execute(wf_id, input_data or {})["execution"]


def test_true_branch_follows_true_edge_only(eng: WorkflowEngine) -> None:
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="score", op="gte", value="50"),
            _node("a1", "action", tool="on_true"),
            _node("a2", "action", tool="on_false"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "a1", "condition": "true"},
            {"from": "c", "to": "a2", "condition": "false"},
        ],
        input_data={"score": 80},
    )
    assert rec["status"] == "completed"
    assert rec["nodes_executed"] == ["t", "c", "a1"]
    assert rec["condition_results"] == {"c": True}


def test_false_branch_follows_false_edge_only(eng: WorkflowEngine) -> None:
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="score", op="gte", value="50"),
            _node("a1", "action", tool="on_true"),
            _node("a2", "action", tool="on_false"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "a1", "condition": "true"},
            {"from": "c", "to": "a2", "condition": "false"},
        ],
        input_data={"score": 10},
    )
    assert rec["nodes_executed"] == ["t", "c", "a2"]
    assert rec["condition_results"] == {"c": False}


def test_missing_field_takes_false_branch(eng: WorkflowEngine) -> None:
    """Missing context is the safe default: FALSE branch, no crash."""
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="ghost", op="eq", value="x"),
            _node("yes", "action"),
            _node("no", "action"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "yes", "condition": "true"},
            {"from": "c", "to": "no", "condition": "false"},
        ],
        input_data={},
    )
    assert rec["nodes_executed"] == ["t", "c", "no"]


def test_unwired_branch_is_a_dead_end_not_an_error(eng: WorkflowEngine) -> None:
    """Only the FALSE branch is wired; a FALSE evaluation ends the path."""
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="ok", op="truthy"),
            _node("yes", "action"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "yes", "condition": "true"},
        ],
        input_data={"ok": False},
    )
    assert rec["status"] == "completed"
    assert rec["nodes_executed"] == ["t", "c"]


def test_unconditional_edges_still_chain(eng: WorkflowEngine) -> None:
    """A condition node whose wired branch chains onward keeps flowing."""
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="ok", op="truthy"),
            _node("a1", "action"),
            _node("a2", "action"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "a1", "condition": "true"},
            {"from": "a1", "to": "a2"},
        ],
        input_data={"ok": "yes"},
    )
    assert rec["nodes_executed"] == ["t", "c", "a1", "a2"]


def test_condition_without_condition_edges_falls_back_to_unconditional(eng: WorkflowEngine) -> None:
    """Back-compat: a condition node wired only with plain edges behaves
    like a regular node (both edges followed) instead of dead-ending."""
    rec = _run(
        eng,
        nodes=[_node("t", "trigger"), _node("c", "condition", field="x", op="eq", value="1"), _node("a1", "action"), _node("a2", "action")],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "a1"},
            {"from": "c", "to": "a2"},
        ],
        input_data={"x": "1"},
    )
    assert rec["nodes_executed"] == ["t", "c", "a1", "a2"]


def test_coercion_string_vs_number(eng: WorkflowEngine) -> None:
    """Canvas config stores strings; numeric comparison must still work."""
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="cpu", op="gt", value="80"),
            _node("hi", "action"),
            _node("lo", "action"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "hi", "condition": "true"},
            {"from": "c", "to": "lo", "condition": "false"},
        ],
        input_data={"cpu": "85.5"},
    )
    assert rec["nodes_executed"] == ["t", "c", "hi"]


def test_boolean_coercion_false_string(eng: WorkflowEngine) -> None:
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="dnd", op="eq", value="false"),
            _node("notify", "action"),
            _node("skip", "action"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "notify", "condition": "true"},
            {"from": "c", "to": "skip", "condition": "false"},
        ],
        input_data={"dnd": False},
    )
    assert rec["nodes_executed"] == ["t", "c", "notify"]


def test_supported_ops_matrix(eng: WorkflowEngine) -> None:
    cases = [
        ("eq", "hello", "hello", True),
        ("ne", "hello", "world", True),
        ("contains", "Hello World", "wor", True),
        ("not_contains", "Hello", "xyz", True),
        ("starts_with", "foobar", "foo", True),
        ("ends_with", "foobar", "bar", True),
        ("in", "b", "a, b ,c", True),
        ("truthy", "anything", "", True),
        ("lt", 5, "10", True),
    ]
    for i, (op, actual, expected, want) in enumerate(cases):
        rec = _run(
            eng,
            nodes=[
                _node("t", "trigger"),
                _node("c", "condition", field="f", op=op, value=expected),
                _node("yes", "action"),
                _node("no", "action"),
            ],
            edges=[
                {"from": "t", "to": "c"},
                {"from": "c", "to": "yes", "condition": "true"},
                {"from": "c", "to": "no", "condition": "false"},
            ],
            input_data={"f": actual},
        )
        took_true = rec["nodes_executed"][-1] == "yes"
        assert took_true is want, f"case {i}: op={op} actual={actual!r} expected={expected!r}"


def test_unknown_op_fails_safe_to_false(eng: WorkflowEngine) -> None:
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="f", op="regex_magic", value=".*"),
            _node("yes", "action"),
            _node("no", "action"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "yes", "condition": "true"},
            {"from": "c", "to": "no", "condition": "false"},
        ],
        input_data={"f": "anything"},
    )
    assert rec["nodes_executed"] == ["t", "c", "no"]


def test_cycle_guard_aborts_as_failed(eng: WorkflowEngine) -> None:
    """A user-wired cycle must fail the run, not hang the worker."""
    wf_id = _build(
        eng,
        nodes=[_node("t", "trigger"), _node("a", "action"), _node("b", "action")],
        edges=[{"from": "t", "to": "a"}, {"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    )
    run = eng.execute(wf_id, {})
    rec = run["execution"]
    # visited-set stops the loop; run still completes with nodes run once.
    assert rec["status"] == "completed"
    assert rec["nodes_executed"].count("a") == 1


def test_diamond_both_paths_converge(eng: WorkflowEngine) -> None:
    """Fan-out from a trigger runs both arms; each node runs once."""
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("l", "action", tool="left"),
            _node("r", "action", tool="right"),
            _node("j", "action", tool="join"),
        ],
        edges=[
            {"from": "t", "to": "l"},
            {"from": "t", "to": "r"},
            {"from": "l", "to": "j"},
            {"from": "r", "to": "j"},
        ],
        input_data={},
    )
    assert rec["nodes_executed"] == ["t", "l", "r", "j"]


def test_output_reports_condition_results(eng: WorkflowEngine) -> None:
    rec = _run(
        eng,
        nodes=[
            _node("t", "trigger"),
            _node("c1", "condition", field="a", op="truthy"),
            _node("c2", "condition", field="b", op="truthy"),
            _node("x", "action"),
        ],
        edges=[
            {"from": "t", "to": "c1"},
            {"from": "c1", "to": "c2"},
            {"from": "c2", "to": "x", "condition": "true"},
        ],
        input_data={"a": 1, "b": 0},
    )
    assert rec["output"]["conditions"] == {"c1": True, "c2": False}
    assert rec["nodes_executed"] == ["t", "c1", "c2"]


@pytest.mark.asyncio
async def test_execute_route_accepts_input_data(client, monkeypatch, tmp_path) -> None:
    """The HTTP route forwards input_data as the condition context."""
    from pathlib import Path

    import dash_backend.services.workflow_builder as wb

    eng = WorkflowEngine(state_path=Path(tmp_path) / "route_state.json")
    monkeypatch.setattr(wb, "workflow_engine", eng)

    created = eng.create(
        "route branch",
        nodes=[
            _node("t", "trigger"),
            _node("c", "condition", field="score", op="gte", value="50"),
            _node("hi", "action"),
            _node("lo", "action"),
        ],
        edges=[
            {"from": "t", "to": "c"},
            {"from": "c", "to": "hi", "condition": "true"},
            {"from": "c", "to": "lo", "condition": "false"},
        ],
    )
    wf_id = created["workflow"]["id"]

    resp_hi = await client.post(
        f"/api/v1/enhanced/workflows/{wf_id}/execute", json={"input_data": {"score": 90}}
    )
    assert resp_hi.status_code == 200
    assert resp_hi.json()["execution"]["nodes_executed"] == ["t", "c", "hi"]

    resp_lo = await client.post(
        f"/api/v1/enhanced/workflows/{wf_id}/execute", json={"input_data": {"score": 5}}
    )
    assert resp_lo.json()["execution"]["nodes_executed"] == ["t", "c", "lo"]

    # Empty/no body still runs (back-compat with the desktop Run button).
    resp_empty = await client.post(f"/api/v1/enhanced/workflows/{wf_id}/execute")
    assert resp_empty.status_code == 200
    assert resp_empty.json()["execution"]["nodes_executed"] == ["t", "c", "lo"]
