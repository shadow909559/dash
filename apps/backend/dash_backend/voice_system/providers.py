"""Provider interfaces and adapters for speech and TTS.

These interfaces wrap the lower-level provider registry in apps/backend/dash_backend/voice.py
and expose a clearer, typed interface for the voice subsystem. They also provide
noop adapters which are used when no real provider is configured.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable
import asyncio
import base64

from dash_backend.logging_config import get_logger
import dash_backend.voice as core_voice

logger = get_logger(__name__)


@runtime_checkable
class SpeechProviderInterface(Protocol):
    name: str

    async def transcribe(self, audio_bytes: bytes) -> str:
        ...


@runtime_checkable
class TTSProviderInterface(Protocol):
    name: str

    async def synthesize(self, text: str) -> bytes:
        ...


# Adapters to the core voice module providers
class CoreSpeechAdapter:
    def __init__(self, provider_name: Optional[str] = None):
        self.provider_name = provider_name
        self.provider = core_voice.get_provider("speech", provider_name)

    async def transcribe(self, audio_bytes: bytes) -> str:
        if self.provider is None:
            self.provider = core_voice.get_provider("speech")
        try:
            return await self.provider.transcribe(audio_bytes)
        except Exception as exc:
            logger.exception("CoreSpeechAdapter error: %s", exc)
            return ""


class CoreTTSAdapter:
    def __init__(self, provider_name: Optional[str] = None):
        self.provider_name = provider_name
        self.provider = core_voice.get_provider("tts", provider_name)

    async def synthesize(self, text: str) -> bytes:
        if self.provider is None:
            self.provider = core_voice.get_provider("tts")
        try:
            return await self.provider.synthesize(text)
        except Exception as exc:
            logger.exception("CoreTTSAdapter error: %s", exc)
            return b""


# Factory helpers
def get_speech_provider(name: Optional[str] = None) -> SpeechProviderInterface:
    return CoreSpeechAdapter(name)


def get_tts_provider(name: Optional[str] = None) -> TTSProviderInterface:
    return CoreTTSAdapter(name)
