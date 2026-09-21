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
            return await self._transcribe(payload)
        if action == "synthesize":
            return await self._synthesize(payload)
        if action == "wake_word":
            # REAL state from the always-listening loop — never fabricated.
            from dash_backend.voice_system.always_listening import get_wake_loop

            status = get_wake_loop().get_status()
            return {
                "wake_word": status.get("wake_word") or payload.get("wake_word", "hey dash"),
                "active": bool(status.get("running")),
                "state": status.get("state"),
                "detail": status.get("detail"),
                "last_wake_at": status.get("last_wake_at"),
            }
        if action == "vad":
            # Honest threshold computation on the caller-supplied amplitude.
            amplitude = float(payload.get("amplitude", 0.0))
            return {"speaking": amplitude > 0.15, "amplitude": amplitude}
        if action == "stream":
            return await self._stream(payload)
        return {"status": "ok", "agent": "voice"}

    async def _stream(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Start/stop a REAL voice session via the VoiceManager."""
        from dash_backend.voice_system.service import get_voice_manager

        session_id = str(payload.get("session_id") or "")
        if not session_id:
            raise ValueError("stream requires a session_id")
        manager = get_voice_manager()
        if str(payload.get("mode") or "start") == "stop":
            manager.stop_session(session_id)
            return {"streaming": False, "session_id": session_id, "stopped": True}
        manager.start_session(session_id, user_id=payload.get("user_id"))
        return {
            "streaming": True,
            "session_id": session_id,
            "active": manager.get_session(session_id) is not None,
        }

    async def _transcribe(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Transcribe real audio bytes through the real speech provider.

        The old fallback echoed the caller-supplied ``text`` back as a
        "transcription" — fabricated output. Now: no audio or no configured
        provider raises instead of lying.
        """
        import base64

        from dash_backend.voice_system.providers import get_speech_provider

        audio = payload.get("audio")
        if not audio:
            raise ValueError("transcribe requires audio bytes (base64 or raw)")
        data = base64.b64decode(audio) if isinstance(audio, str) else bytes(audio)
        provider = get_speech_provider(payload.get("provider"))
        if getattr(provider, "provider", None) is None:
            raise ValueError("no speech provider configured")
        text = await provider.transcribe(data)
        return {"text": text, "provider": "speech"}

    async def _synthesize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize real speech through the real TTS provider.

        No provider configured raises — the old fallback returned
        ``{"audio": None, "provider": "fallback"}`` which callers could
        mistake for a real synthesis.
        """
        from dash_backend.voice_system.providers import get_tts_provider

        text = str(payload.get("text") or "")
        if not text:
            raise ValueError("synthesize requires text")
        provider = get_tts_provider(payload.get("provider"))
        if getattr(provider, "provider", None) is None:
            raise ValueError("no TTS provider configured")
        audio = await provider.synthesize(text)
        if not audio:
            raise ValueError("TTS provider returned no audio")
        return {"audio": audio, "audio_bytes": len(audio), "provider": "tts"}


_voice_agent: VoiceAgent | None = None


def get_voice_agent() -> VoiceAgent:
    """Return the Voice Agent singleton."""
    global _voice_agent
    if _voice_agent is None:
        _voice_agent = VoiceAgent()
    return _voice_agent
