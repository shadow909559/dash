"""Sentence-streaming TTS (spec #8/#45 — decisions.md #102).

The wake loop previously synthesized the ENTIRE reply before a single
sample reached the speaker. This module splits a reply into speakable
sentences and yields them as they complete, so playback of sentence 1
starts while the rest is still being synthesized. First-audio latency
(TTFA) drops from "full synthesis" to "first sentence synthesis".

Design constraints:
- No new dependencies; pure-python sentence split tuned for short
  assistant replies (abbreviations, decimals, ellipses).
- The caller owns playback concurrency; this module never touches audio
  devices. `speak_streamed` orchestrates synth-while-playing with a
  bounded one-item look-ahead so a slow synth cannot stack unbounded
  playback tasks.
- Every TTFA observation is REAL (measured from the injected clock), or
  the metric is simply not recorded — never estimated.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

# Sentence boundary: . ! ? … followed by space/end, but NOT a decimal
# point, a known abbreviation, or a single capital initial ("J. Smith").
_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+(?=[A-Z0-9\"'(])")
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "st", "vs", "e.g", "i.e", "etc"}


def split_sentences(text: str, min_len: int = 2) -> list[str]:
    """Split into speakable sentences; merges tiny fragments forward.

    Deterministic and dependency-free. Returns at least one chunk for any
    non-empty input so callers never dead-lock on an empty split.
    """
    text = (text or "").strip()
    if not text:
        return []
    raw = _SENTENCE_RE.split(text)
    out: list[str] = []
    for piece in raw:
        piece = piece.strip()
        if not piece:
            continue
        # "e.g." / "St." trailing dots already split above only when
        # followed by a capital — re-merge obvious abbreviations.
        if out and _ends_with_abbreviation(out[-1]):
            out[-1] = f"{out[-1]} {piece}"
            continue
        if len(piece) < min_len and out:
            out[-1] = f"{out[-1]} {piece}"
            continue
        out.append(piece)
    if not out:
        out = [text]
    return out


def _ends_with_abbreviation(sentence: str) -> bool:
    tail = sentence.rstrip().split()[-1].rstrip(".").lower() if sentence.strip() else ""
    return tail in _ABBREVIATIONS


async def speak_streamed(
    text: str,
    synthesize: Callable[[str], Awaitable[bytes]],
    play: Callable[[bytes], Awaitable[None]],
    *,
    clock: Callable[[], float] = time.time,
    look_ahead: int = 1,
) -> dict:
    """Stream a reply sentence-by-sentence: synth sentence N while
    sentence N-1 plays. Returns honest telemetry.

    `look_ahead` bounds how many synthesies may run ahead of playback
    (default 1: at most one sentence is pre-rendered).

    Raises nothing for individual sentence failures — failures are
    recorded in the result so the caller can decide (a partially spoken
    reply is reported, never claimed complete).
    """
    sentences = split_sentences(text)
    result: dict = {
        "sentences": len(sentences),
        "spoken": 0,
        "failed": 0,
        "ttfa_ms": None,
        "cancelled": False,
    }
    if not sentences:
        return result

    t0 = clock()
    first_audio_recorded = False

    # bounded look-ahead: a queue of pending synthesis tasks
    pending: dict[int, asyncio.Task] = {}

    def _queue_next(idx: int) -> None:
        while idx < len(sentences) and len(pending) <= look_ahead:
            if idx in pending:
                idx += 1
                continue
            pending[idx] = asyncio.ensure_future(synthesize(sentences[idx]))
            idx += 1

    _queue_next(0)
    for i in range(len(sentences)):
        if i not in pending:
            _queue_next(i)
        try:
            audio = await pending.pop(i)
        except asyncio.CancelledError:
            result["cancelled"] = True
            for task in pending.values():
                task.cancel()
            raise
        except Exception as exc:  # synth failure: record, keep going
            result["failed"] += 1
            logger.warning("streamed TTS sentence %d failed: %s", i, exc)
            continue
        if not audio:
            result["failed"] += 1
            continue
        if not first_audio_recorded:
            result["ttfa_ms"] = round((clock() - t0) * 1000.0, 1)
            first_audio_recorded = True
            try:
                from dash_backend.assistant.metrics import observe_latency
                observe_latency("tts_first_audio", result["ttfa_ms"])
            except Exception:
                pass
        try:
            await play(audio)
            result["spoken"] += 1
        except asyncio.CancelledError:
            result["cancelled"] = True
            for task in pending.values():
                task.cancel()
            raise
        except Exception as exc:
            result["failed"] += 1
            logger.warning("streamed TTS playback sentence %d failed: %s", i, exc)
    return result
