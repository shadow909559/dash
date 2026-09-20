"""Real playback-amplitude measurement for DASH's own speech (#130).

While DASH speaks through the SERVER's speakers (the wake loop's Piper
playback via winsound/paplay/afplay), the orb should pulse with that
speech the same way it pulses with the owner's mic. This module measures
the actual PCM being played — no simulation:

- ``parse_wav_pcm`` extracts the PCM payload from the WAV bytes DASH is
  about to play (None for non-PCM data — measurement honestly skips).
- ``pcm_amplitude`` computes rough perceived loudness (RMS, gamma-corrected)
  of one chunk of interleaved PCM.
- ``PlaybackAmplitudeMonitor`` maps wall-clock playback position to the
  matching chunk, so a ticker can emit levels synchronized with what the
  speaker is actually producing right now.
- ``emit`` pushes ``{"type": "voice.amplitude", "level": 0..1,
  "speaking": bool}`` through the assistant ws channel (same shape and
  delivery contract as presence.update; best-effort, drops when no client).

The desktop's own ``voice.tts_ready`` playback (browser Audio element) is
measured client-side with a WebAudio analyser tap in ``lib/ws.ts`` — that
audio never passes through this server, so faking it here would be
dishonest. Both paths produce real measurements of real speakers.
"""

from __future__ import annotations

import math
import struct
import time
from typing import Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Emission cadence: fast enough to look live, slow enough to not flood ws.
_EMIT_INTERVAL_S = 0.033
_CHUNK_S = 0.03  # amplitude granularity within one playback


def parse_wav_pcm(data: bytes) -> Optional[dict[str, Any]]:
    """Parse a RIFF/WAVE file, returning PCM payload + format.

    Returns None for anything that is not an uncompressed PCM WAV —
    measurement is skipped honestly rather than estimated.
    """
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    pos = 12
    fmt: Optional[dict[str, int]] = None
    pcm: Optional[bytes] = None
    while pos + 8 <= len(data):
        chunk_id = data[pos:pos + 4]
        (chunk_size,) = struct.unpack("<I", data[pos + 4:pos + 8])
        body = data[pos + 8:pos + 8 + chunk_size]
        if chunk_id == b"fmt " and len(body) >= 16:
            audio_format, channels, rate, _bps, _align, bits = struct.unpack(
                "<HHIIHH", body[:16])
            fmt = {
                "format": audio_format,
                "channels": channels,
                "sample_rate": rate,
                "bits": bits,
            }
        elif chunk_id == b"data":
            pcm = body
        pos += 8 + chunk_size + (chunk_size & 1)  # chunks are word-aligned
    if fmt is None or pcm is None:
        return None
    if fmt["format"] != 1 or fmt["bits"] not in (8, 16, 32):
        return None
    return {**fmt, "data": pcm}


