"""Push "DASH is speaking" state transitions (#132).

The #130 playback-amplitude stream tells the DESKTOP orb when DASH speaks
(30 Hz live levels). The Android companion has no orb wired to ws events
yet — but it does not need the stream either. What the phone wants is the
STATE: "DASH is talking right now" / "DASH stopped", pushed as transitions
over the same assistant-push channel as presence.update, so the companion
(WebSocketManager, same /ws endpoint, same registration) can reflect it.

Design:

- Consumes the REAL amplitude stream (levels from actual PCM playback).
  Nothing here fabricates a state: no stream → no transitions.
- DEBOUNCED transitions: streamed TTS plays sentence-by-sentence, so the
  raw stream flaps (level>0, level=0, level>0, ...). A 'speaking' push is
  confirmed after MIN_SPEAKING_MS of continuous levels; a 'stopped' push
  after MIN_SILENCE_MS without any. A new level inside the silence window
  cancels the pending stop (the inter-sentence gap case).
- Transitions only — never a 30 Hz firehose to the phone.
- Payload carries no content: {"type": "voice.speaking", "speaking": bool,
  "source": "playback"}. Same no-secrets contract as every other push.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

MIN_SPEAKING_MS = 300   # confirm 'speaking' after this much live audio
MIN_SILENCE_MS = 700    # confirm 'stopped' after this much silence


class VoiceSpeakingStateTracker:
    """Debounced two-state machine over the #130 amplitude stream."""

    def __init__(
        self,
        *,
        min_speaking_ms: int = MIN_SPEAKING_MS,
        min_silence_ms: int = MIN_SILENCE_MS,
        clock=time.monotonic,
    ) -> None:
        self._min_speaking_s = min_speaking_ms / 1000.0
        self._min_silence_s = min_silence_ms / 1000.0
        self._clock = clock
        self._speaking = False
        self._first_live_at: Optional[float] = None   # pending 'speaking'
        self._last_live_at: Optional[float] = None    # pending 'stopped'
        self._flush_handle: Optional[asyncio.TimerHandle] = None

    # ── input ────────────────────────────────────────────────────

    def on_amplitude(self, level: float, speaking: bool) -> None:
        """Feed one amplitude-stream sample (level 0..1, speaking flag).

        Call from the playback ticker (every ~33 ms). Flushes any pending
        transition first, then updates the debounce bookkeeping.
        """
        now = self._clock()
        self._flush(now)
        if speaking and level > 0.0:
            self._last_live_at = now
            if not self._speaking and self._first_live_at is None:
                self._first_live_at = now
        elif not speaking:
            # explicit stop signal (#130 stop) — debounce to 'stopped'
            if self._speaking and self._last_live_at is None:
                self._last_live_at = now
            self._first_live_at = None
        self._schedule_flush()

    # ── transition resolution ────────────────────────────────────

    def _flush(self, now: float) -> None:
        # Pending 'speaking': enough live audio has accumulated AND it is
        # still flowing — a blip followed by silence dies unconfirmed.
        if (
            not self._speaking
            and self._first_live_at is not None
            and self._last_live_at is not None
            and now - self._first_live_at >= self._min_speaking_s
        ):
            if now - self._last_live_at > self._min_speaking_s:
                self._first_live_at = None  # blip died mid-debounce
            else:
                self._speaking = True
                self._first_live_at = None
                self._push(True)
        # Pending 'stopped': enough silence since the last live level.
        if (
            self._speaking
            and self._last_live_at is not None
            and now - self._last_live_at >= self._min_silence_s
        ):
            self._speaking = False
            self._last_live_at = None
            self._push(False)

    def _schedule_flush(self) -> None:
        """Deferred flush so the final 'stopped' fires even when the
        stream ends (no further on_amplitude calls arrive).

        A loop timer, not a Task: timers die silently with their loop,
        whereas a pending Task leaked 'Task was destroyed but it is
        pending' at interpreter shutdown when nothing ever flushed it.
        """
        if self._flush_handle is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # sync context: the next on_amplitude flushes
        self._flush_handle = loop.call_later(
            self._min_silence_s + 0.05, self._on_flush_timer
        )

    def _on_flush_timer(self) -> None:
        self._flush_handle = None
        self._flush(self._clock())
        if self._speaking:
            # still live — keep ticking so a stop is eventually pushed
            self._schedule_flush()

    # ── delivery ─────────────────────────────────────────────────

    def _push(self, speaking: bool) -> None:
        payload: dict[str, Any] = {
            "type": "voice.speaking",
            "speaking": speaking,
            "source": "playback",
        }
        try:
            from dash_backend.assistant.push import push_assistant_event
            push_assistant_event(None, payload)
        except Exception:
            logger.debug("voice.speaking push failed", exc_info=True)

    # ── introspection ────────────────────────────────────────────

    @property
    def speaking(self) -> bool:
        return self._speaking

    def shutdown(self) -> None:
        if self._flush_handle is not None:
            self._flush_handle.cancel()
        self._flush_handle = None


_tracker: Optional[VoiceSpeakingStateTracker] = None


def get_voice_speaking_state() -> VoiceSpeakingStateTracker:
    global _tracker
    if _tracker is None:
        _tracker = VoiceSpeakingStateTracker()
    return _tracker


def reset_voice_speaking_state() -> None:
    global _tracker
    if _tracker is not None:
        _tracker.shutdown()
    _tracker = None
