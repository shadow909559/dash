"""Tests for the meeting-intelligence proactive closures (#127, §21/#24).

Before #127 two gaps existed against the master plan:
- §21 said DASH *prepares* the briefing before a meeting; the tick only
  said "briefing ready on request" while prepare_briefing sat unused by
  the proactive path.
- §24 produced the post-meeting summary into the store, but nothing
  proactively told the owner it exists.

These tests pin the closures: the tick actually prepares the briefing
and says so honestly, and the summary proactively reaches the owner
through the shared #119 routing — once per real live meeting, never on
re-close, never blocking the close on delivery failure.
"""
from __future__ import annotations

import json

import pytest

from dash_backend.assistant import mobile_bridge as amob
from dash_backend.assistant import proactive as aprobic
from dash_backend.assistant.crm_store import CrmStore
from dash_backend.assistant.meeting_engine import MeetingEngine


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


def _store(tmp_path) -> CrmStore:
    return CrmStore(base_dir=tmp_path / "crm")


# ── §21: the tick PREPARES the briefing ──────────────────────────────────


@pytest.mark.asyncio
async def test_tick_prepares_briefing_and_says_so(tmp_path, monkeypatch):
    import time as _time

    store = _store(tmp_path)
    client = store.create_client("Acme")
    m = store.create_meeting("Sprint review", client_id=client["id"],
                             scheduled_at=_time.time() + 600)
    notifier = _FakeNotifier()

    d = await aprobic.proactive_tick(store, notifier=notifier)
    item = next(i for i in d["items"] if i["kind"] == "meeting_soon")
    assert "briefing prepared." in item["text"]

    # Real effect: the briefing is IN THE STORE, not a claim.
    meeting = store.get_meeting(m["id"])
    assert meeting["briefing"]["meeting"] == "Sprint review"
    assert meeting["briefing"]["client"] == "Acme"


@pytest.mark.asyncio
async def test_tick_briefing_failure_reported_honestly(tmp_path, monkeypatch):
    import time as _time

    store = _store(tmp_path)
    client = store.create_client("Acme")
    store.create_meeting("Review", client_id=client["id"],
                         scheduled_at=_time.time() + 600)

    class _BoomStore(CrmStore):
        def __init__(self, *a, **k):
            pass

        def get_meeting(self, meeting_id):
            raise RuntimeError("store exploded")

        def get_client(self, client_id):
            raise RuntimeError("store exploded")

    import dash_backend.assistant.meeting_engine as me_mod
    monkeypatch.setattr(me_mod, "MeetingEngine",
                        lambda store=None, **k: MeetingEngine(
                            store=_BoomStore()))

    d = await aprobic.proactive_tick(store, notifier=None)
    item = next(i for i in d["items"] if i["kind"] == "meeting_soon")
    assert "briefing will be ready on request." in item["text"]


# ── §24: the summary proactively reaches the owner ───────────────────────


def test_end_meeting_routes_summary_to_owner(tmp_path, monkeypatch):
    from dash_backend.assistant import push as apush

    sent: list[dict] = []
    monkeypatch.setattr(apush, "push_assistant_event",
                        lambda user_id, payload: sent.append(payload))

    store = _store(tmp_path)
    client = store.create_client("Acme")
    m = store.create_meeting("Review", client_id=client["id"])
    eng = MeetingEngine(store=store, notifier=_FakeNotifier())
    eng.start_live(m["id"])
    eng.ingest_turn(m["id"], "Client", "We need WhatsApp notifications too.")
    summary = eng.end_meeting(m["id"])

    assert summary["turns"] == 1
    # Summary contact was pushed as a digest item with routing decision.
    kinds = [i.get("kind") for p in sent for i in p.get("items", [])]
    assert "meeting_summary" in kinds
    item = next(i for p in sent for i in p.get("items", [])
                if i.get("kind") == "meeting_summary")
    assert item["urgency"] == "important"
    assert "ws" in item["channels"]
    assert "1 requirement(s)" in item["text"]
    # Persisted summary also present (unchanged behavior).
    meeting = store.get_meeting(m["id"])
    assert meeting["summary"]["turns"] == 1


def test_end_meeting_without_live_session_never_notifies(
        tmp_path, monkeypatch):
    from dash_backend.assistant import push as apush

    sent: list[dict] = []
    monkeypatch.setattr(apush, "push_assistant_event",
                        lambda user_id, payload: sent.append(payload))

    store = _store(tmp_path)
    m = store.create_meeting("Ghost")
    eng = MeetingEngine(store=store)
    # Re-ending an already-closed meeting (session already popped): must
    # close out the record honestly but NEVER re-notify.
    eng.start_live(m["id"])
    eng.end_meeting(m["id"])
    sent.clear()
    summary2 = eng.end_meeting(m["id"])
    assert summary2["turns"] == 0
    assert sent == []


def test_summary_delivery_failure_does_not_break_close(
        tmp_path, monkeypatch):
    from dash_backend.assistant import push as apush

    def _boom(user_id, payload):
        raise RuntimeError("ws gone")
    monkeypatch.setattr(apush, "push_assistant_event", _boom)

    store = _store(tmp_path)
    client = store.create_client("Acme")
    m = store.create_meeting("Review", client_id=client["id"])
    eng = MeetingEngine(store=store)
    eng.start_live(m["id"])
    summary = eng.end_meeting(m["id"])
    # The close completed and the store holds the summary.
    assert store.get_meeting(m["id"])["summary"]["turns"] == 0 or \
        summary is not None


def test_quiet_hours_suppress_desktop_summary_but_ws_still_delivers(
        tmp_path, monkeypatch):
    import dash_backend.assistant.proactive as _p

    from dash_backend.assistant import push as apush

    sent: list[dict] = []
    monkeypatch.setattr(apush, "push_assistant_event",
                        lambda user_id, payload: sent.append(payload))

    store = _store(tmp_path)
    store.update_preferences({"quiet_hours": {"start": 22, "end": 7}})
    client = store.create_client("Acme")
    m = store.create_meeting("Review", client_id=client["id"])
    # Force the local hour into the quiet window deterministically.
    eng = MeetingEngine(store=store, notifier=_FakeNotifier(),
                        local_hour_fn=lambda: 23)
    eng.start_live(m["id"])
    eng.end_meeting(m["id"])

    item = next(i for p in sent for i in p.get("items", [])
                if i.get("kind") == "meeting_summary")
    assert "ws" in item["channels"]          # ambient record always fires
    assert "desktop" not in item["channels"]  # important < critical
    assert "voice" not in item["channels"]    # summaries never speak