def pcm_amplitude(chunk: bytes, bits: int, channels: int) -> float:
    """Rough perceived loudness (0..1) of one chunk of interleaved PCM.

    Uses RMS of the first channel, then a gamma curve so typical speech
    sits in a usable range for visual reactivity. Silent → 0.0.
    """
    if bits not in (8, 16, 32) or channels < 1 or not chunk:
        return 0.0
    width = bits // 8
    frame = width * channels
    usable = len(chunk) - (len(chunk) % frame)
    if usable <= 0:
        return 0.0
    if bits == 8:
        # 8-bit WAV is unsigned
        samples = struct.unpack_from("<%dB" % (usable // width), chunk, 0)
        mean = 128.0
        peak = 128.0
    elif bits == 16:
        samples = struct.unpack_from("<%dh" % (usable // width), chunk, 0)
        mean = 0.0
        peak = 32768.0
    else:
        samples = struct.unpack_from("<%di" % (usable // width), chunk, 0)
        mean = 0.0
        peak = 2147483648.0
    acc = 0.0
    n = 0
    for i in range(0, len(samples), channels):  # first channel only
        v = (samples[i] - mean) / peak
        acc += v * v
        n += 1
    if n == 0:
        return 0.0
    rms = math.sqrt(acc / n)
    return min(1.0, math.sqrt(rms))  # gamma 0.5: speech lands ~0.3–0.9


class PlaybackAmplitudeMonitor:
    """Maps real playback time to the amplitude of the chunk being heard."""

    def __init__(self) -> None:
        self._chunks: list[float] = []
        self._chunk_s = _CHUNK_S
        self._t0: float = 0.0
        self._duration: float = 0.0
        self._active = False
        self._last_emit_t = 0.0
        self._last_level = -1.0

    def begin(self, audio: bytes) -> bool:
        """Start monitoring a WAV that is about to play on this machine.

        Returns False (and monitors nothing) when the payload is not
        measurable PCM — honest no-op instead of fabricated levels.
        """
        self.end()
        parsed = parse_wav_pcm(audio)
        if parsed is None:
            return False
        channels = max(1, parsed["channels"])
        bits = parsed["bits"]
        rate = max(1, parsed["sample_rate"])
        data = parsed["data"]
        width = bits // 8
        frame = width * channels
        total_samples = len(data) // frame
        self._chunks = []
        step = max(1, int(rate * self._chunk_s))
        for start in range(0, total_samples, step):
            take = min(step, total_samples - start) * frame
            off = start * frame
            self._chunks.append(pcm_amplitude(data[off:off + take], bits, channels))
        self._duration = total_samples / rate
        self._t0 = time.monotonic()
        self._active = True
        self._last_level = -1.0
        return True

    def tick(self, now: Optional[float] = None) -> float:
        """Amplitude of the chunk the speaker is producing at ``now``."""
        if not self._active or not self._chunks:
            return 0.0
        t = time.monotonic() if now is None else now
        # A ticker may sample marginally before t0 (parsing happens inside
        # begin); clamp to the start of the audio rather than dropping.
        pos = max(0.0, t - self._t0)
        if pos > self._duration + self._chunk_s:
            return 0.0
        idx = min(int(pos / self._chunk_s), len(self._chunks) - 1)
        return self._chunks[idx]

    def end(self) -> None:
        self._active = False
        self._chunks = []
        self._duration = 0.0

    @property
    def active(self) -> bool:
        return self._active

    def emit(self, level: float, speaking: bool) -> None:
        """Best-effort ws push with throttling + no-value-change suppression."""
        # The speaking-state tracker (#132) sees every RAW sample (pre-
        # throttle): it is a pure state machine over the true stream and
        # pushes only debounced transitions.
        try:
            from dash_backend.assistant.voice_speaking_state import (
                get_voice_speaking_state,
            )
            get_voice_speaking_state().on_amplitude(level, speaking)
        except Exception:
            logger.debug("speaking-state feed failed", exc_info=True)
        now = time.monotonic()
        rounded = round(min(1.0, max(0.0, level)), 3)
        if speaking and not self._active:
            return
        if speaking and rounded == self._last_level and (now - self._last_emit_t) < 0.25:
            return
        if speaking and (now - self._last_emit_t) < _EMIT_INTERVAL_S:
            return
        self._last_emit_t = now
        self._last_level = rounded
        try:
            from dash_backend.assistant.push import push_assistant_event
            push_assistant_event(None, {
                "type": "voice.amplitude",
                "level": rounded,
                "speaking": bool(speaking),
            })
        except Exception:
            logger.debug("voice.amplitude push failed", exc_info=True)


_monitor: Optional[PlaybackAmplitudeMonitor] = None


def get_playback_amplitude() -> PlaybackAmplitudeMonitor:
    global _monitor
    if _monitor is None:
        _monitor = PlaybackAmplitudeMonitor()
    return _monitor


def reset_playback_amplitude() -> None:
    global _monitor
    _monitor = None
