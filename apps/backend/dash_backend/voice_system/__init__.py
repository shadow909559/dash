"""Voice subsystem package

Provides a higher-level voice-first architecture built on top of the existing
apps/backend/dash_backend/voice.py provider abstractions.

This package intentionally contains lightweight, well-documented components that
can be integrated into the websocket/chat pipeline without forcing changes to
existing endpoints. All heavy functionality (wake-word, VAD, audio processing)
is provider-abstracted and ships with safe noop defaults so the system runs in
environments without native audio tooling.
"""
from .manager import VoiceManager
from .providers import SpeechProviderInterface, TTSProviderInterface
from .service import VoiceService

__all__ = ["VoiceManager", "SpeechProviderInterface", "TTSProviderInterface", "VoiceService"]
