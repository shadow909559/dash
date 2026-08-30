"""Noise Suppressor - Background noise reduction for voice processing."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class NoiseSuppressor:
    def __init__(self, reduction_level: float = 0.5):
        self._reduction_level = reduction_level
        self._enabled = True
    
    async def process(self, audio_chunk: bytes) -> bytes:
        if not self._enabled:
            return audio_chunk
        return audio_chunk
    
    def set_level(self, level: float) -> None:
        self._reduction_level = max(0.0, min(1.0, level))
    
    def enable(self) -> None:
        self._enabled = True
    
    def disable(self) -> None:
        self._enabled = False


_noise_suppressor: Optional[NoiseSuppressor] = None


def get_noise_suppressor() -> NoiseSuppressor:
    global _noise_suppressor
    if _noise_suppressor is None:
        _noise_suppressor = NoiseSuppressor()
    return _noise_suppressor
