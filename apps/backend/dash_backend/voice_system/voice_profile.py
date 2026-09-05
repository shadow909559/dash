"""Voice Profile - Voice settings and profiles management."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceProfile:
    name: str = "default"
    language: str = "en-US"
    speech_rate: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    stt_provider: str = "default"
    tts_provider: str = "default"
    wake_word: str = "dash"
    vad_threshold: float = 0.5
    noise_reduction: bool = True
    auto_interrupt: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class VoiceProfileManager:
    def __init__(self):
        self._profiles: Dict[str, VoiceProfile] = {
            "default": VoiceProfile()
        }
        self._active: str = "default"
    
    def get_active(self) -> VoiceProfile:
        return self._profiles.get(self._active, self._profiles["default"])
    
    def set_active(self, name: str) -> bool:
        if name in self._profiles:
            self._active = name
            return True
        return False
    
    def create_profile(self, name: str, **kwargs) -> VoiceProfile:
        profile = VoiceProfile(name=name, **kwargs)
        self._profiles[name] = profile
        return profile
    
    def delete_profile(self, name: str) -> bool:
        if name == "default":
            return False
        return self._profiles.pop(name, None) is not None
    
    def list_profiles(self) -> List[str]:
        return list(self._profiles.keys())
    
    def update_profile(self, name: str, **kwargs) -> bool:
        profile = self._profiles.get(name)
        if not profile:
            return False
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        return True


_voice_profile_manager: Optional[VoiceProfileManager] = None


def get_voice_profile_manager() -> VoiceProfileManager:
    global _voice_profile_manager
    if _voice_profile_manager is None:
        _voice_profile_manager = VoiceProfileManager()
    return _voice_profile_manager
