"""Interruption Handler - Handle voice interruptions during TTS."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class InterruptionHandler:
    def __init__(self):
        self._speaking = False
        self._callbacks: List[Callable] = []
    
    async def detect_interruption(self, audio_level: float) -> bool:
        """Detect if user is interrupting current speech."""
        if self._speaking and audio_level > 0.6:
            logger.info("Interruption detected")
            for cb in self._callbacks:
                try:
                    cb()
                except Exception:
                    pass
            return True
        return False
    
    def on_interrupt(self, callback: Callable) -> None:
        self._callbacks.append(callback)
    
    @property
    def is_speaking(self) -> bool:
        return self._speaking
    
    @is_speaking.setter
    def is_speaking(self, value: bool) -> None:
        self._speaking = value


_interruption_handler: Optional[InterruptionHandler] = None


def get_interruption_handler() -> InterruptionHandler:
    global _interruption_handler
    if _interruption_handler is None:
        _interruption_handler = InterruptionHandler()
    return _interruption_handler
