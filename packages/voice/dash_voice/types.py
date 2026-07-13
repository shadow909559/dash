"""Voice processing types (scaffold)."""

from enum import Enum


class VoiceMode(str, Enum):
    """Voice interaction modes."""

    STT = "speech_to_text"
    TTS = "text_to_speech"
