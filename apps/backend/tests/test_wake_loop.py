"""Always-listening wake-word loop tests (decisions.md #86, audit #87).

All hermetic: fake mic source, scripted fake transcriber, fake TTS, fake
player, injectable clock — no microphone, no Whisper model, no speaker.
The fake source advances the injected clock by one chunk-duration per
consumed chunk, so silence tails and timeouts progress deterministically
with the audio stream itself (empty reads freeze time — no wall-clock
flakiness).

Proves the honesty contract: wake requires a real phrase match, babble
never reaches the LLM, every stage failure is recorded (never silently
swallowed), DASH cannot wake on its own echo, and the disabled loop refuses
to start with its real reason.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import pytest

from dash_backend.voice_system.always_listening import (
    AlwaysListeningLoop,
    WakePhraseMatcher,
    pcm_to_wav,
)

AUTH = {"Authorization": "Bearer dash-test-device-token-" + "a" * 32}

CHUNK_S = 0.1  # each fake chunk represents 100ms of stream time


class FakeSource:
    """Scripted mic source; advances the injected clock per consumed chunk."""

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
        time.sleep(0.005)  # mimic the real source's blocking wait
        return None


class FakeTranscriber:
    """Returns scripted transcripts in order; records WAV payloads."""

    def __init__(self, transcripts):
        self.transcripts = list(transcripts)
        self.calls: list[bytes] = []

    async def __call__(self, wav_bytes: bytes) -> str:
        self.calls.append(wav_bytes)
        if not self.transcripts:
            return ""
        item = self.transcripts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeTTS:
    def __init__(self):
        self.texts: list[str] = []

    async def __call__(self, text: str) -> bytes:
        self.texts.append(text)
        return pcm_to_wav(b"\x00\x01" * 16000)  # ~1s of WAV


class FakePlayer:
    def __init__(self):
        self.played: list[bytes] = []

    async def __call__(self, audio: bytes) -> None:
        self.played.append(audio)


class FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish_sync(self, topic, data=None, **kwargs):
        self.events.append((topic, data or {}))


SPEECH = (b"\x10\x27" * 1600)   # loud 100ms chunk (energy VAD: speech)
SILENCE = (b"\x00\x00" * 1600)  # quiet 100ms chunk

TAIL = int(0.5 / CHUNK_S) + 2          # silence chunks to close a phrase window
CMD_TAIL = int(1.2 / CHUNK_S) + 2      # silence chunks to close a command window


class Harness:
    def __init__(self, transcripts, chat_reply="Here is my honest answer."):
        self.clock = [1000.0]
        self.source = FakeSource(self.clock)
        self.transcriber = FakeTranscriber(transcripts)
        self.tts = FakeTTS()
        self.player = FakePlayer()
        self.bus = FakeBus()
        self.chat_calls: list[str] = []

        async def chat_runner(text: str) -> str:
            self.chat_calls.append(text)
            return chat_reply

        self.loop = AlwaysListeningLoop(
            enabled=True,
            source=self.source,
            transcriber=self.transcriber,
            tts_synth=self.tts,
            chat_runner=chat_runner,
            matcher=WakePhraseMatcher("hey dash"),
            vad=None,  # real EnergyVAD — deterministic on synthetic chunks
            event_bus=self.bus,
            clock=lambda: self.clock[0],
            player=self.player,
        )

    def say(self, *chunks: bytes) -> None:
        self.source.chunks.extend(chunks)

    def wake(self, transcript: str = "hey dash") -> None:
        """Speech + enough silence to close the phrase window."""
        self.say(SPEECH, *([SILENCE] * TAIL))
        self.transcriber.transcripts.insert(0, transcript)


async def settle(pred, timeout: float = 4.0) -> bool:
    deadline = time.monotonic() + timeout
    while not pred():
        if time.monotonic() > deadline:
            return False
        await asyncio.sleep(0.02)
    return True


# ── matcher semantics ─────────────────────────────────────────────────────


def test_matcher_word_boundaries_and_command_extraction():
    m = WakePhraseMatcher("hey dash")
    assert m.matches("Hey, DASH!")
    assert m.matches("hey dash what time is it")
    assert not m.matches("they dashed quickly")  # substring trap
    assert not m.matches("play some music")
    assert m.extract_command("Hey, DASH! What time is it?") == "what time is it"
    assert m.extract_command("hey dash") == ""


# ── lifecycle honesty ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_disabled_loop_refuses_to_start_with_real_reason():
    loop = AlwaysListeningLoop(enabled=False)
    result = await loop.start()
    assert result["ok"] is False
    assert "DASH_WAKE_LOOP_ENABLED" in result["reason"]
    assert loop.get_status()["state"] == "disabled"


# ── the full pipeline ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_wake_cycle_speaks_reply():
    h = Harness(["hey dash", "what time is it"])
    assert (await h.loop.start())["ok"] is True

    h.wake("hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)
    assert h.bus.events[0][0] == "voice.wake"
    assert h.bus.events[0][1]["transcript"] == "hey dash"

    # command window: speech, then silence past the tail
    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "what time is it")
    assert await settle(lambda: h.loop.status.command_count == 1)
    assert h.chat_calls == ["what time is it"]
    topics = [t for t, _ in h.bus.events]
    assert "voice.command" in topics and "voice.reply" in topics
    assert h.loop.status.last_reply == "Here is my honest answer."
    assert len(h.player.played) == 1

    await h.loop.stop()
    assert h.source.stopped


@pytest.mark.asyncio
async def test_inline_command_after_wake_skips_second_window():
    h = Harness(["hey dash what time is it"])
    await h.loop.start()

    h.wake("hey dash what time is it")
    assert await settle(lambda: h.loop.status.command_count == 1)
    assert h.chat_calls == ["what time is it"]
    assert h.loop.status.wake_count == 1
    await h.loop.stop()


@pytest.mark.asyncio
async def test_rejected_phrase_never_reaches_chat():
    h = Harness(["play some music"])
    await h.loop.start()

    h.wake("play some music")
    assert await settle(lambda: h.loop.status.rejected_phrase_count == 1)
    assert h.loop.status.wake_count == 0
    assert h.bus.events == []
    assert h.chat_calls == []
    await h.loop.stop()


@pytest.mark.asyncio
async def test_silence_babble_transcribes_to_nothing():
    h = Harness([""])
    await h.loop.start()

    h.wake("")
    assert await settle(lambda: len(h.transcriber.calls) == 1)
    await asyncio.sleep(0.15)
    assert h.loop.status.wake_count == 0 and h.loop.status.command_count == 0
    await h.loop.stop()


# ── echo suppression ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dash_ignores_audio_during_echo_guard():
    h = Harness(["hey dash", "speak louder"])
    await h.loop.start()

    h.wake("hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)
    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "speak louder")
    assert await settle(lambda: h.loop.status.command_count == 1)
    assert h.loop._speak_until > h.clock[0]

    # DASH "hears itself": chunks during the guard are ignored entirely
    calls_before = len(h.transcriber.calls)
    h.say(SPEECH, *([SILENCE] * 3))
    await asyncio.sleep(0.3)
    assert len(h.transcriber.calls) == calls_before
    assert h.loop.status.wake_count == 1
    await h.loop.stop()


# ── failure honesty ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transcription_failure_recorded_not_swallowed():
    h = Harness([RuntimeError("whisper exploded")])
    await h.loop.start()

    # speech + silence, and the transcriber raises on the very first call
    h.say(SPEECH, *([SILENCE] * TAIL))
    assert await settle(lambda: "transcription failed" in (h.loop.status.last_error or ""))
    # the loop survives and keeps listening
    assert h.loop.status.state == "listening"
    await h.loop.stop()


@pytest.mark.asyncio
async def test_chat_failure_recorded_and_no_tts():
    h = Harness(["hey dash", "do a thing"], chat_reply=None)

    async def failing_chat(text: str) -> str:
        raise RuntimeError("llm down")

    h.loop._chat_runner = failing_chat
    await h.loop.start()

    h.wake("hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1)
    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, "do a thing")
    assert await settle(lambda: "chat failed" in (h.loop.status.last_error or ""))
    assert h.tts.texts == [] and h.player.played == []
    await h.loop.stop()


# ── status endpoint ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wake_status_endpoint_auth_and_honest_refusal(client):
    import httpx
    from dash_backend.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        unauth = await ac.get("/api/v1/voice/wake/status")
        assert unauth.status_code == 401
        authed = await ac.get("/api/v1/voice/wake/status", headers=AUTH)
        assert authed.status_code == 200
        body = authed.json()
        assert body["state"] in {"disabled", "stopped", "listening", "error", "starting"}
        assert body["enabled"] is False  # hermetic env: loop off by default
        assert "running" in body

        refused = await ac.post("/api/v1/voice/wake/control", headers=AUTH, json={"enabled": True})
        assert refused.status_code == 409
        assert "DASH_WAKE_LOOP_ENABLED" in refused.json()["detail"]
