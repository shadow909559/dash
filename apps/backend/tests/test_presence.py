"""PresenceEngine tests (decisions.md #117) — fusion, priority, TTL,
sticky states, and the four real wirings (voice loop, task orchestrator,
approval engine, meeting engine).

Presence is the one authoritative observable signal, so its tests pin the
behaviors the orb will trust: conflicts resolve by priority, claims of
dead sources expire, sticky claims don't, and every wiring maps REAL
state — never fabricated states.
"""

from __future__ import annotations

import time

import pytest

from dash_backend.assistant.presence import (
    PRESENCE_PRIORITY,
    Presence,
    PresenceEngine,
    get_presence_engine,
    reset_presence_engine,
)


@pytest.fixture(autouse=True)
def _fresh_engine():
    reset_presence_engine()
    yield
    reset_presence_engine()


# ── Owner-observable transition history (decisions.md #123) ─────────────


def test_history_records_real_transitions_only():
    e = PresenceEngine()
    e.claim("voice_loop", "speaking", "reply playback")
    e.release("voice_loop")
    e.claim("orchestrator", "executing", "task run")
    e.release("orchestrator")
    h = e.history()
    states = [item["state"] for item in h]
    assert states == ["speaking", "idle", "executing", "idle"]
    # Real source provenance, oldest first.
    assert h[0]["source"] == "voice_loop"
    assert h[2]["source"] == "orchestrator"
    # Monotonic timestamps.
    times = [item["at"] for item in h]
    assert times == sorted(times)


def test_history_no_entry_for_renewing_same_state():
    e = PresenceEngine()
    e.claim("chat", "thinking", "run 1")
    n = len(e.history())
    e.claim("chat", "thinking", "run 2")  # same state, not a transition
    assert len(e.history()) == n


def test_history_records_expiry_transitions():
    e = PresenceEngine()
    e.claim("voice_loop", "speaking", "reply", ttl=1.0)  # engine's TTL floor
    assert e.history()[-1]["state"] == "speaking"
    time.sleep(1.1)
    e.snapshot()  # read path resolves expiry → idle
    assert e.history()[-1]["state"] == "idle"
    assert e.history()[-1]["source"] == ""


def test_history_bounded_and_limit_clamped():
    e = PresenceEngine()
    for i in range(60):  # 60 transitions, ring holds 50
        e.claim("chat", "thinking", f"run {i}")
        e.release("chat")
    assert len(e.history()) == 50
    assert e.history()[-1]["state"] == "idle"       # newest: the last release
    assert e.history()[-2]["detail"] == "run 59"    # just before it
    assert len(e.history(5)) == 5
    assert len(e.history(999)) == 50  # clamped to ring size
    assert len(e.history("bogus")) == 50  # defensive clamp


# ── Core fusion behavior ─────────────────────────────────────────────


def test_starts_idle():
    e = PresenceEngine()
    assert e.state == Presence.IDLE


def test_single_claim_resolves_and_includes_source():
    e = PresenceEngine()
    snap = e.claim("voice_loop", Presence.SPEAKING, detail="replying")
    assert snap["state"] == Presence.SPEAKING
    assert snap["source"] == "voice_loop"
    assert snap["detail"] == "replying"
    assert any(c["source"] == "voice_loop" for c in snap["claims"])


def test_priority_fusion_approval_outruns_speaking():
    e = PresenceEngine()
    e.claim("voice_loop", Presence.SPEAKING)
    snap = e.claim("approvals", Presence.WAITING_FOR_APPROVAL)
    assert snap["state"] == Presence.WAITING_FOR_APPROVAL


def test_release_returns_to_lower_priority_claim():
    e = PresenceEngine()
    e.claim("voice_loop", Presence.SPEAKING)
    e.claim("approvals", Presence.WAITING_FOR_APPROVAL)
    e.release("approvals")
    assert e.state == Presence.SPEAKING


