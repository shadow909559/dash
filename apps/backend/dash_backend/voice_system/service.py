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
import os
import platform
import subprocess
import tempfile
import time
import uuid
from typing import Callable, Optional, Awaitable

from dash_backend.logging_config import get_logger
from .providers import get_speech_provider, get_tts_provider
from .vad import get_default_vad
from .wake_word import NoopWakeWordEngine
from .profiles import get_profile_manager

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
        # Piper playback state
        self._interrupt_flag = asyncio.Event()
        self._is_speaking = False
        self._temp_files: list[str] = []

    def on_transcript(self, cb: Callable[[str], Awaitable[None]]):
        self._on_transcript = cb

    def on_event(self, cb: Callable[[str, dict], Awaitable[None]]):
        self._on_event = cb

    async def feed_audio(self, chunk: bytes):
        """Feed a raw audio chunk (16-bit PCM recommended)."""
        # Interrupt current TTS if user speaks
        if self._is_speaking and self._vad.is_speech(chunk):
            await self.interrupt_speech()

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
        """Synthesize text to speech and play it locally.

        Uses the Piper provider to generate WAV audio, writes to a temp file,
        plays it via platform audio, then cleans up.
        """
        if not text or not text.strip():
            return

        self._is_speaking = True
        self._interrupt_flag.clear()

        try:
            # Get the raw TTS provider (may be PiperTTSProvider)
            audio = await self._tts_provider.synthesize(text)
            if not audio:
                logger.warning("TTS produced empty audio for: %s", text[:50])
                return

            if self._interrupt_flag.is_set():
                return

            # Write temp WAV file
            tmp_path = os.path.join(
                tempfile.gettempdir(),
                f"dash_tts_{uuid.uuid4().hex[:12]}.wav",
            )
            try:
                with open(tmp_path, "wb") as f:
                    f.write(audio)
                self._temp_files.append(tmp_path)

                # Play via platform audio
                await self._play_wav(tmp_path)

                # Notify via event
                if self._on_event:
                    import base64
                    audio_b64 = base64.b64encode(audio).decode("ascii")
                    await self._on_event("tts_ready", {"audio_bytes": audio_b64})

            finally:
                self._cleanup_temp(tmp_path)

        except Exception:
            logger.exception("TTS playback failed")
        finally:
            self._is_speaking = False

    async def interrupt_speech(self):
        """Interrupt current TTS playback."""
        self._interrupt_flag.set()
        self._is_speaking = False
        # Kill any active Piper subprocess via the provider
        try:
            from dash_backend.voice import get_provider
            piper = get_provider("tts", "piper")
            if piper and hasattr(piper, "interrupt"):
                piper.interrupt()
        except Exception:
            logger.exception("Failed to interrupt Piper")
        if self._on_event:
            await self._on_event("interrupt", {})

    async def _play_wav(self, wav_path: str) -> None:
        """Play a WAV file using platform audio.

        On Windows uses winsound. On macOS uses afplay. On Linux uses aplay/paplay.
        Checks interrupt flag periodically.
        """
        if self._interrupt_flag.is_set():
            return

        system = platform.system()

        try:
            if system == "Windows":
                import winsound
                loop = asyncio.get_running_loop()

                def _play():
                    if not self._interrupt_flag.is_set():
                        winsound.PlaySound(wav_path, winsound.SND_FILENAME)

                await loop.run_in_executor(None, _play)

            elif system == "Darwin":
                proc = await asyncio.create_subprocess_exec(
                    "afplay", wav_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                while True:
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=0.2)
                        break
                    except asyncio.TimeoutError:
                        if self._interrupt_flag.is_set():
                            proc.kill()
                            break

            else:
                # Linux: try paplay then aplay
                for candidate in ["paplay", "aplay"]:
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            candidate, wav_path,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        while True:
                            try:
                                await asyncio.wait_for(proc.wait(), timeout=0.2)
                                break
                            except asyncio.TimeoutError:
                                if self._interrupt_flag.is_set():
                                    proc.kill()
                                    break
                        break
                    except FileNotFoundError:
                        continue

        except Exception:
            logger.exception("Failed to play audio")

    def _cleanup_temp(self, path: str) -> None:
        """Delete a single temp file if it exists."""
        try:
            if os.path.exists(path):
                os.remove(path)
            if path in self._temp_files:
                self._temp_files.remove(path)
        except Exception:
            logger.exception("Failed to delete temp file %s", path)

    def cleanup_all_temp(self) -> None:
        """Delete all tracked temporary audio files."""
        for path in list(self._temp_files):
            self._cleanup_temp(path)
        self._temp_files.clear()


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
            s = self._sessions[session_id]
            s.cleanup_all_temp()
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
