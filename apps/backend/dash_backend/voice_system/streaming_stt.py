"""Streaming STT - Real-time speech-to-text with streaming support."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StreamingSTT:
    def __init__(self):
        self._is_streaming = False
        self._callbacks: List[Callable] = []
        self._interim_results: List[str] = []
        self._final_text = ""
    
    async def start_streaming(self, sample_rate: int = 16000) -> bool:
        self._is_streaming = True
        self._interim_results = []
        self._final_text = ""
        logger.info("STT streaming started (sample_rate=%d)", sample_rate)
        return True
    
    async def stop_streaming(self) -> str:
        self._is_streaming = False
        result = self._final_text
        self._final_text = ""
        return result
    
    async def process_chunk(self, audio_chunk: bytes) -> Optional[str]:
        if not self._is_streaming:
            return None
        try:
            from dash_backend.voice import transcribe_audio
            text = await transcribe_audio(audio_chunk)
            if text and text != "[voice transcription not available]":
                self._final_text += " " + text
                for cb in self._callbacks:
                    try:
                        cb({"type": "stt.interim", "text": text})
                    except Exception:
                        pass
                return text
        except Exception as exc:
            logger.debug("STT chunk error: %s", exc)
        return None
    
    def on_transcript(self, callback: Callable) -> None:
        self._callbacks.append(callback)
    
    @property
    def is_streaming(self) -> bool:
        return self._is_streaming


_streaming_stt: Optional[StreamingSTT] = None


def get_streaming_stt() -> StreamingSTT:
    global _streaming_stt
    if _streaming_stt is None:
        _streaming_stt = StreamingSTT()
    return _streaming_stt