def test_release_state_only_drops_matching_state():
    e = PresenceEngine()
    e.claim("voice_loop", Presence.SPEAKING)
    # A stale release for a different state must not clobber
    e.release_state("voice_loop", Presence.LISTENING)
    assert e.state == Presence.SPEAKING
    e.release_state("voice_loop", Presence.SPEAKING)
    assert e.state == Presence.IDLE


def test_error_is_top_priority():
    e = PresenceEngine()
    e.claim("approvals", Presence.WAITING_FOR_APPROVAL)
    e.claim("voice_loop", Presence.ERROR, detail="mic dead")
    assert e.state == Presence.ERROR


def test_unknown_state_rejected():
    e = PresenceEngine()
    with pytest.raises(ValueError):
        e.claim("voice_loop", "vibing")


def test_snapshot_shows_all_claims():
    e = PresenceEngine()
    e.claim("voice_loop", Presence.LISTENING)
    e.claim("meetings", Presence.IN_MEETING)
    snap = e.snapshot()
    sources = {c["source"] for c in snap["claims"]}
    assert {"voice_loop", "meetings"} <= sources
    assert snap["state"] == Presence.IN_MEETING


# ── TTL honesty ──────────────────────────────────────────────────────────


def test_transient_claim_expires_after_ttl():
    e = PresenceEngine()
    e.claim("voice_loop", Presence.SPEAKING, ttl=1.0)
    assert e.state == Presence.SPEAKING
    # Force expiry by faking the clock
    with e._lock:
        c = e._claims["voice_loop"]
        c.expires_at = time.time() - 0.01
    snap = e.snapshot()
    assert snap["state"] == Presence.IDLE
    assert "voice_loop" not in {x["source"] for x in snap["claims"]}


def test_sticky_states_do_not_expire():
    e = PresenceEngine()
    for state in (Presence.WAITING_FOR_APPROVAL, Presence.IN_MEETING,
                  Presence.IN_CALL, Presence.PAUSED):
        e2 = PresenceEngine()
        e2.claim("approvals", state)
        c = e2._claims["approvals"]
        assert c.expires_at is None, f"{state} must be sticky"


def test_renewed_claim_refreshes_expiry():
    e = PresenceEngine()
    e.claim("voice_loop", Presence.EXECUTING, ttl=10.0)
    first = e._claims["voice_loop"].expires_at
    time.sleep(0.01)
    e.claim("voice_loop", Presence.EXECUTING, ttl=10.0)
    second = e._claims["voice_loop"].expires_at
    assert second > first


# ── Real wirings: task orchestrator ─────────────────────────────────────


def _mk_orchestrator(tmp_path):
    """Real orchestrator with its real store pointed at a temp file."""
    from dash_backend.autonomous.task_orchestrator import TaskOrchestrator
    from dash_backend.autonomous.task_state import TaskStateStore

    store = TaskStateStore(path=tmp_path / "tasks.json")
    return TaskOrchestrator(store=store)


@pytest.mark.asyncio
async def test_task_running_claims_executing(tmp_path):
    orch = _mk_orchestrator(tmp_path)
    from dash_backend.autonomous.task_state import AgentTask, TaskStatus

    task = AgentTask(id="t1", goal="demo task", status=TaskStatus.RUNNING)
    orch._tasks[task.id] = task
    orch._claim_presence(task)
    from dash_backend.assistant.presence import get_presence_engine
    assert get_presence_engine().state == Presence.EXECUTING


@pytest.mark.asyncio
async def test_terminal_task_releases_when_none_active(tmp_path):
    orch = _mk_orchestrator(tmp_path)
    from dash_backend.autonomous.task_state import AgentTask, TaskStatus

    task = AgentTask(id="t2", goal="done task", status=TaskStatus.COMPLETED)
    orch._tasks[task.id] = task
    orch._claim_presence(task)
    from dash_backend.assistant.presence import get_presence_engine
    assert get_presence_engine().state == Presence.IDLE


