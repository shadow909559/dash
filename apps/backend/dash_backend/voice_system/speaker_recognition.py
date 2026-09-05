"""Speaker Recognition - Identify and recognize speakers for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpeakerRecognition:
    def __init__(self):
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._current_speaker: Optional[str] = None
    
    async def register_voice(self, speaker_id: str, audio_sample: bytes) -> bool:
        self._profiles[speaker_id] = {
            "sample": audio_sample,
            "registered_at": asyncio.get_event_loop().time(),
        }
        logger.info("Registered speaker: %s", speaker_id)
        return True
    
    async def identify(self, audio_chunk: bytes) -> Optional[str]:
        return self._current_speaker
    
    async def set_current_speaker(self, speaker_id: Optional[str]) -> None:
        self._current_speaker = speaker_id
    
    def list_profiles(self) -> List[str]:
        return list(self._profiles.keys())


_speaker_recognition: Optional[SpeakerRecognition] = None


def get_speaker_recognition() -> SpeakerRecognition:
    global _speaker_recognition
    if _speaker_recognition is None:
        _speaker_recognition = SpeakerRecognition()
    return _speaker_recognition
