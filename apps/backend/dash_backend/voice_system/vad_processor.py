"""VAD Processor - Voice Activity Detection for natural conversation."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class VADProcessor:
    def __init__(self, threshold: float = 0.5, silence_duration: float = 1.0):
        self._threshold = threshold
        self._silence_duration = silence_duration
        self._is_speaking = False
        self._silence_start: Optional[float] = None
        self._callbacks: List[Callable] = []
    
    async def process_audio(self, audio_level: float) -> str:
        """Process audio level and return VAD state.
        
        Returns: "speech_start", "speech_end", or "silence"
        """
        if audio_level > self._threshold:
            if not self._is_speaking:
                self._is_speaking = True
                self._silence_start = None
                for cb in self._callbacks:
                    try:
                        cb("speech_start")
                    except Exception:
                        pass
                return "speech_start"
            return "speaking"
        else:
            if self._is_speaking:
                if self._silence_start is None:
                    self._silence_start = asyncio.get_event_loop().time()
                elif (asyncio.get_event_loop().time() - self._silence_start) > self._silence_duration:
                    self._is_speaking = False
                    self._silence_start = None
                    for cb in self._callbacks:
                        try:
                            cb("speech_end")
                        except Exception:
                            pass
                    return "speech_end"
            return "silence"
    
    def on_vad_event(self, callback: Callable) -> None:
        self._callbacks.append(callback)
    
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking


_vad_processor: Optional[VADProcessor] = None


def get_vad_processor() -> VADProcessor:
    global _vad_processor
    if _vad_processor is None:
        _vad_processor = VADProcessor()
    return _vad_processor
