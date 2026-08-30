"""Wake Word Detection - Trigger phrase detection for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class WakeWordDetector:
    def __init__(self, wake_word: str = "dash"):
        self._wake_word = wake_word.lower()
        self._listening = False
        self._callbacks: List[Callable] = []
    
    async def start(self) -> None:
        self._listening = True
        logger.info("Wake word detection started: '%s'", self._wake_word)
    
    async def stop(self) -> None:
        self._listening = False
    
    async def process_audio(self, audio_chunk: bytes) -> bool:
        """Return True when the configured wake word/phrase is detected.

        This simple detector is a stub: it lowercases the incoming audio bytes (if
        decodable) and searches for the wake word. In production this would be a
        proper speech/keyword detector.
        """
        if not self._listening:
            return False
        try:
            text = audio_chunk.decode("utf-8", errors="ignore").lower()
            return self._wake_word in text
        except Exception:
            return False
    
    def on_wake_word(self, callback: Callable) -> None:
        self._callbacks.append(callback)
    
    def set_wake_word(self, word: str) -> None:
        self._wake_word = word.lower()
    
    @property
    def is_listening(self) -> bool:
        return self._listening


# Backwards-compatible noop/phrase engines used by tests and legacy code
class NoopWakeWordEngine:
    """Legacy noop engine kept for backward compatibility.

    Provides async feed_audio(audio_chunk) -> None
    """
    async def feed_audio(self, audio_chunk: bytes):
        return None


class PhraseWakeWordEngine:
    """Simple phrase-based wake word engine for tests.

    Usage: engine = PhraseWakeWordEngine(phrase="hey dash")
    The async feed_audio method returns {"phrase": phrase} when the phrase
    is found in the decoded audio bytes; otherwise returns None.
    """
    def __init__(self, phrase: str = "dash"):
        self.phrase = phrase.lower()

    async def feed_audio(self, audio_chunk: bytes):
        try:
            text = audio_chunk.decode("utf-8", errors="ignore").lower()
            if self.phrase in text:
                return {"phrase": self.phrase}
        except Exception:
            pass
        return None


_wake_word_detector: Optional[WakeWordDetector] = None


def get_wake_word_detector() -> WakeWordDetector:
    global _wake_word_detector
    if _wake_word_detector is None:
        _wake_word_detector = WakeWordDetector()
    return _wake_word_detector
