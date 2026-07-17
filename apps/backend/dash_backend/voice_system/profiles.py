"""Manage voice profiles and settings.

Voice profiles hold user-specific synthesis/recognition preferences, speaker
selection and audio routing. Profiles are stored in-memory in this MVP and can
be persisted in the DB later (via memory or a new table) if desired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class VoiceProfile:
    id: str
    name: str
    stt_provider: Optional[str] = None
    tts_provider: Optional[str] = None
    tts_voice: Optional[str] = None
    vad_sensitivity: float = 0.5
    push_to_talk: bool = False
    always_listen: bool = False


class VoiceProfileManager:
    def __init__(self):
        self._profiles: Dict[str, VoiceProfile] = {}
        # create default profile
        default = VoiceProfile(id="default", name="default", stt_provider="default", tts_provider="default")
        self._profiles[default.id] = default

    def get(self, profile_id: str = "default") -> VoiceProfile:
        return self._profiles.get(profile_id) or self._profiles["default"]

    def update(self, profile_id: str, **kwargs) -> VoiceProfile:
        p = self._profiles.get(profile_id)
        if not p:
            p = VoiceProfile(id=profile_id, name=profile_id)
            self._profiles[profile_id] = p
        for k, v in kwargs.items():
            if hasattr(p, k):
                setattr(p, k, v)
        return p


# singleton
_profile_manager: Optional[VoiceProfileManager] = None


def get_profile_manager() -> VoiceProfileManager:
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = VoiceProfileManager()
    return _profile_manager
