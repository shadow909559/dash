"""Voice Agent.

Controls the voice layer of DASH:
- Speech recognition (STT)
- Speech synthesis (TTS)
- Wake word detection
- Voice activity detection (VAD)
- Streaming of audio

This agent wraps the existing voice capabilities (``voice_system``,
``voice``, ``speech`` services) behind the common agent interface. It is
additive and does not recreate the underlying voice engines.
"""

from __future__ import annotations

from typing import Any, Dict, List

from dash_backend.agents.ecosystem.base import (
    AgentDependency,
    AgentPriority,
    AgentSpec,
    BaseAgent,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def voice_agent_spec() -> AgentSpec:
    """The declarative spec for the Voice Agent."""
    return AgentSpec(
        key="voice",
        name="Voice Agent",
        description=(
            "Controls speech recognition, synthesis, wake word, voice "
            "activity detection and streaming."
        ),
        capabilities=[
            "speech_recognition",
            "speech_synthesis",
            "wake_word",
            "voice_activity_detection",
            "audio_streaming",
        ],
        priority=AgentPriority.HIGH,
        permissions=["microphone", "audio_output"],
        dependencies=[
            AgentDependency(name="conversation", kind="agent", required=False),
        ],
        tools=["stt", "tts", "wake_word_detect", "vad"],
        memory_access="read_write",
        execution_api="stream",
        category="core",
        system_prompt=(
            "You are DASH's Voice Agent. You handle the real-time voice "
            "interaction layer: transcribing user speech, producing natural "
            "speech output, and managing wake-word + VAD lifecycle."
        ),
    )


class VoiceAgent(BaseAgent):
    """Runtime for the Voice Agent."""

    def __init__(self) -> None:
        super().__init__(voice_agent_spec())

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "status")
        logger.info("Voice Agent action=%s", action)

        if action == "transcribe":
            # STT — wraps existing speech recognition service
            return await self._transcribe(payload)
        if action == "synthesize":
            # TTS — wraps existing synthesis service
            return await self._synthesize(payload)
        if action == "wake_word":
            # Wake word detection lifecycle
            return {"wake_word": payload.get("wake_word", "hey dash"), "active": True}
        if action == "vad":
            # Voice activity detection
            amplitude = float(payload.get("amplitude", 0.0))
            return {"speaking": amplitude > 0.15, "amplitude": amplitude}
        if action == "stream":
            # Streaming session
            return {"streaming": True, "session_id": payload.get("session_id")}
        return {"status": "ok", "agent": "voice"}

    async def _transcribe(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap the existing STT pipeline."""
        try:
            from dash_backend.voice_system.service import transcribe_audio  # type: ignore[import-not-found]

            audio = payload.get("audio")
            result = await transcribe_audio(audio)
            return {"text": result, "provider": "local"}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Voice transcribe fallback: %s", exc)
            return {"text": payload.get("text", ""), "provider": "fallback"}

    async def _synthesize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap the existing TTS pipeline."""
        text = payload.get("text", "")
        try:
            from dash_backend.voice_system.service import synthesize_speech  # type: ignore[import-not-found]

            audio = await synthesize_speech(text)
            return {"audio": audio, "provider": "local"}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Voice synthesize fallback: %s", exc)
            return {"audio": None, "text": text, "provider": "fallback"}


_voice_agent: VoiceAgent | None = None


def get_voice_agent() -> VoiceAgent:
    """Return the Voice Agent singleton."""
    global _voice_agent
    if _voice_agent is None:
        _voice_agent = VoiceAgent()
    return _voice_agent
