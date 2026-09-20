"""Tests for the companion speaking-state push (#132).

The tracker consumes the REAL #130 amplitude stream and pushes debounced
transitions — never fabricated states, never the 30 Hz firehose. A fake
clock makes the debounce windows deterministic.
"""

from __future__ import annotations

import asyncio
import time

import pytest

import dash_backend.assistant.push as push_mod
from dash_backend.assistant.voice_speaking_state import (
    VoiceSpeakingStateTracker,
    get_voice_speaking_state,
    reset_voice_speaking_state,
)


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture()
def sent(monkeypatch):
    out: list[dict] = []
    monkeypatch.setattr(
        push_mod, "push_assistant_event", lambda uid, payload: out.append(payload)
    )
    yield out


@pytest.fixture(autouse=True)
def _reset():
    reset_voice_speaking_state()
    yield
    reset_voice_speaking_state()


def _live(tracker: VoiceSpeakingStateTracker, clock: _Clock, ms: int, step_ms: int = 33):
    """Feed `ms` of continuous live audio in `step_ms` steps."""
    for _ in range(0, ms, step_ms):
        clock.t += step_ms / 1000.0
        tracker.on_amplitude(0.6, True)


def _quiet(tracker: VoiceSpeakingStateTracker, clock: _Clock, ms: int, step_ms: int = 33):
    for _ in range(0, ms, step_ms):
        clock.t += step_ms / 1000.0
        tracker.on_amplitude(0.0, False)


def test_short_blip_never_becomes_speaking(sent):
    clock = _Clock()
    tr = VoiceSpeakingStateTracker(clock=clock)
    _live(tr, clock, 150)   # under the 300 ms confirm window
    _quiet(tr, clock, 800)  # dies unconfirmed
    assert sent == []
    assert tr.speaking is False


def test_sustained_speech_pushes_speaking_once(sent):
    clock = _Clock()
    tr = VoiceSpeakingStateTracker(clock=clock)
    _live(tr, clock, 400)
    before = len([p for p in sent if p["speaking"] is True])
    _live(tr, clock, 2000)  # many more samples — must stay ONE transition
    speaking_pushes = [p for p in sent if p["speaking"] is True]
    assert before == 1 and len(speaking_pushes) == 1
    assert sent[0]["type"] == "voice.speaking"
    assert sent[0]["source"] == "playback"
    assert tr.speaking is True


def test_silence_pushes_stopped_once(sent):
    clock = _Clock()
    tr = VoiceSpeakingStateTracker(clock=clock)
    _live(tr, clock, 400)
    _quiet(tr, clock, 800)
    stopped = [p for p in sent if p["speaking"] is False]
    assert len(stopped) == 1
    assert tr.speaking is False


def test_sentence_gap_does_not_flap(sent):
    """A <700 ms gap between sentences stays 'speaking' (one transition)."""
    clock = _Clock()
    tr = VoiceSpeakingStateTracker(clock=clock)
    _live(tr, clock, 400)            # sentence 1 confirmed speaking
    _quiet(tr, clock, 400)           # inter-sentence synth gap
    _live(tr, clock, 300)            # sentence 2
    assert [p["speaking"] for p in sent] == [True]
    _quiet(tr, clock, 800)           # real end
    assert [p["speaking"] for p in sent] == [True, False]


def test_slow_synthesis_gap_reports_truth(sent):
    """A gap LONGER than the window honestly reports stopped, then the next
    sentence reports speaking again — truth over smoothness."""
    clock = _Clock()
    tr = VoiceSpeakingStateTracker(clock=clock)
    _live(tr, clock, 400)
    _quiet(tr, clock, 900)           # slow synth: exceeds the window
    _live(tr, clock, 400)
    assert [p["speaking"] for p in sent] == [True, False, True]


def test_explicit_stop_signal_ends_cycle(sent):
    clock = _Clock()
    tr = VoiceSpeakingStateTracker(clock=clock)
    _live(tr, clock, 400)
    tr.on_amplitude(0.0, False)      # the #130 explicit stop signal
    assert tr.speaking is True       # not yet confirmed stopped
    clock.t += 0.8
    tr.on_amplitude(0.0, False)      # next sample flushes past the window
    assert [p["speaking"] for p in sent] == [True, False]


@pytest.mark.asyncio
async def test_stop_pushes_without_further_samples(sent):
    """Stream ended right after speech: the deferred flush still delivers
    the stopped transition (no next on_amplitude call needed)."""
    clock = _Clock()
    tr = VoiceSpeakingStateTracker(clock=clock)
    _live(tr, clock, 400)
    tr.on_amplitude(0.0, False)
    clock.t += 0.8
    await asyncio.sleep(0.0)         # let the deferred task observe the clock
    await asyncio.sleep(0.8)         # real sleep past the deferred flush
    assert [p["speaking"] for p in sent] == [True, False]


def test_push_failure_is_isolated(sent, monkeypatch):
    def _boom(uid, payload):
        raise RuntimeError("channel down")

    monkeypatch.setattr(push_mod, "push_assistant_event", _boom)
    clock = _Clock()
    tr = VoiceSpeakingStateTracker(clock=clock)
    _live(tr, clock, 400)            # must not raise
    assert tr.speaking is True       # state machine still correct


def test_singleton_lifecycle():
    a = get_voice_speaking_state()
    b = get_voice_speaking_state()
    assert a is b
    reset_voice_speaking_state()
    assert get_voice_speaking_state() is not a
