"""Voice support module (STT/TTS provider abstractions and simple defaults).

This single-module implementation keeps things minimal and avoids adding a new
package directory (simpler to maintain in this environment). Production users
can split this into a package later.
"""
from __future__ import annotations

import asyncio
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


class _SpeechRecognitionProvider(SpeechProvider):
    """Real STT provider using the installed `speech_recognition` package
    (Google Web Speech API). Falls back to the noop result if unavailable."""

    name = "speech_recognition"

    async def transcribe(self, audio_bytes: bytes) -> str:
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            # speech_recognition accepts WAV/FLAC/AIFF raw bytes via AudioData
            audio = sr.AudioData(audio_bytes, 16000, 2)
            text = await asyncio.to_thread(
                recognizer.recognize_google, audio
            )
            return (text or "").strip()
        except sr.UnknownValueError:
            logger.warning("STT: could not understand audio")
            return ""
        except sr.RequestError as exc:
            logger.warning("STT: speech_recognition request error: %s", exc)
            return ""
        except Exception as exc:
            logger.exception("STT speech_recognition provider error: %s", exc)
            return ""


# Prefer the real speech_recognition STT provider when available.
try:
    import speech_recognition as _sr  # noqa: F401

    register_provider("speech", "default", _SpeechRecognitionProvider())
    logger.info("SpeechRecognition STT provider registered")
except Exception:
    logger.exception("Failed to register speech_recognition STT provider")

# Register Piper TTS provider (local neural TTS via piper.exe).
# Piper is registered under both "piper" and "default" so that explicit
# voice.tts requests and implicit auto-TTS both prefer the local neural
# engine when it is available.
try:
    from dash_backend.voice_system.piper_provider import PiperTTSProvider

    _piper = PiperTTSProvider()
    register_provider("tts", "piper", _piper)
    register_provider("tts", "default", _piper)
    logger.info("Piper TTS provider registered (voice=ryan)")
except Exception:
    logger.exception("Failed to register Piper TTS provider")


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
