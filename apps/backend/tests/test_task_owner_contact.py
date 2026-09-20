"""Tests for immediate task-event owner contact (decisions.md #124).

The orchestrator's ws push is best-effort — with no client connected, a
task failure used to vanish until the next 5-minute digest tick. These
tests pin the immediate intake path: failure/recovery/confirmation
events reach the owner through the shared #119 urgency routing, are
deduped against the digest grouping and across repeats, respect the
owner's urgency floor, and never fire for routine events.
"""
from __future__ import annotations

import pytest

from dash_backend.assistant import mobile_bridge as amob
from dash_backend.assistant import proactive as aprobic
from dash_backend.assistant.crm_store import CrmStore


class _FakeNotifier:
    def __init__(self):
        self.calls = []

    async def show(self, title, message):
        self.calls.append({"title": title, "message": message})


@pytest.fixture(autouse=True)
def _reset_dedupe():
    aprobic._seen.clear()
    amob.reset_seen()
    yield
    aprobic._seen.clear()
    amob.reset_seen()


def _task(status="failed", goal="prepare demo", task_id="t1"):
    return {"id": task_id, "goal": goal, "status": status}


@pytest.mark.asyncio
async def test_failure_reaches_owner_immediately(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    notifier = _FakeNotifier()
    item = await aprobic.notify_task_event(
        _task(), "failed", store=store, notifier=notifier)
    assert item is not None
    assert item["kind"] == "task_failed"
    assert item["urgency"] == "urgent"
    # Routed through the ONE policy: urgent → desktop + phone + ws
    assert "desktop" in item["channels"]
    assert "phone" in item["channels"]
    assert notifier.calls, "desktop notifier must fire with no ws client"
    assert "prepare demo" in notifier.calls[0]["message"]


@pytest.mark.asyncio
async def test_failure_deduped_second_time_and_against_digest(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    notifier = _FakeNotifier()
    await aprobic.notify_task_event(_task(), "failed", store=store,
                                    notifier=notifier)
    # Same task failing again the same day → silence (bounded, honest)
    item2 = await aprobic.notify_task_event(_task(), "failed", store=store,
                                            notifier=notifier)
    assert item2 is None
    assert len(notifier.calls) == 1
    # The digest tick's grouped-failures path excludes this task (the
    # immediate path marked task_failed_owner:t1 today), so the tick
    # cannot double-notify the same failure.
    assert aprobic._already_sent("task_failed_owner:t1")
    assert not aprobic._already_sent("task_failed_owner:never-seen")


@pytest.mark.asyncio
async def test_waiting_confirmation_is_critical(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    notifier = _FakeNotifier()
    item = await aprobic.notify_task_event(
        _task(status="waiting_confirmation"), "waiting_confirmation",
        store=store, notifier=notifier)
    assert item["urgency"] == "critical"
    assert "confirmation" in item["text"]
    # Critical reaches the owner even during quiet hours (#119)
    store.update_preferences({"quiet_hours": {"start": 0, "end": 0}})
    assert item["channels"], "critical must route somewhere at any hour"


@pytest.mark.asyncio
async def test_recovery_only_first_push_per_day(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    notifier = _FakeNotifier()
    item = await aprobic.notify_task_event(_task(), "recovery",
                                           store=store, notifier=notifier)
    assert item is not None and item["kind"] == "task_recovery"
    # First recovery push reaches the owner (urgent-routed → desktop)…
    assert len(notifier.calls) == 1
    # …but retries are progress, not news — subsequent ones stay silent.
    again = await aprobic.notify_task_event(_task(), "recovery",
                                            store=store, notifier=notifier)
    assert again is None
    assert len(notifier.calls) == 1


@pytest.mark.asyncio
async def test_urgency_floor_lifts_phone_off_failure(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    # Owner raised the floor: phone only for critical (no desktop either —
    # the floor is global; ws push still always happens).
    store.update_preferences({"notification_urgency_floor": "critical"})
    notifier = _FakeNotifier()
    item = await aprobic.notify_task_event(_task(), "failed", store=store,
                                           notifier=notifier)
    assert item is not None
    assert "phone" not in item["channels"]
    assert "desktop" not in item["channels"]
    assert notifier.calls == []


@pytest.mark.asyncio
async def test_routine_events_are_ignored(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    notifier = _FakeNotifier()
    for ev in ("created", "step_started", "step_completed", "completed",
               "replanned"):
        item = await aprobic.notify_task_event(_task(), ev, store=store,
                                               notifier=notifier)
        assert item is None, f"{ev} must not page the owner"
    assert notifier.calls == []


@pytest.mark.asyncio
async def test_no_notifier_no_store_still_routes_ws(tmp_path, monkeypatch):
    """Minimal path: neither store nor notifier injected — must not raise
    and must still produce the ws-side item (ws is always allowed)."""
    from dash_backend.assistant import push as apush

    sent = []
    monkeypatch.setattr(apush, "push_assistant_event",
                        lambda user_id, payload: sent.append(payload))
    item = await aprobic.notify_task_event(_task(), "failed")
    assert item is not None
    assert sent and sent[0]["type"] == "proactive.digest"
    assert sent[0].get("immediate") is True


@pytest.mark.asyncio
async def test_eventbus_topic_published(tmp_path):
    """The event mirrors onto the EventBus for observability (#124)."""
    import asyncio

    from dash_backend.events.event_bus import get_event_bus

    bus = get_event_bus()
    received = []
    sub = bus.subscribe("task.orchestrator.failed",
                        lambda e: received.append(e) or asyncio.sleep(0))
    try:
        await aprobic.notify_task_event(_task(), "failed",
                                        store=CrmStore(base_dir=tmp_path))
        await asyncio.sleep(0.05)
        assert received, "failure must publish task.orchestrator.failed"
        assert received[0].data["task_id"] == "t1"
        assert received[0].data["status"] == "failed"
    finally:
        bus.unsubscribe(sub)
