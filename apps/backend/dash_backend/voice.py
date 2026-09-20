"""Voice support module (STT/TTS provider abstractions and simple defaults).

This single-module implementation keeps things minimal and avoids adding a new
package directory (simpler to maintain in this environment). Production users
can split this into a package later.
"""
from __future__ import annotations

import asyncio
import base64
import os
import time
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


class WhisperSpeechProvider(SpeechProvider):
    """Local, fully offline STT with two interchangeable engines.

    Primary engine is **faster-whisper** (CTranslate2 reimplementation —
    roughly 3-4x faster than openai-whisper on CPU at comparable accuracy,
    same model family). When it is not installed (or fails to load), the
    provider falls back to the original **openai-whisper** implementation —
    same models, same ffmpeg-based file decoding, slower.

    Which engine actually ran is recorded in ``engine`` ("faster-whisper"
    or "openai-whisper") so logs and status never have to guess. Models
    download once on first use to each engine's standard cache; after that
    transcription never touches the network — audio stays on this machine.
    Default model is ``base.en`` (CPU-friendly); override with the
    ``DASH_WHISPER_MODEL`` env var or a constructor arg.

    Failure contract: returns "" on any failure — the websocket STT handler
    turns an empty transcript into a clean voice.stt.error instead of
    forwarding garbage into the LLM pipeline.
    """

    name = "whisper"

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or os.getenv("DASH_WHISPER_MODEL", "base.en")
        self.engine = "none"  # set when the model first loads
        self._model: Any = None
        # Serializes load + transcription. A local assistant sends one
        # utterance at a time; queuing beats racing a shared whisper model.
        self._lock = asyncio.Lock()

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        # Preference: faster-whisper (same models, ~3-4x faster on CPU).
        # ImportError = not installed; any other load failure (bad download,
        # incompatible wheel) is also worth an honest fallback attempt —
        # the engine that actually ran is always reported.
        try:
            from faster_whisper import WhisperModel

            # int8 is the measured sweet spot on this CPU-only machine:
            # 1.16s vs 1.60s per ~6.5s clip vs openai-whisper with IDENTICAL
            # word error rate (scripts/bench_stt_engines.py). Set
            # DASH_WHISPER_COMPUTE=float32 (or auto) to disable.
            compute = os.getenv("DASH_WHISPER_COMPUTE", "int8").strip()
            kwargs: dict[str, Any] = {}
            if compute and compute != "auto":
                kwargs["compute_type"] = compute
            logger.info("STT: loading faster-whisper model '%s' (first use may download it)", self.model_name)
            self._model = WhisperModel(self.model_name, device="cpu", **kwargs)
            self.engine = "faster-whisper"
            logger.info("STT: faster-whisper model '%s' ready", self.model_name)
            return self._model
        except ImportError:
            logger.info("STT: faster-whisper not installed — using openai-whisper fallback")
        except Exception:
            logger.exception("STT: faster-whisper failed to load — trying openai-whisper fallback")

        import whisper

        logger.info("STT: loading openai-whisper model '%s' (first use may download it)", self.model_name)
        self._model = whisper.load_model(self.model_name)
        self.engine = "openai-whisper"
        logger.info("STT: openai-whisper model '%s' ready", self.model_name)
        return self._model

    def _transcribe_sync(self, model: Any, path: str) -> str:
        """Engine-specific call; both decode any container via ffmpeg."""
        if self.engine == "faster-whisper":
            segments, _info = model.transcribe(path)
            # segments is a lazy generator; iterating runs the actual decode.
            return "".join(seg.text for seg in segments).strip()
        result = model.transcribe(path)
        return str(result.get("text", "")).strip()

    async def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        import os as _os
        import tempfile

        # Both engines read from file paths; decode whatever the client sent
        # via ffmpeg (bundled with whisper's dependency chain), so any
        # container (wav/webm/ogg/mp3) works.
        fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="dash_stt_")
        try:
            with _os.fdopen(fd, "wb") as fh:
                fh.write(audio_bytes)
            async with self._lock:
                try:
                    model = await asyncio.to_thread(self._load_model)
                    text = await asyncio.to_thread(self._transcribe_sync, model, tmp_path)
                except Exception as exc:
                    logger.exception("Whisper STT error: %s", exc)
                    return ""
            return text
        finally:
            try:
                _os.unlink(tmp_path)
            except OSError:
                pass


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


def _register_stt_providers(whisper_available: Optional[bool] = None) -> None:
    """Register STT providers. Preference order:

    1. Whisper (local, offline, private) — default when a local whisper engine
       is importable: faster-whisper first (same models, ~3-4x faster on
       CPU), openai-whisper as the fallback engine it serves.
    2. speech_recognition (Google Web Speech API — cloud) — default only when
       no local engine exists; always registered under its own name so it can
       be selected explicitly.
    """
    if whisper_available is None:
        whisper_available = False
        try:
            import faster_whisper as _fw  # noqa: F401

            whisper_available = True
        except ImportError:
            pass
        if not whisper_available:
            try:
                import whisper as _whisper  # noqa: F401

                whisper_available = True
            except ImportError:
                pass

    if whisper_available:
        _whisper_provider = WhisperSpeechProvider()
        register_provider("speech", "whisper", _whisper_provider)
        register_provider("speech", "default", _whisper_provider)
        logger.info("Whisper STT provider registered as default (offline, model=%s)", _whisper_provider.model_name)

    try:
        import speech_recognition as _sr  # noqa: F401

        register_provider("speech", "speech_recognition", _SpeechRecognitionProvider())
        if not whisper_available:
            register_provider("speech", "default", _SpeechRecognitionProvider())
            logger.info("SpeechRecognition STT provider registered as default (cloud fallback)")
    except Exception:
        logger.exception("Failed to register speech_recognition STT provider")


_register_stt_providers()

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
    _t0 = time.perf_counter()
    try:
        text = await provider.transcribe(audio_bytes)
        try:
            from dash_backend.assistant.metrics import observe_latency
            observe_latency("voice_stt", (time.perf_counter() - _t0) * 1000.0)
        except Exception:
            pass
        return text
    except Exception as exc:
        logger.exception("STT provider error: %s", exc)
        try:
            from dash_backend.assistant.metrics import incr_error
            incr_error("voice_stt")
        except Exception:
            pass
        return "[speech transcription failed]"


async def synthesize_text(text: str, provider_name: Optional[str] = None, *, user_id: Optional[str] = None) -> str:
    provider = get_provider("tts", provider_name)
    if provider is None:
        provider = get_provider("tts")
    _t0 = time.perf_counter()
    try:
        audio_bytes = await provider.synthesize(text)
        try:
            from dash_backend.assistant.metrics import observe_latency
            observe_latency("voice_tts", (time.perf_counter() - _t0) * 1000.0)
        except Exception:
            pass
        return base64.b64encode(audio_bytes).decode("ascii")
    except Exception as exc:
        logger.exception("TTS provider error: %s", exc)
        try:
            from dash_backend.assistant.metrics import incr_error
            incr_error("voice_tts")
        except Exception:
            pass
        return ""
