"""Wake-word engine abstraction.

This module provides a simple pluggable wake-word detection interface. It
includes a NoopWakeWordEngine that never triggers and an in-memory example
that can trigger when a specific phrase appears in recent transcripts.

Real wake-word engines (porcupine, snowboy, VOSK-based keyword spotting) can
be integrated by implementing WakeWordEngine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import asyncio

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class WakeWordEngine:
    """Abstract interface for wake-word detectors."""

    name: str = "base"

    async def feed_audio(self, audio_chunk: bytes) -> Optional[dict]:
        """Feed an audio chunk to the detector; return non-None dict when
        wake-word is detected with metadata e.g. {"phrase": "hey dash", "confidence": 0.9}
        """
        raise NotImplementedError


class NoopWakeWordEngine(WakeWordEngine):
    name = "noop"

    async def feed_audio(self, audio_chunk: bytes) -> Optional[dict]:
        # Never triggers
        await asyncio.sleep(0)
        return None


@dataclass
class PhraseWakeWordEngine(WakeWordEngine):
    """A simple wake-word implementation that watches transcripts for a phrase.

    This is intended for environments where audio is fed through STT and
    transcripts are available to check for wake words (not for production
    always-on keyword spotting, but useful for quick testing).
    """

    phrase: str
    name: str = "phrase"

    async def feed_audio(self, audio_chunk: bytes) -> Optional[dict]:
        # This engine assumes audio_chunk is actually text bytes for simple testing
        try:
            text = audio_chunk.decode("utf-8", errors="ignore").lower()
            if self.phrase.lower() in text:
                return {"phrase": self.phrase, "confidence": 0.9}
        except Exception:
            pass
        return None