@pytest.mark.asyncio
async def test_waiting_confirmation_claims_waiting_for_approval(tmp_path):
    orch = _mk_orchestrator(tmp_path)
    from dash_backend.autonomous.task_state import AgentTask, TaskStatus

    task = AgentTask(id="t3", goal="risky task", status=TaskStatus.WAITING_CONFIRMATION)
    orch._tasks[task.id] = task
    orch._claim_presence(task)
    from dash_backend.assistant.presence import get_presence_engine
    assert get_presence_engine().state == Presence.WAITING_FOR_APPROVAL


# ── Real wirings: approval engine ────────────────────────────────────────


@pytest.mark.asyncio
async def test_approval_creation_claims_and_resolution_releases(tmp_path):
    from dash_backend.assistant.authority import ApprovalEngine
    from dash_backend.assistant.crm_store import CrmStore
    from dash_backend.services.audit_logs import AuditLogService

    store = CrmStore(base_dir=tmp_path / "crm")
    audit = AuditLogService(log_dir=str(tmp_path / "audit"))
    engine = ApprovalEngine()

    req = engine.create_request(
        store, audit, action_kind="send_email",
        description="Email Acme the revised quote",
        reason="owner asked", risk_level=3, target="acme@example.com",
    )
    from dash_backend.assistant.presence import get_presence_engine
    pe = get_presence_engine()
    assert pe.state == Presence.WAITING_FOR_APPROVAL

    resolved = engine.resolve(store, audit, req["id"], "approve")
    assert resolved is not None
    assert pe.state == Presence.IDLE


@pytest.mark.asyncio
async def test_second_pending_approval_keeps_claim(tmp_path):
    from dash_backend.assistant.authority import ApprovalEngine
    from dash_backend.assistant.crm_store import CrmStore
    from dash_backend.services.audit_logs import AuditLogService

    store = CrmStore(base_dir=tmp_path / "crm")
    audit = AuditLogService(log_dir=str(tmp_path / "audit"))
    engine = ApprovalEngine()
    pe = get_presence_engine()

    r1 = engine.create_request(store, audit, "send_email", "A", "r", 3, "t1")
    r2 = engine.create_request(store, audit, "deploy", "B", "r", 4, "t2")
    assert pe.state == Presence.WAITING_FOR_APPROVAL

    engine.resolve(store, audit, r1["id"], "approve")
    assert pe.state == Presence.WAITING_FOR_APPROVAL  # r2 still pending
    engine.resolve(store, audit, r2["id"], "reject")
    assert pe.state == Presence.IDLE


# ── Real wirings: meeting engine ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_meeting_start_claims_and_end_releases(tmp_path):
    from dash_backend.assistant.crm_store import CrmStore
    from dash_backend.assistant.meeting_engine import MeetingEngine

    store = CrmStore(base_dir=tmp_path / "crm")
    client = store.create_client("Acme")
    meeting = store.create_meeting("Scope review", client_id=client["id"])
    engine = MeetingEngine(store=store)

    started = engine.start_live(meeting["id"], mode="listen_only")
    assert started is not None
    from dash_backend.assistant.presence import get_presence_engine
    assert get_presence_engine().state == Presence.IN_MEETING

    engine.end_meeting(meeting["id"])
    assert get_presence_engine().state == Presence.IDLE


# ── Presence API route contract ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_presence_rest_endpoint(monkeypatch):
    """The REST snapshot route returns the live engine snapshot.

    Authenticates exactly like conftest's client: device token via the
    DASH_DEVICE_TOKEN test bootstrap (see local_identity.py:165).
    """
    from fastapi.testclient import TestClient

    from dash_backend.assistant.presence import get_presence_engine
    from dash_backend.main import create_app
    from dash_backend.security import local_identity

    monkeypatch.setenv("DASH_DEVICE_TOKEN", "dash-test-device-token-" + "a" * 32)
    local_identity.get_identity(force_reload=True)

    get_presence_engine().claim("voice_loop", Presence.MONITORING)
    app = create_app()
    headers = {"Authorization": "Bearer dash-test-device-token-" + "a" * 32}
    with TestClient(app) as client:
        resp = client.get("/api/v1/assistant/presence", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == Presence.MONITORING
        assert isinstance(body["claims"], list)
