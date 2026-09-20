"""Playback-amplitude tests (decisions.md #130) — the orb pulses with
DASH's REAL speech, measured from the actual PCM, never simulated.

Pins:
- WAV parsing is honest: PCM parses, junk returns None (measurement skips).
- Amplitude math: silence is 0.0, a loud sine lands in a usable range.
- The monitor maps real playback time to the chunk being heard.
- ``_play_wav`` emits live ``voice.amplitude`` while playing and an explicit
  {level: 0, speaking: False} stop signal afterwards — through the same
  assistant-push channel as presence.update.
- Playback itself is never gated on measurement (player still runs when the
  monitor fails), and non-PCM payloads simply skip monitoring.
"""

from __future__ import annotations

import asyncio
import math
import struct
import time

import pytest

from dash_backend.voice_system.always_listening import AlwaysListeningLoop
from dash_backend.voice_system.playback_amplitude import (
    PlaybackAmplitudeMonitor,
    parse_wav_pcm,
    pcm_amplitude,
    reset_playback_amplitude,
)


def _make_wav(rate: int = 22050, seconds: float = 0.5, amp: int = 20000) -> bytes:
    """A real 16-bit mono PCM WAV containing a 440 Hz sine."""
    n = int(rate * seconds)
    frames = b"".join(
        struct.pack("<h", int(amp * math.sin(2 * math.pi * 440 * i / rate)))
        for i in range(n)
    )
    data = b"data" + struct.pack("<I", len(frames)) + frames
    fmt = b"fmt " + struct.pack("<I", 16) + struct.pack(
        "<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    body = fmt + data
    return b"RIFF" + struct.pack("<I", len(body)) + b"WAVE" + body


# ── parsing + amplitude math ─────────────────────────────────────────


def test_parse_wav_pcm_accepts_real_wav():
    wav = _make_wav()
    parsed = parse_wav_pcm(wav)
    assert parsed is not None
    assert parsed["format"] == 1
    assert parsed["bits"] == 16
    assert parsed["channels"] == 1
    assert parsed["sample_rate"] == 22050
    assert len(parsed["data"]) == 22050  # 0.5 s * 22050 * 2 bytes


def test_parse_wav_pcm_rejects_non_pcm_honestly():
    assert parse_wav_pcm(b"") is None
    assert parse_wav_pcm(b"not a wav") is None
    assert parse_wav_pcm(b"RIFF" + struct.pack("<I", 4) + b"WAVE" + b"junk") is None


def test_pcm_amplitude_silence_vs_loud():
    assert pcm_amplitude(bytes(22050), 16, 1) == 0.0  # 1 s of silence
    wav = _make_wav()
    parsed = parse_wav_pcm(wav)
    loud = pcm_amplitude(parsed["data"][:2205], 16, 1)  # 0.1 s chunk
    assert 0.2 < loud <= 1.0


# ── monitor time mapping ─────────────────────────────────────────────


def test_monitor_maps_playback_time_to_chunks():
    m = PlaybackAmplitudeMonitor()
    t0 = time.monotonic()
    assert m.begin(_make_wav(seconds=0.5)) is True
    assert m.active
    assert m.tick(t0 + 0.0) > 0.1  # loud sine at the start
    assert m.tick(t0 + 0.1) > 0.1
    assert m.tick(t0 + 10.0) == 0.0  # long past the end → silent
    m.end()
    assert not m.active
    assert m.tick(t0 + 0.0) == 0.0


def test_monitor_skips_non_pcm():
    m = PlaybackAmplitudeMonitor()
    assert m.begin(b"ogg-data-not-pcm") is False
    assert not m.active
    assert m.tick() == 0.0


# ── emission contract ────────────────────────────────────────────────


def test_emit_pushes_amplitude_and_stop_signal(monkeypatch):
    import dash_backend.assistant.push as push_mod

    sent: list[dict] = []
    monkeypatch.setattr(
        push_mod, "push_assistant_event",
        lambda uid, payload: sent.append(payload),
    )

    m = PlaybackAmplitudeMonitor()
    m.begin(_make_wav())
    for _ in range(5):
        m.emit(m.tick(time.monotonic()), True)
    assert sent, "live levels must be pushed"
    assert sent[0]["type"] == "voice.amplitude"
    assert 0.0 <= sent[0]["level"] <= 1.0
    assert sent[0]["speaking"] is True

    m.emit(0.0, False)  # explicit stop signal
    assert sent[-1] == {"type": "voice.amplitude", "level": 0.0, "speaking": False}


def test_emit_suppresses_value_no_change_spam(monkeypatch):
    import dash_backend.assistant.push as push_mod

    sent: list[dict] = []
    monkeypatch.setattr(
        push_mod, "push_assistant_event",
        lambda uid, payload: sent.append(payload),
    )

    m = PlaybackAmplitudeMonitor()
    m._last_emit_t = 0.0
    for _ in range(10):
        m.emit(0.5, True)  # identical value, rapid fire
    # First one passes, identical rapid repeats are suppressed.
    levels = [(p["level"], p["speaking"]) for p in sent]
    assert levels.count((0.5, True)) <= 2


def test_emit_drops_speaking_levels_when_not_active(monkeypatch):
    import dash_backend.assistant.push as push_mod

    sent: list[dict] = []
    monkeypatch.setattr(
        push_mod, "push_assistant_event",
        lambda uid, payload: sent.append(payload),
    )

    m = PlaybackAmplitudeMonitor()  # never begun
    m.emit(0.7, True)  # fabricating a level with no playback is refused
    assert sent == []


# ── wiring: the wake loop's real playback path ───────────────────────


@pytest.mark.asyncio
async def test_play_wav_emits_live_amplitude(monkeypatch):
    reset_playback_amplitude()
    import dash_backend.assistant.push as push_mod

    sent: list[dict] = []
    monkeypatch.setattr(
        push_mod, "push_assistant_event",
        lambda uid, payload: sent.append(payload),
    )

    played: list[bytes] = []

    async def fake_player(audio: bytes) -> None:
        played.append(audio)
        await asyncio.sleep(0.15)  # playback takes real time

    loop = AlwaysListeningLoop(enabled=True, player=fake_player)
    wav = _make_wav(seconds=0.5)
    await loop._play_wav(wav)

    assert played == [wav], "playback must complete regardless of monitoring"
    types = [p["type"] for p in sent]
    assert "voice.amplitude" in types
    assert sent[-1]["speaking"] is False and sent[-1]["level"] == 0.0


@pytest.mark.asyncio
async def test_play_wav_survives_monitor_failure(monkeypatch):
    reset_playback_amplitude()
    import dash_backend.voice_system.playback_amplitude as pa_mod

    def _boom():
        raise RuntimeError("monitor unavailable")

    monkeypatch.setattr(pa_mod, "get_playback_amplitude", _boom)

    played: list[bytes] = []

    async def fake_player(audio: bytes) -> None:
        played.append(audio)

    loop = AlwaysListeningLoop(enabled=True, player=fake_player)
    await loop._play_wav(_make_wav())  # must not raise
    assert len(played) == 1, "playback is never gated on measurement"
