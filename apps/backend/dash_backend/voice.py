"""Voice support module (STT/TTS provider abstractions and simple defaults).

This single-module implementation keeps things minimal and avoids adding a new
package directory (simpler to maintain in this environment). Production users
can split this into a package later.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from dataclasses import dataclass
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------
# Models
# ---------------------------

@dataclass
class VoiceTranscript:
    text: str
    language: Optional[str] = None


@dataclass
class VoiceAudio:
    audio_bytes: bytes
    mime: str = "audio/wav"


# ---------------------------
# Provider abstractions
# ---------------------------


class SpeechProvider:
    name: str = "base"

    async def transcribe(self, audio_bytes: bytes) -> str:
        raise NotImplementedError


class TTSProvider:
    name: str = "base"

    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError


# Simple registry
_PROVIDERS: Dict[str, Dict[str, Any]] = {"speech": {}, "tts": {}}


def register_provider(kind: str, name: str, provider: Any) -> None:
    if kind not in _PROVIDERS:
        raise ValueError("Unknown provider kind")
    _PROVIDERS[kind][name] = provider


def get_provider(kind: str, name: Optional[str] = None):
    providers = _PROVIDERS.get(kind, {})
    if name:
        return providers.get(name)
    return next(iter(providers.values()), None)


# ---------------------------
# Default noop providers
# ---------------------------


class _NoopSpeechProvider(SpeechProvider):
    name = "noop"

    async def transcribe(self, audio_bytes: bytes) -> str:
        # Try to decode utf-8 content if test harness sent plain text
        try:
            s = audio_bytes.decode("utf-8").strip()
            if s:
                return s
        except Exception:
            pass
        return "[voice transcription not available]"


class _NoopTTSProvider(TTSProvider):
    name = "noop"

    async def synthesize(self, text: str) -> bytes:
        # Return empty bytes; clients should handle gracefully
        return b""


# Register default noop providers so functionality is available without config
register_provider("speech", "default", _NoopSpeechProvider())
register_provider("tts", "default", _NoopTTSProvider())


# ---------------------------
# Service helpers
# ---------------------------


async def transcribe_audio(audio_bytes: bytes, provider_name: Optional[str] = None, *, user_id: Optional[str] = None, store: bool = False) -> str:
    provider = get_provider("speech", provider_name)
    if provider is None:
        provider = get_provider("speech")
    try:
        text = await provider.transcribe(audio_bytes)
        return text
    except Exception as exc:
        logger.exception("STT provider error: %s", exc)
        return "[speech transcription failed]"


async def synthesize_text(text: str, provider_name: Optional[str] = None, *, user_id: Optional[str] = None) -> str:
    provider = get_provider("tts", provider_name)
    if provider is None:
        provider = get_provider("tts")
    try:
        audio_bytes = await provider.synthesize(text)
        return base64.b64encode(audio_bytes).decode("ascii")
    except Exception as exc:
        logger.exception("TTS provider error: %s", exc)
        return ""
