"""Barge-in and voice-loop latency metrics (spec #8/#11/#45/#114).

Follows tests/test_wake_loop.py's hermetic harness: fake mic source,
scripted transcriber, fake TTS/player, injectable clock, monkeypatched
user resolution — no hardware. The hanging player proves the capture
loop cancels playback when the owner speaks over DASH (barge-in).
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import pytest

from dash_backend.assistant import metrics as ametrics
from dash_backend.voice_system.always_listening import (
    AlwaysListeningLoop,
    WakePhraseMatcher,
    pcm_to_wav,
)

CHUNK_S = 0.1

SPEECH = (b"\x10\x27" * 1600)
SILENCE = (b"\x00\x00" * 1600)
TAIL = int(0.5 / CHUNK_S) + 2
CMD_TAIL = int(1.2 / CHUNK_S) + 2


class FakeSource:
    def __init__(self, clock):
        self.clock = clock
        self.chunks: list[bytes] = []
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def read_chunk(self, timeout: float = 0.1) -> Optional[bytes]:
        if self.chunks:
            self.clock[0] += CHUNK_S
            return self.chunks.pop(0)
        time.sleep(0.005)
        return None


class FakeTranscriber:
    def __init__(self, transcripts):
        self.transcripts = list(transcripts)

    async def __call__(self, wav: bytes) -> str:
        if not self.transcripts:
            return ""
        return self.transcripts.pop(0)


class FakeTTS:
    async def __call__(self, text: str) -> bytes:
        return pcm_to_wav(b"\x00\x01" * 16000)  # ~1s of audio


class HangingPlayer:
    """Simulates long playback; records cancellation (the barge-in proof)."""

    def __init__(self):
        self.played = 0
        self.started = False
        self.cancelled = False

    async def __call__(self, audio: bytes) -> None:
        self.started = True
        self.played += 1
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class InstantPlayer:
    def __init__(self):
        self.played = 0

    async def __call__(self, audio: bytes) -> None:
        self.played += 1


class FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish_sync(self, topic, data=None, **kwargs):
        self.events.append((topic, data or {}))


class Harness:
    def __init__(self, transcripts, player):
        self.clock = [1000.0]
        self.source = FakeSource(self.clock)
        self.transcriber = FakeTranscriber(transcripts)
        self.player = player
        self.bus = FakeBus()
        self.loop = AlwaysListeningLoop(
            enabled=True,
            source=self.source,
            transcriber=self.transcriber,
            tts_synth=FakeTTS(),
            chat_runner=_fake_chat,
            matcher=WakePhraseMatcher("hey dash"),
            vad=None,           # real EnergyVAD — deterministic on fakes
            event_bus=self.bus,
            clock=lambda: self.clock[0],
            player=player,
        )

    def say(self, *chunks: bytes) -> None:
        self.source.chunks.extend(chunks)


async def _fake_chat(text: str) -> str:
    return "Here is my reply."


async def settle(pred, timeout: float = 6.0) -> bool:
    deadline = time.monotonic() + timeout
    while not pred():
        if time.monotonic() > deadline:
            return False
        await asyncio.sleep(0.02)
    return True


@pytest.fixture(autouse=True)
def _metrics_reset():
    ametrics.reset()
    yield
    ametrics.reset()


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    # start() resolves the owner user id through the DB — not under test
    async def _resolve(self=None):
        return "owner"
    monkeypatch.setattr(
        "dash_backend.voice_system.always_listening.AlwaysListeningLoop._resolve_user",
        _resolve)


@pytest.mark.asyncio
async def test_barge_in_cancels_playback_and_publishes_event(monkeypatch):
    """Spec #11: owner speech during playback cancels the reply task,
    publishes voice.interrupted, and clears the echo guard."""
    h = Harness(["hey dash", "what is happening with acme"], HangingPlayer())
    assert (await h.loop.start())["ok"] is True

    h.say(SPEECH, *([SILENCE] * TAIL))
    h.transcriber.transcripts.insert(0, "hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)

    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "what is happening with acme")
    assert await settle(lambda: h.loop.status.command_count == 1)

    # DASH is now speaking (hanging player). Owner starts talking OVER it.
    h.say(*([SPEECH] * 40))
    ok = await settle(lambda: getattr(h.player, "cancelled", False))
    await h.loop.stop()
    assert ok, "speech during playback must cancel the playback task"
    topics = [t for t, _ in h.bus.events]
    assert "voice.interrupted" in topics
    assert h.loop._interrupted_count == 1
    assert h.loop.status.extra.get("barge_in") is True
    assert h.loop._speak_until == 0.0, "echo guard cleared after barge-in"


@pytest.mark.asyncio
async def test_wake_loop_records_measured_latency(monkeypatch):
    """Spec #45/#114: command→reply latency is recorded from the real
    loop path, not claimed."""
    h = Harness(["hey dash", "what time is it"], InstantPlayer())
    assert (await h.loop.start())["ok"] is True

    h.say(SPEECH, *([SILENCE] * TAIL))
    h.transcriber.transcripts.insert(0, "hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)

    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "what time is it")
    ok = await settle(
        lambda: "voice_command_to_reply" in ametrics.summary()["latency"])
    await h.loop.stop()
    assert ok, "the loop must record measured command-to-reply latency"
    s = ametrics.summary()
    assert s["latency"]["voice_command_to_reply"]["n"] >= 1


@pytest.mark.asyncio
async def test_normal_reply_completes_without_barge_in():
    """Regression: with an instant player, the full cycle still speaks
    and no voice.interrupted is published (barge-in only on real speech
    during playback)."""
    h = Harness(["hey dash", "what time is it"], InstantPlayer())
    assert (await h.loop.start())["ok"] is True

    h.say(SPEECH, *([SILENCE] * TAIL))
    h.transcriber.transcripts.insert(0, "hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)

    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "what time is it")
    assert await settle(lambda: h.player.played == 1)
    await h.loop.stop()
    topics = [t for t, _ in h.bus.events]
    assert "voice.reply" in topics and "voice.interrupted" not in topics
    assert h.loop._interrupted_count == 0


# ── Streamed TTS path (decisions.md #102, spec #8/#45) ────────────────────


@pytest.mark.asyncio
async def test_streamed_reply_publishes_ttfa_metric(monkeypatch):
    """Streamed speak: reply publishes with streamed=True and a REAL
    tts_first_audio sample lands in the metrics registry."""
    h = Harness(["hey dash", "what time is it"], InstantPlayer())
    assert (await h.loop.start())["ok"] is True

    h.say(SPEECH, *([SILENCE] * TAIL))
    h.transcriber.transcripts.insert(0, "hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)

    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "what time is it")
    ok = await settle(lambda: any(
        topic == "voice.reply" and data.get("streamed")
        for topic, data in h.bus.events))
    await h.loop.stop()
    assert ok, "streamed path must publish voice.reply with streamed=True"
    s = ametrics.summary()
    assert s["latency"].get("tts_first_audio", {}).get("n", 0) >= 1, \
        "TTFA must be measured from the real streamed path"


@pytest.mark.asyncio
async def test_streamed_reply_barge_in_cancels(monkeypatch):
    """Barge-in works in the streamed path: speech during streamed
    playback cancels the stream task and publishes voice.interrupted."""
    h = Harness(["hey dash", "what is happening with acme"], HangingPlayer())
    assert (await h.loop.start())["ok"] is True

    h.say(SPEECH, *([SILENCE] * TAIL))
    h.transcriber.transcripts.insert(0, "hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)

    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "what is happening with acme")
    assert await settle(lambda: getattr(h.player, "started", False))

    # owner talks over the streamed reply
    h.say(*([SPEECH] * 40))
    ok = await settle(lambda: getattr(h.player, "cancelled", False))
    await h.loop.stop()
    assert ok, "speech during streamed playback must cancel the stream"
    topics = [t for t, _ in h.bus.events]
    assert "voice.interrupted" in topics
    assert h.loop._interrupted_count == 1


@pytest.mark.asyncio
async def test_meeting_context_injected_into_voice_commands():
    """Spec #29/#82: an attached meeting grounds every voice command and
    the mode travels with it; clearing removes it."""
    replies: list[str] = []

    async def recorder(text: str) -> str:
        replies.append(text)
        return "Grounded answer."

    h = Harness(["hey dash", "what did the client just ask"], InstantPlayer())
    h.loop._chat_runner = recorder
    h.loop.set_meeting_context({
        "meeting_id": "mt1", "title": "Acme sync", "mode": "assisted"})
    assert (await h.loop.start())["ok"] is True

    h.say(SPEECH, *([SILENCE] * TAIL))
    h.transcriber.transcripts.insert(0, "hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)

    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "what did the client just ask")
    assert await settle(lambda: len(replies) == 1)
    await h.loop.stop()
    assert replies and replies[0].startswith("[Active meeting: Acme sync")
    assert "assisted" in replies[0]

    h.loop.clear_meeting_context()
    with pytest.raises(ValueError):
        h.loop.set_meeting_context({"meeting_id": "m", "mode": "dictator"})
