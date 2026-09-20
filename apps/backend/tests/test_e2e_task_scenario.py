"""End-to-end scenario (master plan §46–48 spirit, decisions.md #125).

ONE task through the REAL orchestrator and the REAL owner-contact chain:

    step fails → retries with recovery → owner contacted once
    → authority gate (high-risk step) → owner contacted again
    → approval → verified completion → honest final report

Every stage is asserted on a real observable surface — task events,
presence claims, ws payloads, EventBus topics, routing decisions — never
on internal flags. Real components under test: TaskOrchestrator,
task_verifier, the #124 immediate intake, the #119 urgency policy, the
presence engine (#117), and the EventBus topic (#124). Only the LLM
planner and the ToolManager are faked (deterministic, hermetic); the
desktop notifier/audit are absent by design (pytest-quiet wiring), which
this scenario treats as the "no desktop session" condition the ws path
must survive.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from dash_backend.assistant import mobile_bridge as amob
from dash_backend.assistant import proactive as aprobic
from dash_backend.assistant.crm_store import CrmStore
from dash_backend.assistant.presence import (
    Presence,
    PresenceEngine,
    get_presence_engine,
    reset_presence_engine,
)
from dash_backend.autonomous import task_orchestrator as orch_mod
from dash_backend.autonomous.task_orchestrator import TaskOrchestrator
from dash_backend.autonomous.task_state import (
    AgentTask,
    RiskLevel,
    StepStatus,
    TaskStateStore,
    TaskStatus,
    TaskStep,
)
from dash_backend.autonomous.task_verifier import VerificationStatus

# ── Fakes ─────────────────────────────────────────────────────────────────


class _FakeParam:
    def __init__(self, name: str):
        self.name = name
        self.required = True


class _FakeSpec:
    def __init__(self, params):
        self.parameters = params


class _FakeTool:
    def __init__(self, required_names):
        self.spec = _FakeSpec([_FakeParam(n) for n in required_names])


class _FakeToolManager:
    """Deterministic tool surface: 'flaky_probe' fails on its first call,
    succeeds afterwards; 'commit_deploy' records its executions."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.flaky_done = False
        self.deploy_done = False

    def get_tool(self, name):
        if name in ("flaky_probe", "commit_deploy"):
            return _FakeTool([])
        return None

    def select_tool_definitions(self, desc, max_tools=10):
        return []

    async def execute(self, tool, args, ctx):
        self.calls.append((tool, dict(args)))
        if tool == "flaky_probe":
            if not self.flaky_done:
                self.flaky_done = True
                return {"status": "error", "error_message": "probe device busy"}
            return {"status": "ok", "summary": "probe clean"}
        if tool == "commit_deploy":
            self.deploy_done = True
            return {"status": "ok", "summary": "deployed"}
        return {"status": "error", "error_message": f"unknown tool {tool}"}


@pytest.fixture
def fake_tools(monkeypatch):
    manager = _FakeToolManager()
    monkeypatch.setattr(
        "dash_backend.tools.tool_manager.get_tool_manager", lambda: manager
    )
    return manager


@pytest.fixture(autouse=True)
def _clean_observability():
    aprobic._seen.clear()
    amob.reset_seen()
    reset_presence_engine()
    yield
    aprobic._seen.clear()
    amob.reset_seen()
    reset_presence_engine()


@pytest.fixture
def ws_capture(monkeypatch):
    """Capture BOTH live push surfaces the desktop consumes:
    - assistant ws (proactive digests / immediate owner contact)
    - task ws (orchestrator progress events)"""
    from dash_backend.assistant import push as apush
    from dash_backend.autonomous import task_push

    sent: list[dict] = []
    monkeypatch.setattr(apush, "push_assistant_event",
                        lambda user_id, payload: sent.append(payload))
    monkeypatch.setattr(task_push, "push_task_event",
                        lambda user_id, payload: sent.append(payload))
    return sent


@pytest.fixture
def task_events_capture():
    """Capture EventBus task.orchestrator.* publications."""
    import asyncio as _asyncio

    from dash_backend.events.event_bus import get_event_bus

    received: list = []
    bus = get_event_bus()
    subs = [
        bus.subscribe("task.orchestrator.failed",
                      lambda e: received.append(e) or _asyncio.sleep(0)),
        bus.subscribe("task.orchestrator.waiting_confirmation",
                      lambda e: received.append(e) or _asyncio.sleep(0)),
    ]
    yield received
    for sub in subs:
        bus.unsubscribe(sub)


def make_orchestrator(store, monkeypatch) -> TaskOrchestrator:
    """Orchestrator with the LLM planner replaced by the scenario plan."""

    async def fake_plan(goal, context=None):
        task = AgentTask(goal=goal)
        task.steps = [
            TaskStep(
                id="probe", index=0, description="probe the service",
                tool="flaky_probe", args={},
                risk=RiskLevel.SAFE, depends_on=[],
                verify={"type": "output_contains", "expect": "clean"},
                max_attempts=3,
            ),
            TaskStep(
                id="deploy", index=1, description="deploy the fix",
                tool="commit_deploy", args={},
                risk=RiskLevel.HIGH, depends_on=["probe"],
                verify={"type": "output_contains", "expect": "deployed"},
                max_attempts=2,
            ),
        ]
        return task

    monkeypatch.setattr(orch_mod, "plan_task_graph", fake_plan)
    return TaskOrchestrator(store=store)


