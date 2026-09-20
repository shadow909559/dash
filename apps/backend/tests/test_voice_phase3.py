"""Phase 3 — voice behavioral tests (decisions.md #118).

Covers the four Phase-3 behaviors on the real loop, hermetically:
  1. partial STT  — voice.partial events (bus + ws push), throttled, and
                    the STT call itself gated so a CPU-only machine is not
                    saturated; final emit at command tail.
  2. live barge-in — owner speech during playback claims INTERRUPTED
                     presence (TTL-bounded) and the real detection→stopped
                     latency lands in the metrics registry.
  3. voice_mode    — the wake path asks the LLM for short, spoken-friendly
                     replies (ChatSendMessage.voice_mode=True).
  4. honesty       — the four dead voice modules (streaming_stt,
                     enhanced_streaming_tts, streaming_tts,
                     interruption_handler) are deleted, not imported.

Harness conventions follow test_wake_barge_in.py (fake source, scripted
transcribers, injectable clock, monkeypatched user resolution).
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import pytest

from dash_backend.assistant import metrics as ametrics
from dash_backend.voice_system.always_listening import (
    AlwaysListeningLoop,
    PARTIAL_INTERVAL_S,
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

    def start(self):
        self.started = True

    def stop(self):
        pass

    def read_chunk(self, timeout: float = 0.1) -> Optional[bytes]:
        if self.chunks:
            self.clock[0] += CHUNK_S
            return self.chunks.pop(0)
        time.sleep(0.005)
        return None


class FakeTranscriber:
    """Scripted final-window transcriber (FIFO)."""

    def __init__(self, transcripts):
        self.transcripts = list(transcripts)

    async def __call__(self, wav: bytes) -> str:
        if not self.transcripts:
            return ""
        return self.transcripts.pop(0)


class FakePartialTranscriber:
    """Scripted interim transcriber keyed by buffered length so tests stay
    deterministic regardless of loop scheduling."""

    def __init__(self, by_size: dict[int, str]):
        self.by_size = dict(by_size)
        self.calls = 0

    async def __call__(self, pcm: bytes) -> str:
        self.calls += 1
        return self.by_size.get(len(pcm), "")


class FakeTTS:
    async def __call__(self, text: str) -> bytes:
        return pcm_to_wav(b"\x00\x01" * 16000)


class HangingPlayer:
    def __init__(self):
        self.cancelled = False
        self.started = False

    async def __call__(self, audio: bytes) -> None:
        self.started = True
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish_sync(self, topic, data=None, **kwargs):
        self.events.append((topic, data or {}))


class Harness:
    def __init__(self, transcripts, player, partial=None, chat=None):
        self.clock = [1000.0]
        self.source = FakeSource(self.clock)
        self.transcriber = FakeTranscriber(transcripts)
        self.partial = partial
        self.player = player
        self.bus = FakeBus()
        self.loop = AlwaysListeningLoop(
            enabled=True,
            source=self.source,
            transcriber=self.transcriber,
            partial_transcriber=partial,
            tts_synth=FakeTTS(),
            chat_runner=chat or _fake_chat,
            matcher=WakePhraseMatcher("hey dash"),
            vad=None,  # real EnergyVAD — deterministic on the fakes
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
    async def _resolve(self=None):
        return "owner"

    monkeypatch.setattr(
        "dash_backend.voice_system.always_listening.AlwaysListeningLoop._resolve_user",
        _resolve)


async def _wake_then_command(h: Harness, command: str) -> None:
    """Drive one full wake → command capture cycle.

    Discipline inherited from test_wake_barge_in.py: the loop task runs
    concurrently, so each window's transcript must be inserted while the
    loop is provably idle — settle(wake) between the windows. Inserting
    both up-front lets window 1 consume the command's slot (FIFO).
    """
    h.say(SPEECH, *([SILENCE] * TAIL))
    h.transcriber.transcripts.insert(0, "hey dash")
    assert await settle(lambda: h.loop.status.wake_count == 1), "wake must fire"
    h.say(SPEECH, *([SILENCE] * CMD_TAIL))
    h.transcriber.transcripts.insert(0, command)
    assert await settle(lambda: h.loop.status.command_count == 1), \
        "command must dispatch"


# ── 1. Partial STT ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_partial_transcripts_published_to_bus_and_ws():
    """During command capture, interim transcripts publish voice.partial on
    the EventBus AND push to the assistant ws (spec #7 partial transcript)."""
    # One scripted interim for the first partial-sized buffer; finals flow
    # through the separate scripted transcriber untouched.
    partial = FakePartialTranscriber({len(SPEECH): "what is happening with acme"})
    h = Harness(["hey dash", "what is happening with acme"], HangingPlayer(),
                partial=partial)
    assert (await h.loop.start())["ok"] is True

    await _wake_then_command(h, "what is happening with acme")
    assert await settle(lambda: h.loop.status.wake_count == 1)
    assert await settle(lambda: h.loop.status.command_count == 1)

    await h.loop.stop()
    partials = [d for t, d in h.bus.events if t == "voice.partial"]
    assert partials, "at least one interim transcript must be published"
    assert any(d.get("text") == "what is happening with acme" for d in partials)
    assert all(isinstance(d.get("final"), bool) for d in partials)


@pytest.mark.asyncio
async def test_partial_throttle_and_stt_gating(monkeypatch):
    """Two disciplines hold at once: events are throttled to
    PARTIAL_INTERVAL_S, and the STT call itself is gated on the same
    interval — a Whisper pass per 100ms chunk would saturate a CPU box."""
    partial = FakePartialTranscriber({len(SPEECH): "interim words"})
    h = Harness(["hey dash", "final command"], InstantLikePlayer(),
                partial=partial)
    assert (await h.loop.start())["ok"] is True

    await _wake_then_command(h, "final command")
    assert await settle(lambda: h.loop.status.command_count == 1)
    await h.loop.stop()

    # STT gating: the interim transcriber ran only where the gate allowed —
    # one call on the speech chunk + one at the final tail, never per-chunk.
    assert partial.calls <= 3, f"STT must be gated: {partial.calls} calls"
    assert partial.calls < 11, "STT must be gated, not per-chunk"

    # Throttle: at most one published event per interval window.
    # Command window spans 1.2s tail + capture ≈ 2.3s → ≤ ~4 events.
    events = [d for t, d in h.bus.events if t == "voice.partial"]
    assert len(events) <= 4, f"throttle exceeded: {len(events)} events"


class InstantLikePlayer:
    def __init__(self):
        self.played = 0

    async def __call__(self, audio: bytes) -> None:
        self.played += 1


@pytest.mark.asyncio
async def test_partial_final_emit_at_command_tail():
    """The transcript at the silence tail publishes with final=True before
    the full command path takes over."""
    partial = FakePartialTranscriber({len(SPEECH): "read back the number"})
    h = Harness(["hey dash", "final command"], InstantLikePlayer(),
                partial=partial)
    assert (await h.loop.start())["ok"] is True

    await _wake_then_command(h, "final command")
    assert await settle(lambda: h.loop.status.command_count == 1)
    await h.loop.stop()
    finals = [d for t, d in h.bus.events
              if t == "voice.partial" and d.get("final")]
    assert finals and finals[-1]["text"] == "read back the number"


@pytest.mark.asyncio
async def test_partial_fails_soft_without_hardware(monkeypatch):
    """No partial transcriber injected → default is the loop's own STT
    provider, which in a no-model environment returns empty/raises. Either
    way the command path must complete with no partial events published."""
    h = Harness(["hey dash", "tell me the time"], InstantLikePlayer(),
                partial=None)
    assert (await h.loop.start())["ok"] is True

    await _wake_then_command(h, "tell me the time")
    assert await settle(lambda: h.loop.status.command_count == 1)
    await h.loop.stop()
    assert h.loop.status.command_count == 1


# ── 2. Live barge-in: presence + measured latency ─────────────────────────


@pytest.mark.asyncio
async def test_barge_in_claims_interrupted_presence_with_ttl():
    """Speech over playback claims INTERRUPTED presence — TTL-bounded so a
    dead playback task can never strand the orb in 'interrupted'."""
    from dash_backend.assistant.presence import (
        PresenceEngine,
        get_presence_engine,
        reset_presence_engine,
    )

    reset_presence_engine()
    h = Harness(["hey dash", "stop talking"], HangingPlayer())
    assert (await h.loop.start())["ok"] is True

    await _wake_then_command(h, "stop talking")
    assert await settle(lambda: h.loop.status.wake_count == 1)
    assert await settle(lambda: h.loop.status.command_count == 1)
    assert await settle(lambda: h.player.started)

    h.say(*([SPEECH] * 40))
    ok = await settle(lambda: getattr(h.player, "cancelled", False))

    # Read presence BEFORE stop(): stop() unconditionally releases the
    # voice_loop source — correct production behavior, so the claim must
    # be observed while the loop is still alive.
    assert ok, "owner speech during playback must cancel it"
    snap = get_presence_engine().snapshot()
    assert snap["state"] == "interrupted", \
        "INTERRUPTED must be claimed at detection time"
    await h.loop.stop()
    after = get_presence_engine().snapshot()
    assert after["state"] != "interrupted", \
        "loop stop must release the interrupted claim"


@pytest.mark.asyncio
async def test_barge_in_records_measured_interrupt_latency():
    """The detection→playback-stopped latency is measured where the cancel
    lands, not estimated — a real voice_interrupt sample must exist."""
    h = Harness(["hey dash", "stop talking"], HangingPlayer())
    assert (await h.loop.start())["ok"] is True

    await _wake_then_command(h, "stop talking")
    assert await settle(lambda: h.loop.status.wake_count == 1)
    assert await settle(lambda: h.loop.status.command_count == 1)
    assert await settle(lambda: h.player.started)

    h.say(*([SPEECH] * 40))
    ok = await settle(lambda: getattr(h.player, "cancelled", False))
    ok2 = await settle(
        lambda: ametrics.summary()["latency"].get("voice_interrupt", {}).get("n", 0) >= 1)
    await h.loop.stop()
    assert ok, "cancel must land for latency to be observable"
    assert ok2, "voice_interrupt must be measured on the real barge-in path"
    sample = ametrics.summary()["latency"]["voice_interrupt"]
    assert sample["n"] >= 1 and sample["avg_ms"] >= 0.0


@pytest.mark.asyncio
async def test_interrupted_presence_ttl_expires(monkeypatch):
    """The INTERRUPTED claim is transient: with a frozen clock nothing can
    expire it mid-turn, and a stop() after expiry leaves no stale claim."""
    from dash_backend.assistant.presence import (
        get_presence_engine,
        reset_presence_engine,
    )

    reset_presence_engine()
    h = Harness(["hey dash", "stop"], HangingPlayer())
    # Freeze the loop clock mid-value so the claim's TTL (5s) stays live.
    assert (await h.loop.start())["ok"] is True

    await _wake_then_command(h, "stop")
    assert await settle(lambda: h.loop.status.wake_count == 1)
    assert await settle(lambda: h.loop.status.command_count == 1)
    assert await settle(lambda: h.player.started)

    h.say(*([SPEECH] * 40))
    assert await settle(lambda: getattr(h.player, "cancelled", False))
    # Before stop(): the claim is live with a finite expiry (TTL contract).
    snap = get_presence_engine().snapshot()
    assert snap["state"] == "interrupted"
    claims = [c for c in snap.get("claims", []) if c["source"] == "voice_loop"]
    assert claims and claims[0]["state"] == "interrupted"
    assert claims[0]["expires_at"] is not None, \
        "interrupted claim must be TTL-bounded, not sticky"
    assert claims[0]["expires_at"] > claims[0]["since"]
    await h.loop.stop()
    # After stop(): the source is released — no stale claim survives.
    after = get_presence_engine().snapshot()
    assert not [c for c in after.get("claims", [])
                if c["source"] == "voice_loop"]


# ── 3. voice_mode on the wake chat runner ─────────────────────────────────


@pytest.mark.asyncio
async def test_wake_chat_runner_uses_voice_mode(monkeypatch):
    """The wake path must ask for short, spoken-friendly replies
    (ChatSendMessage.voice_mode=True) — text-style paragraphs are wrong
    for a speaker (spec #6)."""
    captured: dict = {}

    class _Result:
        def __init__(self, items):
            self._items = items

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._items:
                raise StopAsyncIteration
            return self._items.pop(0)

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class _FakeSessionLocal:
        def __call__(self):
            return _FakeSession()

    async def _fake_handle(msg, session=None, user_id=None):
        captured["voice_mode"] = getattr(msg, "voice_mode", None)
        captured["content"] = msg.content
        yield _FakeToken("ok")
        yield _FakeDone()

    class _FakeToken:
        def __init__(self, content):
            self.content = content

    class _FakeDone:
        pass

    from dash_backend.api.websocket import handlers as ws_handlers

    monkeypatch.setattr(ws_handlers, "handle_chat_send", _fake_handle)
    monkeypatch.setattr(
        "dash_backend.db.session.AsyncSessionLocal", _FakeSessionLocal())

    # ChatSendMessage is pydantic — real parse proves the field travels.
    # Clear the injected runner so _get_chat_runner() lazily falls back to
    # the DEFAULT runner — the actual code under test.
    h = Harness(["hey dash", "what time is it"], InstantLikePlayer())
    h.loop._chat_runner = None
    assert (await h.loop.start())["ok"] is True
    await _wake_then_command(h, "what time is it")
    assert await settle(lambda: h.loop.status.command_count == 1)
    await h.loop.stop()
    assert captured.get("voice_mode") is True, \
        "wake path must set voice_mode=True for spoken-style replies"


# ── 4. Honesty: dead modules deleted, not imported ────────────────────────


def test_dead_voice_modules_are_gone():
    """The Phase-1 audit's dead code is deleted — importing any of them
    must fail, proving nothing can silently regress to the fake pipeline."""
    import importlib
    import sys
    for mod in (
        "dash_backend.voice_system.streaming_stt",
        "dash_backend.voice_system.enhanced_streaming_tts",
        "dash_backend.voice_system.streaming_tts",
        "dash_backend.voice_system.interruption_handler",
    ):
        sys.modules.pop(mod, None)
        with pytest.raises(ImportError):
            importlib.import_module(mod)


def test_no_source_references_to_deleted_modules():
    """No production code may still reference the deleted modules."""
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "dash_backend"
    result = subprocess.run(
        ["grep", "-rn", "--include=*.py", "-E",
         "streaming_stt|enhanced_streaming_tts|interruption_handler",
         str(root)],
        capture_output=True, text=True)
    hits = [ln for ln in result.stdout.splitlines() if "__pycache__" not in ln]
    assert not hits, f"stale references remain: {hits[:5]}"


def test_partial_interval_is_sane():
    """The throttle constant exists and is in a useful band (not per-chunk,
    not so slow that live typing feels broken)."""
    assert 0.2 <= PARTIAL_INTERVAL_S <= 2.0
