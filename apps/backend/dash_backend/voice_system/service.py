"""High-level voice service exposing an API for websocket handlers.

VoiceService manages streaming audio input, wake-word detection, VAD and
transcription flow. It is intentionally provider-agnostic and designed to be
integrated into the existing websocket chat handler without modifying the
contract between Flutter and the backend.

Key features provided by this MVP implementation:
- Start/stop session
- Feed audio chunks (bytes) into the pipeline
- Detect wake word (no-op by default)
- Use configured STT provider to transcribe speech when VAD detects speech end
- Provide hooks for text to be forwarded into the existing chat pipeline
- Expose events for client notification (wake, transcript, error, tts_ready)
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional, Awaitable
import time

from dash_backend.logging_config import get_logger
from .providers import get_speech_provider, get_tts_provider
from .vad import get_default_vad
from .wake_word import NoopWakeWordEngine
from .profiles import get_profile_manager
from .parser import parse_command

logger = get_logger(__name__)


class VoiceSession:
    def __init__(self, session_id: str, user_id: Optional[str] = None):
        self.session_id = session_id
        self.user_id = user_id
        self.profile = get_profile_manager().get("default")
        self._speech_provider = get_speech_provider(self.profile.stt_provider)
        self._tts_provider = get_tts_provider(self.profile.tts_provider)
        self._vad = get_default_vad()
        self._wake_engine = NoopWakeWordEngine()
        self._buffer = bytearray()
        self._last_speech_time = 0.0
        self._on_transcript: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_event: Optional[Callable[[str, dict], Awaitable[None]]] = None
        self._push_to_talk = self.profile.push_to_talk
        self._always_listen = self.profile.always_listen

    def on_transcript(self, cb: Callable[[str], Awaitable[None]]):
        self._on_transcript = cb

    def on_event(self, cb: Callable[[str, dict], Awaitable[None]]):
        self._on_event = cb

    async def feed_audio(self, chunk: bytes):
        """Feed a raw audio chunk (16-bit PCM recommended)."""
        # Feed to wake-word engine
        try:
            wake = await self._wake_engine.feed_audio(chunk)
            if wake and self._on_event:
                await self._on_event("wake", {"data": wake})
        except Exception:
            logger.exception("wake engine error")

        # Buffer and perform simple VAD
        self._buffer.extend(chunk)
        if self._vad.is_speech(chunk):
            self._last_speech_time = time.time()
            return
        # If silence for a small window, consider speech ended
        if self._buffer and (time.time() - self._last_speech_time) > 0.35:
            # attempt transcription
            buf = bytes(self._buffer)
            self._buffer.clear()
            try:
                text = await self._speech_provider.transcribe(buf)
            except Exception:
                logger.exception("speech provider failed")
                text = ""
            if text and self._on_transcript:
                await self._on_transcript(text)
                if self._on_event:
                    await self._on_event("transcript", {"text": text})

    async def synthesize_and_notify(self, text: str):
        try:
            audio = await self._tts_provider.synthesize(text)
            if self._on_event:
                # return base64 via websocket handler as needed
                await self._on_event("tts_ready", {"audio_bytes": audio})
        except Exception:
            logger.exception("tts failed")


class VoiceManager:
    """Top-level manager that tracks voice sessions per websocket connection."""

    def __init__(self):
        self._sessions: dict[str, VoiceSession] = {}

    def start_session(self, session_id: str, user_id: Optional[str] = None) -> VoiceSession:
        s = VoiceSession(session_id=session_id, user_id=user_id)
        self._sessions[session_id] = s
        return s

    def stop_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        return self._sessions.get(session_id)


# single manager instance
_voice_manager: Optional[VoiceManager] = None


def get_voice_manager() -> VoiceManager:
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = VoiceManager()
    return _voice_manager


# Convenience service wrapper for integration
class VoiceService:
    def __init__(self):
        self.manager = get_voice_manager()

    def create_session(self, session_id: str, user_id: Optional[str] = None) -> VoiceSession:
        return self.manager.start_session(session_id, user_id)

    def end_session(self, session_id: str) -> None:
        self.manager.stop_session(session_id)

    def get(self, session_id: str) -> Optional[VoiceSession]:
        return self.manager.get_session(session_id)


# module-level service instance
service = VoiceService()