async def _wait(condition, timeout_s=5.0):
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if condition():
            return True
        await asyncio.sleep(0.02)
    return False


# ── The scenario ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fail_recover_gate_approve_verify_complete(
        tmp_path, monkeypatch, fake_tools, ws_capture,
        task_events_capture):
    store = TaskStateStore(path=tmp_path / "task_state.json")
    crm = CrmStore(base_dir=tmp_path / "crm")
    o = make_orchestrator(store, monkeypatch)

    task = await o.create_task("fix and deploy the service")
    engine: PresenceEngine = get_presence_engine()

    # 1. The run starts — presence claims executing from the REAL status.
    assert await _wait(
        lambda: engine.state in (Presence.EXECUTING, Presence.RECOVERING))
    claim = next(c for c in engine.snapshot()["claims"]
                 if c["source"] == "task_orchestrator")
    assert claim["state"] in (Presence.EXECUTING, Presence.RECOVERING)

    # 2. Step 1 fails on attempt 1 → recovery event → owner contacted ONCE
    #    (urgent-routed, via the #124 immediate intake).
    assert await _wait(
        lambda: any(s.attempts == 1 for s in task.steps))
    assert await _wait(lambda: any(
        p.get("type") == "proactive.digest" and p.get("immediate")
        and any(i.get("kind") == "task_recovery" for i in p["items"])
        for p in ws_capture))
    recovery_item = next(
        i for p in ws_capture if p.get("type") == "proactive.digest"
        for i in p.get("items", []) if i.get("kind") == "task_recovery")
    assert recovery_item["urgency"] == "urgent"
    assert "phone" in recovery_item["channels"]  # urgent → phone per #119
    # Retries stay silent: still exactly one recovery item afterwards.
    await _wait(lambda: fake_tools.flaky_done and task.steps[0].status
                == StepStatus.COMPLETED, timeout_s=10.0)
    assert sum(1 for p in ws_capture if p.get("type") == "proactive.digest"
               and any(i.get("kind") == "task_recovery"
                       for i in p.get("items", []))) == 1

    # 3. Probe verified on the observed output — never assumed.
    assert task.steps[0].verification.status == VerificationStatus.VERIFIED

    # 4. HIGH-risk step hits the authority gate — the LLM cannot pass it;
    #    the task stops and the owner is asked (critical → breaks through).
    assert await _wait(
        lambda: task.status == TaskStatus.WAITING_CONFIRMATION)
    assert fake_tools.deploy_done is False, "gate must precede execution"
    gate_events = [p for p in ws_capture
                   if p.get("type") == "task.waiting_confirmation"]
    assert gate_events, "gate must be pushed to the ws"
    assert gate_events[0]["task"]["pending_confirmation"]["risk"] == "high"
    assert await _wait(lambda: any(
        p.get("type") == "proactive.digest" and p.get("immediate")
        and any(i.get("kind") == "task_waiting_confirmation"
                for i in p["items"]) for p in ws_capture))
    gate_item = next(
        i for p in ws_capture if p.get("type") == "proactive.digest"
        for i in p.get("items", [])
        if i.get("kind") == "task_waiting_confirmation")
    assert gate_item["urgency"] == "critical"
    assert engine.state == Presence.WAITING_FOR_APPROVAL

    # 5. The EventBus mirror received the observable topics.
    await asyncio.sleep(0.05)
    assert any(e.data.get("task_id") == task.id
               and e.topic == "task.orchestrator.waiting_confirmation"
               for e in task_events_capture)

    # 6. Owner approves → the tool runs exactly once → verified completion.
    assert await o.approve_step(task.id, approved=True)
    assert await _wait(
        lambda: task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED),
        timeout_s=10.0)
    assert task.status == TaskStatus.COMPLETED
    assert fake_tools.deploy_done is True
    assert fake_tools.calls.count(("commit_deploy", {})) == 1, \
        "approval must execute the gated tool exactly once"
    assert task.steps[1].verification.status == VerificationStatus.VERIFIED

    # 7. The honest final report: what ran, what was verified, attempt count.
    report = task.final_report
    assert report["status"] == "completed"
    assert report["completed_steps"] == ["probe the service", "deploy the fix"]
    assert report["attempts"] == {"probe": 2}  # the retry is recorded, not hidden

    # 8. Terminal task releases the presence claim (idle system).
    assert await _wait(lambda: "task_orchestrator"
                       not in {c["source"] for c in engine.snapshot()["claims"]})


@pytest.mark.asyncio
async def test_rejection_ends_honestly(
        tmp_path, monkeypatch, fake_tools, ws_capture):
    """Owner says NO: the gated step is skipped, the task cannot claim
    success with a skipped step, and the deploy never happens."""
    store = TaskStateStore(path=tmp_path / "task_state.json")
    o = make_orchestrator(store, monkeypatch)

    task = await o.create_task("fix and deploy the service")
    assert await _wait(
        lambda: task.status == TaskStatus.WAITING_CONFIRMATION,
        timeout_s=10.0)
    assert await o.approve_step(task.id, approved=False)
    assert await _wait(
        lambda: task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED),
        timeout_s=10.0)
    assert fake_tools.deploy_done is False
    assert task.status == TaskStatus.FAILED  # skipped step ⇒ not complete
    assert task.final_report["skipped_steps"] == ["deploy the fix"]
