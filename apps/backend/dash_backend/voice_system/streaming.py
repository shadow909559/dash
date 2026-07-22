"""Streaming voice conversation support with interrupt handling.

Provides an audio stream pipeline that can feed transcription into the
chat pipeline while supporting push-to-talk, continuous listening,
and interrupt handling.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable, Optional

from dash_backend.logging_config import get_logger
from dash_backend.voice_system.providers import get_speech_provider, get_tts_provider
from dash_backend.voice_system.vad import get_default_vad
from dash_backend.voice_system.wake_word import NoopWakeWordEngine

logger = get_logger(__name__)


class AudioStreamState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


class InterruptFlag:
    """Thread-safe interrupt flag for cancelling in-progress TTS or processing."""

    def __init__(self):
        self._interrupted = False

    def set(self):
        self._interrupted = True

    def clear(self):
        self._interrupted = False

    @property
    def is_set(self) -> bool:
        return self._interrupted


class StreamingVoiceProcessor:
    """Handles streaming voice input → transcription → LLM → TTS pipeline.

    Supports:
    - Push-to-talk mode (explicit start/stop)
    - Continuous listening with VAD-based speech detection
    - Wake word detection to start listening
    - Interrupt handling (user speaks while TTS is playing)
    - Memory/planner/RAG integration hooks
    """

    def __init__(
        self,
        *,
        stt_provider_name: Optional[str] = None,
        tts_provider_name: Optional[str] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_state_change: Optional[Callable[[AudioStreamState], None]] = None,
        on_interrupt: Optional[Callable[[], None]] = None,
    ):
        self.speech_provider = get_speech_provider(stt_provider_name)
        self.tts_provider = get_tts_provider(tts_provider_name)
        self.vad = get_default_vad()
        self.wake_engine = NoopWakeWordEngine()

        self._on_transcript = on_transcript
        self._on_state_change = on_state_change
        self._on_interrupt = on_interrupt

        self.interrupt_flag = InterruptFlag()
        self._state = AudioStreamState.IDLE
        self._audio_buffer = bytearray()
        self._silence_duration = 0.0
        self._last_speech_time = 0.0
        self._speech_timeout = 0.8  # seconds of silence before considering speech ended

    @property
    def state(self) -> AudioStreamState:
        return self._state

    def _set_state(self, new_state: AudioStreamState):
        self._state = new_state
        if self._on_state_change:
            try:
                self._on_state_change(new_state)
            except Exception:
                logger.exception("State change callback failed")

    async def feed_audio(self, chunk: bytes) -> Optional[str]:
        """Feed an audio chunk into the pipeline.

        Returns a transcript when speech segment is complete, or None.
        Interrupts if speech is detected while in SPEAKING state.
        """
        # Check for interrupt: if speaking and speech detected, trigger interrupt
        if self._state == AudioStreamState.SPEAKING:
            if self.vad.is_speech(chunk):
                logger.info("Interrupt detected during TTS playback")
                self.interrupt_flag.set()
                self._set_state(AudioStreamState.INTERRUPTED)
                if self._on_interrupt:
                    try:
                        self._on_interrupt()
                    except Exception:
                        logger.exception("Interrupt callback failed")
                # Continue buffering the interrupting speech
                self._set_state(AudioStreamState.LISTENING)
                self._audio_buffer.extend(chunk)
                self._last_speech_time = time.time()
                return None

        # Wake word detection
        try:
            wake = await self.wake_engine.feed_audio(chunk)
            if wake and self._state == AudioStreamState.IDLE:
                logger.info("Wake word detected: %s", wake)
                self._set_state(AudioStreamState.LISTENING)
                self._audio_buffer.clear()
        except Exception:
            logger.exception("Wake engine error")

        if self._state not in (AudioStreamState.LISTENING, AudioStreamState.IDLE):
            return None

        self._audio_buffer.extend(chunk)

        if self.vad.is_speech(chunk):
            self._last_speech_time = time.time()
            self._silence_duration = 0.0
            if self._state == AudioStreamState.IDLE:
                self._set_state(AudioStreamState.LISTENING)
            return None

        # Check for silence timeout
        if self._last_speech_time > 0:
            self._silence_duration = time.time() - self._last_speech_time
            if self._silence_duration > self._speech_timeout and len(self._audio_buffer) > 0:
                # Speech segment complete
                buf = bytes(self._audio_buffer)
                self._audio_buffer.clear()
                self._last_speech_time = 0.0
                self._silence_duration = 0.0
                self._set_state(AudioStreamState.PROCESSING)

                try:
                    transcript = await self.speech_provider.transcribe(buf)
                    if transcript and transcript.strip():
                        logger.info("Transcribed: %s", transcript[:100])
                        if self._on_transcript:
                            try:
                                self._on_transcript(transcript)
                            except Exception:
                                logger.exception("Transcript callback failed")
                        self._set_state(AudioStreamState.IDLE)
                        return transcript
                except Exception:
                    logger.exception("Transcription failed")

                self._set_state(AudioStreamState.IDLE)
                return None

        return None

    def start_push_to_talk(self):
        """Start listening (push-to-talk mode)."""
        self._audio_buffer.clear()
        self._last_speech_time = 0.0
        self._silence_duration = 0.0
        self._set_state(AudioStreamState.LISTENING)

    def stop_push_to_talk(self) -> Optional[bytes]:
        """Stop listening and return buffered audio for final transcription."""
        self._set_state(AudioStreamState.PROCESSING)
        buf = bytes(self._audio_buffer) if self._audio_buffer else None
        self._audio_buffer.clear()
        self._set_state(AudioStreamState.IDLE)
        return buf

    def set_speaking(self):
        """Mark as speaking (TTS playback in progress)."""
        self._set_state(AudioStreamState.SPEAKING)

    def set_idle(self):
        """Return to idle state."""
        self.interrupt_flag.clear()
        self._set_state(AudioStreamState.IDLE)

    def reset(self):
        """Full reset of state and buffers."""
        self._audio_buffer.clear()
        self._last_speech_time = 0.0
        self._silence_duration = 0.0
        self.interrupt_flag.clear()
        self._set_state(AudioStreamState.IDLE)

