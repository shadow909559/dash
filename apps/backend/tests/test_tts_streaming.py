"""Sentence-streaming TTS (decisions.md #102, spec #8/#45).

Hermetic: fake synthesizer/player with an injectable clock. Proves:
- first audio is ready after the FIRST sentence's synthesis, not the
  full reply's (the measurable TTFA win)
- sentences play in order with bounded look-ahead
- per-sentence synth failures are recorded, never hidden
- a play-cancellation (barge-in) propagates as CancelledError with
  result.cancelled=True semantics at the caller
"""
from __future__ import annotations

import asyncio

import pytest

from dash_backend.assistant.tts_streaming import speak_streamed, split_sentences
from dash_backend.voice_system.always_listening import pcm_to_wav


def _wav(seconds: float = 0.01) -> bytes:
    return pcm_to_wav(b"\x00\x01" * int(16000 * seconds))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class ScriptedSynth:
    """Async synth: each sentence takes `cost` clock-seconds."""

    def __init__(self, costs, fail_idx=()):
        self.costs = list(costs)
        self.fail_idx = set(fail_idx)
        self.asked: list[str] = []

    async def __call__(self, text: str) -> bytes:
        self.asked.append(text)
        idx = len(self.asked) - 1
        clock.t += self.costs[idx]
        if idx in self.fail_idx:
            raise RuntimeError("synth boom")
        return _wav()


class ScriptedPlayer:
    def __init__(self, cost=0.2):
        self.cost = cost
        self.played: list[bytes] = []

    async def __call__(self, audio: bytes) -> None:
        clock.t += self.cost
        self.played.append(audio)


clock = Clock()


@pytest.fixture(autouse=True)
def _reset_clock():
    clock.t = 1000.0
    yield


class TestSplitSentences:
    def test_basic_split(self):
        assert split_sentences("Hello there. How are you? Fine!") == [
            "Hello there.", "How are you?", "Fine!"]

    def test_empty_returns_empty(self):
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_abbreviation_not_split(self):
        out = split_sentences("Meet Dr. Adams at 3. She will brief you.")
        assert any("Dr. Adams" in s for s in out)

    def test_decimal_not_split(self):
        out = split_sentences("Version 1.5 ships now. Please test it.")
        assert any("1.5 ships now" in s for s in out)

    def test_no_terminator_single_chunk(self):
        assert split_sentences("just one fragment") == ["just one fragment"]

    def test_tiny_fragment_merges_forward(self):
        out = split_sentences("Go! Ok then we continue.")
        assert out[0].startswith("Go!")


class TestSpeakStreamed:
    @pytest.mark.asyncio
    async def test_first_audio_not_delayed_by_later_sentences(self):
        """The core latency proof: first audio goes out after sentence 1's
        synthesis alone. Later sentences' synthesis must still be PENDING
        when playback starts — with a real (I/O-yielding) synth they run
        concurrently, never serially ahead of first audio."""

        class GatedSynth:
            """Sentence 0 costs 0.5 clock-s. Every later sentence blocks
            until released — if first audio waited on them, TTFA would
            blow past 0.5s and the test would hang/fail."""

            def __init__(self):
                self.asked: list[str] = []
                self.release = asyncio.Event()
                self.clock_at_release = None

            async def __call__(self, text: str) -> bytes:
                self.asked.append(text)
                if len(self.asked) == 1:
                    clock.t += 0.5
                    return _wav()
                await self.release.wait()
                clock.t += 3.0
                return _wav()

        class FirstPlayReleases:
            def __init__(self, synth: GatedSynth):
                self.synth = synth
                self.played = 0
                self.clock_at_first_play = None

            async def __call__(self, audio: bytes) -> None:
                self.played += 1
                if self.played == 1:
                    self.clock_at_first_play = clock.t
                    self.synth.release.set()
                await asyncio.sleep(0)

        synth = GatedSynth()
        player = FirstPlayReleases(synth)
        result = await speak_streamed(
            "Short first. Second sentence here. Third one follows.",
            synth, player, clock=clock)
        assert result["spoken"] == 3
        assert result["failed"] == 0
        assert result["ttfa_ms"] == 500.0
        # first playback started with ONLY sentence-0 synth work done
        assert player.clock_at_first_play == 1000.5
        assert len(synth.asked) == 3  # all sentences were requested (look-ahead)

    @pytest.mark.asyncio
    async def test_order_preserved(self):
        synth = ScriptedSynth(costs=[0.1, 0.1, 0.1])
        player = ScriptedPlayer()
        sentences = ["One. Two. Three."]
        await speak_streamed("One. Two. Three.", synth, player, clock=clock)
        assert len(player.played) == 3

    @pytest.mark.asyncio
    async def test_per_sentence_failure_recorded_not_fatal(self):
        synth = ScriptedSynth(costs=[0.1, 0.1, 0.1], fail_idx={1})
        player = ScriptedPlayer()
        result = await speak_streamed("A. B. C.", synth, player, clock=clock)
        assert result["spoken"] == 2
        assert result["failed"] == 1
        assert result["ttfa_ms"] is not None

    @pytest.mark.asyncio
    async def test_playback_cancellation_propagates(self):
        """Barge-in: the caller's cancellation reaches the synth tasks
        and surfaces as CancelledError — the reply stops."""

        class CancellingPlayer:
            def __init__(self):
                self.started = False

            async def __call__(self, audio: bytes) -> None:
                self.started = True
                raise asyncio.CancelledError()

        synth = ScriptedSynth(costs=[0.1, 0.1])
        player = CancellingPlayer()
        with pytest.raises(asyncio.CancelledError):
            await speak_streamed("A. B.", synth, player, clock=clock)
        assert player.started

    @pytest.mark.asyncio
    async def test_empty_text_noop(self):
        synth = ScriptedSynth(costs=[])
        player = ScriptedPlayer()
        result = await speak_streamed("", synth, player, clock=clock)
        assert result["sentences"] == 0 and result["spoken"] == 0
        assert player.played == []
