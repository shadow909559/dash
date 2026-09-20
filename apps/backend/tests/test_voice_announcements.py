"""Voice announcement tests (decisions.md #126) — the "voice" channel of
the #119 urgency policy, consumed for CRITICAL owner-contact items.

The always-listening loop's ``announce()`` reuses the real reply pipeline
(streamed TTS, presence claim, barge-in). These tests pin:
- announce speaks through _speak ONLY when the loop is actually listening
- the honest refusals: disabled loop, stopped loop, speech in progress,
  empty text — no fabricated speech
- the proactive intake hands critical task events to the loop and the
  result lands on the item; failures never break owner contact
"""
from __future__ import annotations

import asyncio

import pytest

from dash_backend.assistant import mobile_bridge as amob
from dash_backend.assistant import proactive as aprobic
from dash_backend.assistant.crm_store import CrmStore
from dash_backend.voice_system.always_listening import AlwaysListeningLoop


# ── announce() unit behavior ─────────────────────────────────────────────


def _listening_loop(speak_calls: list) -> AlwaysListeningLoop:
    loop = AlwaysListeningLoop()
    loop.status.state = "listening"
    async def fake_speak(text):
        speak_calls.append(text)
    loop._speak = fake_speak
    return loop


@pytest.mark.asyncio
async def test_announce_speaks_when_listening():
    calls: list[str] = []
    loop = _listening_loop(calls)
    result = await loop.announce("Task 'deploy' needs your confirmation.")
    assert result["ok"] is True
    # announcement is cancellable via the same speak task slot as replies
    assert loop._speak_task is not None
    await loop._speak_task
    assert calls == ["Task 'deploy' needs your confirmation."]


@pytest.mark.asyncio
async def test_announce_refuses_disabled_or_stopped_loop():
    calls: list[str] = []
    loop = AlwaysListeningLoop()  # default: disabled
    assert loop.status.state == "disabled"
    result = await loop.announce("hello")
    assert result["ok"] is False
    assert "not listening" in result["reason"]

    loop2 = _listening_loop(calls)
    loop2.status.state = "stopped"
    result2 = await loop2.announce("hello")
    assert result2["ok"] is False
    assert calls == []  # nothing was spoken


@pytest.mark.asyncio
async def test_announce_refuses_while_speaking():
    calls: list[str] = []
    loop = _listening_loop(calls)
    # Simulate a reply in progress: the speak task slot is busy.
    block = asyncio.Event()
    async def busy_speak(text):
        await block.wait()
    loop._speak_task = asyncio.create_task(busy_speak("reply"))
    result = await loop.announce("urgent thing")
    assert result["ok"] is False
    assert result["reason"] == "speech already in progress"
    block.set()
    await loop._speak_task


@pytest.mark.asyncio
async def test_announce_empty_text_is_honest():
    loop = AlwaysListeningLoop()
    result = await loop.announce("   ")
    assert result["ok"] is False
    assert result["reason"] == "empty announcement"


# ── proactive intake → voice channel ─────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_dedupe():
    aprobic._seen.clear()
    amob.reset_seen()
    yield
    aprobic._seen.clear()
    amob.reset_seen()


class _FakeNotifier:
    def __init__(self):
        self.calls = []

    async def show(self, title, message):
        self.calls.append({"title": title, "message": message})


@pytest.mark.asyncio
async def test_critical_event_reaches_voice_channel(tmp_path, monkeypatch):
    """waiting_confirmation is critical → routed to voice → spoken."""
    calls: list[str] = []
    loop = _listening_loop(calls)
    monkeypatch.setattr(
        "dash_backend.voice_system.always_listening.get_wake_loop",
        lambda: loop)

    store = CrmStore(base_dir=tmp_path)
    notifier = _FakeNotifier()
    task = {"id": "t1", "goal": "deploy fix", "status": "waiting_confirmation"}
    item = await aprobic.notify_task_event(
        task, "waiting_confirmation", store=store, notifier=notifier)
    assert item is not None
    assert "voice" in item["channels"]
    assert item["voice_result"]["ok"] is True
    await loop._speak_task
    assert calls and "confirmation" in calls[0]


@pytest.mark.asyncio
async def test_voice_refusal_recorded_not_raised(tmp_path, monkeypatch):
    """Loop disabled (e.g. no mic): announce honestly refuses, the item
    still routes through ws/desktop/phone — owner contact survives."""
    loop = AlwaysListeningLoop()  # disabled
    monkeypatch.setattr(
        "dash_backend.voice_system.always_listening.get_wake_loop",
        lambda: loop)
    store = CrmStore(base_dir=tmp_path)
    notifier = _FakeNotifier()
    item = await aprobic.notify_task_event(
        {"id": "t2", "goal": "g", "status": "waiting_confirmation"},
        "waiting_confirmation", store=store, notifier=notifier)
    assert item["voice_result"]["ok"] is False
    assert "not listening" in item["voice_result"]["reason"]
    assert notifier.calls, "desktop still notified"


@pytest.mark.asyncio
async def test_voice_failure_never_breaks_owner_contact(
        tmp_path, monkeypatch):
    """announce() raising (no loop module, mic crash, whatever) must not
    break the rest of the owner-contact chain."""
    def _boom():
        raise RuntimeError("mic exploded")
    monkeypatch.setattr(
        "dash_backend.voice_system.always_listening.get_wake_loop", _boom)
    store = CrmStore(base_dir=tmp_path)
    notifier = _FakeNotifier()
    item = await aprobic.notify_task_event(
        {"id": "t3", "goal": "g", "status": "failed"},
        "failed", store=store, notifier=notifier)
    assert item is not None
    # urgent ≥ "important" desktop minimum → desktop still notified
    assert notifier.calls, "urgent failure still reaches the desktop"


@pytest.mark.asyncio
async def test_urgent_failure_has_no_voice_channel(tmp_path, monkeypatch):
    """Only critical may speak — an urgent failure must not interrupt."""
    calls: list[str] = []
    loop = _listening_loop(calls)
    monkeypatch.setattr(
        "dash_backend.voice_system.always_listening.get_wake_loop",
        lambda: loop)
    store = CrmStore(base_dir=tmp_path)
    item = await aprobic.notify_task_event(
        {"id": "t4", "goal": "g", "status": "failed"},
        "failed", store=store)
    assert item["urgency"] == "urgent"
    assert "voice" not in item["channels"]
    assert calls == []
