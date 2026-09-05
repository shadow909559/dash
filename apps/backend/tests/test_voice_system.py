"""Tests for the voice subsystem (Phase 12)."""

from __future__ import annotations

import pytest

from dash_backend.voice_system.streaming import (
    StreamingVoiceProcessor,
    AudioStreamState,
    InterruptFlag,
)
from dash_backend.voice_system.parser import parse_command
from dash_backend.voice_system.vad import EnergyVAD, get_default_vad
from dash_backend.voice_system.wake_word import NoopWakeWordEngine, PhraseWakeWordEngine
from dash_backend.voice_system.profiles import VoiceProfileManager
from dash_backend.voice_system.providers import (
    get_speech_provider,
    get_tts_provider,
)


class TestInterruptFlag:
    def test_not_interrupted_by_default(self):
        flag = InterruptFlag()
        assert not flag.is_set

    def test_set_and_clear(self):
        flag = InterruptFlag()
        flag.set()
        assert flag.is_set
        flag.clear()
        assert not flag.is_set


class TestStreamingVoiceProcessor:
    @pytest.mark.asyncio
    async def test_initial_state_is_idle(self):
        processor = StreamingVoiceProcessor()
        assert processor.state == AudioStreamState.IDLE

    @pytest.mark.asyncio
    async def test_push_to_talk_state_transitions(self):
        processor = StreamingVoiceProcessor()
        processor.start_push_to_talk()
        assert processor.state == AudioStreamState.LISTENING

        buf = processor.stop_push_to_talk()
        assert processor.state == AudioStreamState.IDLE

    @pytest.mark.asyncio
    async def test_set_speaking_and_idle(self):
        processor = StreamingVoiceProcessor()
        processor.set_speaking()
        assert processor.state == AudioStreamState.SPEAKING

        processor.set_idle()
        assert processor.state == AudioStreamState.IDLE
        assert not processor.interrupt_flag.is_set

    @pytest.mark.asyncio
    async def test_reset_clears_buffers(self):
        processor = StreamingVoiceProcessor()
        processor.start_push_to_talk()
        processor.reset()
        assert processor.state == AudioStreamState.IDLE
        assert not processor.interrupt_flag.is_set

    def test_state_enum_values(self):
        assert AudioStreamState.IDLE.value == "idle"
        assert AudioStreamState.LISTENING.value == "listening"
        assert AudioStreamState.PROCESSING.value == "processing"
        assert AudioStreamState.SPEAKING.value == "speaking"
        assert AudioStreamState.INTERRUPTED.value == "interrupted"


class TestVoiceCommandParser:
    def test_parse_empty_text(self):
        result = parse_command("")
        assert result["intent"] == "empty"

    def test_parse_open_command(self):
        result = parse_command("open browser")
        assert result["intent"] == "open_url_or_app"
        assert result["args"]["target"] == "browser"

    def test_parse_search_command(self):
        result = parse_command("search for cats")
        assert result["intent"] == "search_web"
        assert result["args"]["query"] == "for cats"

        result = parse_command("search Python docs")
        assert result["intent"] == "search_web"
        # Parser lowercases the query
        assert result["args"]["query"].lower() == "python docs"

    def test_parse_time_command(self):
        result = parse_command("what's the time")
        assert result["intent"] == "get_time"

        result = parse_command("time")
        assert result["intent"] == "get_time"

    def test_parse_llm_fallback(self):
        result = parse_command("tell me a joke")
        assert result["intent"] == "llm_fallback"


class TestVAD:
    def test_energy_vad(self):
        vad = EnergyVAD(threshold=100.0)
        assert not vad.is_speech(b"\x00\x00" * 100)
        assert not vad.is_speech(b"")

    def test_default_vad_created(self):
        vad = get_default_vad()
        assert vad is not None
        assert hasattr(vad, "is_speech")


class TestWakeWordEngines:
    @pytest.mark.asyncio
    async def test_noop_never_triggers(self):
        engine = NoopWakeWordEngine()
        result = await engine.feed_audio(b"some audio data")
        assert result is None

    @pytest.mark.asyncio
    async def test_phrase_wake_word_detects_phrase(self):
        engine = PhraseWakeWordEngine(phrase="hey dash")
        result = await engine.feed_audio(b"hey dash what's up")
        assert result is not None
        assert result["phrase"] == "hey dash"

    @pytest.mark.asyncio
    async def test_phrase_wake_word_no_match(self):
        engine = PhraseWakeWordEngine(phrase="hey dash")
        result = await engine.feed_audio(b"hello world")
        assert result is None


class TestVoiceProfiles:
    def test_default_profile_exists(self):
        manager = VoiceProfileManager()
        profile = manager.get()
        assert profile.id == "default"
        assert profile.name == "default"

    def test_update_profile(self):
        manager = VoiceProfileManager()
        updated = manager.update("default", push_to_talk=True, vad_sensitivity=0.8)
        assert updated.push_to_talk is True
        assert updated.vad_sensitivity == 0.8

    def test_get_nonexistent_falls_back_to_default(self):
        manager = VoiceProfileManager()
        profile = manager.get("nonexistent")
        assert profile is not None
        assert profile.id == "default"

    def test_create_new_profile(self):
        manager = VoiceProfileManager()
        profile = manager.update("user-1", name="User 1", tts_voice="female")
        assert profile.id == "user-1"
        assert profile.tts_voice == "female"


class TestProviders:
    def test_get_speech_provider(self):
        provider = get_speech_provider("default")
        assert provider is not None

    def test_get_tts_provider(self):
        provider = get_tts_provider("default")
        assert provider is not None


class TestVoiceConversationManager:
    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        from dash_backend.voice_system.conversation import VoiceConversationManager
        manager = VoiceConversationManager(user_id="test-user")
        assert manager.user_id == "test-user"
        assert manager.processor is not None
        ctx = manager.get_recent_context()
        assert ctx["transcript_count"] == 0
        assert ctx["has_memory"] is False

