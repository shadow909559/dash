# -*- coding: utf-8 -*-
"""Voice Engine — Wake word, STT (Speech-to-Text), TTS (Text-to-Speech), Voice Commands."""

import logging
import time
import hashlib
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class VoiceCommand:
    """A recognized voice command."""
    id: str
    phrase: str
    intent: str
    parameters: dict = field(default_factory=dict)
    confidence: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class VoiceMemo:
    """A recorded voice memo."""
    id: str
    text: str
    duration_seconds: float = 0.0
    language: str = "en"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)


class VoiceEngine:
    """Complete voice processing engine."""

    WAKE_WORDS = ["hey dash", "ok dash", "dash"]

    VOICE_COMMANDS = {
        "open": {"intent": "open_app", "params": ["app_name"]},
        "close": {"intent": "close_app", "params": ["app_name"]},
        "search": {"intent": "search", "params": ["query"]},
        "remember": {"intent": "create_memory", "params": ["content"]},
        "schedule": {"intent": "create_event", "params": ["event", "time"]},
        "remind": {"intent": "create_reminder", "params": ["task", "time"]},
        "translate": {"intent": "translate", "params": ["text", "language"]},
        "summarize": {"intent": "summarize", "params": ["text"]},
        "write": {"intent": "write_text", "params": ["content"]},
        "read": {"intent": "read_text", "params": ["source"]},
        "screenshot": {"intent": "take_screenshot", "params": []},
        "volume": {"intent": "set_volume", "params": ["level"]},
        "play": {"intent": "play_media", "params": ["media"]},
        "pause": {"intent": "pause_media", "params": []},
        "stop": {"intent": "stop_media", "params": []},
        "settings": {"intent": "open_settings", "params": ["section"]},
        "help": {"intent": "show_help", "params": []},
    }

    SUPPORTED_LANGUAGES = [
        "en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko",
        "ar", "hi", "ru", "nl", "sv", "pl", "tr", "vi", "th",
    ]

    def __init__(self):
        self._wake_word_enabled = True
        self._wake_word_sensitivity = 0.7
        self._stt_language = "en"
        self._tts_voice = "default"
        self._tts_rate = 1.0
        self._tts_pitch = 1.0
        self._continuous_listening = False
        self._memos: list[VoiceMemo] = []
        self._command_history: list[VoiceCommand] = []
        self._wake_word_detections: list[dict] = []

    # ── Wake Word ────────────────────────────────────────────────────────

    def configure_wake_word(self, enabled: bool = True, sensitivity: float = 0.7) -> dict:
        """Configure wake word detection."""
        self._wake_word_enabled = enabled
        self._wake_word_sensitivity = max(0.0, min(1.0, sensitivity))
        return {
            "enabled": self._wake_word_enabled,
            "sensitivity": self._wake_word_sensitivity,
            "wake_words": self.WAKE_WORDS,
        }

    def detect_wake_word(self, audio_text: str) -> dict:
        """Check if audio text contains a wake word."""
        text_lower = audio_text.lower().strip()
        for wake_word in self.WAKE_WORDS:
            if wake_word in text_lower:
                command_text = text_lower.replace(wake_word, "").strip()
                self._wake_word_detections.append({
                    "wake_word": wake_word,
                    "command_text": command_text,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return {
                    "detected": True,
                    "wake_word": wake_word,
                    "command_text": command_text,
                }
        return {"detected": False}

    def get_wake_word_detections(self, limit: int = 50) -> list[dict]:
        """Get recent wake word detections."""
        return self._wake_word_detections[-limit:]

    # ── Speech-to-Text ───────────────────────────────────────────────────

    def configure_stt(self, language: str = "en", model: str = "base") -> dict:
        """Configure speech-to-text settings."""
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        self._stt_language = language
        return {"language": language, "model": model, "status": "configured"}

    async def transcribe(self, audio_data: bytes = None, text_hint: str = "") -> dict:
        """Transcribe audio to text. In production, uses Whisper or similar."""
        if text_hint:
            text = text_hint
        else:
            # Mock transcription — in production, call Whisper API
            text = "[transcribed audio]"

        result = {
            "text": text,
            "language": self._stt_language,
            "confidence": 0.95 if text_hint else 0.85,
            "duration_ms": len(text) * 50,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return result

    # ── Text-to-Speech ───────────────────────────────────────────────────

    def configure_tts(self, voice: str = "default", rate: float = 1.0, pitch: float = 1.0) -> dict:
        """Configure text-to-speech settings."""
        self._tts_voice = voice
        self._tts_rate = max(0.5, min(3.0, rate))
        self._tts_pitch = max(0.5, min(2.0, pitch))
        return {
            "voice": self._tts_voice,
            "rate": self._tts_rate,
            "pitch": self._tts_pitch,
        }

    async def synthesize(self, text: str, voice: str = None) -> dict:
        """Synthesize text to speech. Returns audio data reference."""
        voice = voice or self._tts_voice
        return {
            "text": text,
            "voice": voice,
            "rate": self._tts_rate,
            "pitch": self._tts_pitch,
            "audio_ref": f"tts_{hashlib.md5(text.encode()).hexdigest()[:12]}",
            "duration_ms": len(text) * 60,
            "format": "mp3",
        }

    # ── Voice Commands ───────────────────────────────────────────────────

    def parse_command(self, text: str) -> dict:
        """Parse voice text into a structured command."""
        text_lower = text.lower().strip()

        for trigger, cmd_def in self.VOICE_COMMANDS.items():
            if text_lower.startswith(trigger):
                remainder = text_lower[len(trigger):].strip()
                params = {}
                for i, param_name in enumerate(cmd_def["params"]):
                    words = remainder.split()
                    if i < len(words):
                        params[param_name] = words[i] if len(words) == 1 else " ".join(words[i:i+3])

                cmd = VoiceCommand(
                    id=hashlib.md5(text.encode()).hexdigest()[:16],
                    phrase=text,
                    intent=cmd_def["intent"],
                    parameters=params,
                    confidence=0.9,
                )
                self._command_history.append(cmd)
                return {
                    "recognized": True,
                    "intent": cmd.intent,
                    "parameters": cmd.parameters,
                    "confidence": cmd.confidence,
                    "command_id": cmd.id,
                }

        return {
            "recognized": False,
            "phrase": text,
            "suggestion": "Try: 'open', 'search', 'remember', 'schedule', 'remind'",
        }

    def get_command_history(self, limit: int = 50) -> list[dict]:
        """Get recent voice command history."""
        return [
            {
                "id": c.id,
                "phrase": c.phrase,
                "intent": c.intent,
                "parameters": c.parameters,
                "confidence": c.confidence,
                "timestamp": c.timestamp,
            }
            for c in self._command_history[-limit:]
        ]

    # ── Voice Memos ──────────────────────────────────────────────────────

    def create_memo(self, text: str, duration: float = 0.0, language: str = None, tags: list[str] = None) -> dict:
        """Create a voice memo."""
        memo = VoiceMemo(
            id=hashlib.md5(text.encode()).hexdigest()[:16],
            text=text,
            duration_seconds=duration,
            language=language or self._stt_language,
            tags=tags or [],
        )
        self._memos.append(memo)
        return {
            "id": memo.id,
            "text": memo.text,
            "duration": memo.duration_seconds,
            "language": memo.language,
            "tags": memo.tags,
            "created_at": memo.created_at,
        }

    def get_memos(self, language: str = None, limit: int = 50) -> list[dict]:
        """Get voice memos."""
        memos = self._memos
        if language:
            memos = [m for m in memos if m.language == language]
        return [
            {
                "id": m.id,
                "text": m.text,
                "duration": m.duration_seconds,
                "language": m.language,
                "tags": m.tags,
                "created_at": m.created_at,
            }
            for m in memos[-limit:]
        ]

    def delete_memo(self, memo_id: str) -> dict:
        """Delete a voice memo."""
        before = len(self._memos)
        self._memos = [m for m in self._memos if m.id != memo_id]
        return {"deleted": before > len(self._memos), "memo_id": memo_id}

    # ── Continuous Listening ─────────────────────────────────────────────

    def set_continuous_listening(self, enabled: bool) -> dict:
        """Toggle continuous listening mode."""
        self._continuous_listening = enabled
        return {"continuous_listening": enabled}

    def get_status(self) -> dict:
        """Get voice engine status."""
        return {
            "wake_word_enabled": self._wake_word_enabled,
            "wake_word_sensitivity": self._wake_word_sensitivity,
            "stt_language": self._stt_language,
            "tts_voice": self._tts_voice,
            "tts_rate": self._tts_rate,
            "continuous_listening": self._continuous_listening,
            "supported_languages": self.SUPPORTED_LANGUAGES,
            "total_memos": len(self._memos),
            "total_commands": len(self._command_history),
        }


# Singleton
_voice_engine: Optional[VoiceEngine] = None


def get_voice_engine() -> VoiceEngine:
    global _voice_engine
    if _voice_engine is None:
        _voice_engine = VoiceEngine()
    return _voice_engine
