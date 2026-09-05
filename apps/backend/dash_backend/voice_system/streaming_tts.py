"""Streaming TTS - Real-time text-to-speech with streaming support."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable, List, Optional

logger = logging.getLogger(__name__)


class StreamingTTS:
    def __init__(self):
        self._is_speaking = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._callbacks: List[Callable] = []
        self._interrupt = False
    
    async def speak(self, text: str) -> AsyncIterator[bytes]:
        self._is_speaking = True
        self._interrupt = False
        
        try:
            from dash_backend.voice import synthesize_text
            audio_b64 = await synthesize_text(text)
            if audio_b64:
                import base64
                audio_bytes = base64.b64decode(audio_b64)
                chunk_size = 4096
                for i in range(0, len(audio_bytes), chunk_size):
                    if self._interrupt:
                        break
                    chunk = audio_bytes[i:i + chunk_size]
                    yield chunk
                    await asyncio.sleep(0.01)
        except Exception as exc:
            logger.warning("TTS speak error: %s", exc)
        finally:
            self._is_speaking = False
    
    async def interrupt(self) -> None:
        self._interrupt = True
        self._is_speaking = False
    
    def on_audio(self, callback: Callable) -> None:
        self._callbacks.append(callback)
    
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking


_streaming_tts: Optional[StreamingTTS] = None


def get_streaming_tts() -> StreamingTTS:
    global _streaming_tts
    if _streaming_tts is None:
        _streaming_tts = StreamingTTS()
    return _streaming_tts
