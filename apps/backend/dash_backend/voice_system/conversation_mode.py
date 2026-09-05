"""Conversation Mode - Natural back-and-forth voice interaction."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """States of conversation mode."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class ConversationConfig:
    """Configuration for conversation mode."""
    auto_continue: bool = True  # Continue listening after response
    turn_timeout_ms: int = 30000  # Max time per turn
    silence_threshold_ms: int = 1500  # Silence before processing
    enable_interruption: bool = True
    max_turns: int = 100  # Maximum conversation turns


class ConversationMode:
    """Manages natural back-and-forth voice conversation.
    
    Features:
    - Automatic turn-taking
    - Silence detection
    - Interruption handling
    - Context maintenance
    - Timeout management
    """
    
    def __init__(self, config: Optional[ConversationConfig] = None):
        self.config = config or ConversationConfig()
        self._state = ConversationState.IDLE
        self._turn_count = 0
        self._conversation_history: list[Dict[str, Any]] = []
        self._on_user_speech: Optional[Callable[[str], None]] = None
        self._on_assistant_response: Optional[Callable[[str], None]] = None
        self._on_state_change: Optional[Callable[[ConversationState], None]] = None
        self._running = False
        self._current_task: Optional[asyncio.Task] = None
        
    async def start(self) -> None:
        """Start conversation mode."""
        if self._running:
            logger.warning("Conversation mode already running")
            return
            
        self._running = True
        self._state = ConversationState.LISTENING
        self._turn_count = 0
        self._conversation_history.clear()
        
        self._notify_state_change()
        
        if self.config.auto_continue:
            self._current_task = asyncio.create_task(self._conversation_loop())
            
        logger.info("Conversation mode started")
    
    async def stop(self) -> None:
        """Stop conversation mode."""
        self._running = False
        
        if self._current_task:
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
            self._current_task = None
            
        self._state = ConversationState.IDLE
        self._notify_state_change()
        
        logger.info("Conversation mode stopped (total turns: %d)", self._turn_count)
    
    async def _conversation_loop(self) -> None:
        """Main conversation loop."""
        while self._running and self._turn_count < self.config.max_turns:
            try:
                # Listen for user input
                await self._set_state(ConversationState.LISTENING)
                user_input = await self._listen_for_user()
                
                if not user_input:
                    # Timeout or silence, continue listening
                    continue
                    
                # Process user input
                await self._set_state(ConversationState.PROCESSING)
                response = await self._process_user_input(user_input)
                
                if response:
                    # Speak response
                    await self._set_state(ConversationState.SPEAKING)
                    await self._speak_response(response)
                    
                    # Record conversation
                    self._conversation_history.append({
                        "role": "user",
                        "content": user_input,
                    })
                    self._conversation_history.append({
                        "role": "assistant",
                        "content": response,
                    })
                    
                    self._turn_count += 1
                    
                # Small pause before next turn
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in conversation loop: %s", e)
                await asyncio.sleep(1.0)
    
    async def _listen_for_user(self) -> Optional[str]:
        """Listen for user speech via the microphone and transcribe it."""
        try:
            import wave

            import speech_recognition as sr

            recognizer = sr.Recognizer()
            recognizer.pause_threshold = self.config.silence_threshold_ms / 1000.0
            loop = asyncio.get_running_loop()

            def _capture() -> bytes:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = recognizer.listen(
                        source, timeout=self.config.turn_timeout_ms / 1000.0
                    )
                return audio.get_wav_data()

            wav_bytes = await loop.run_in_executor(None, _capture)
            if not wav_bytes:
                return None

            from dash_backend.voice import transcribe_audio

            text = await transcribe_audio(wav_bytes)
            return text.strip() or None
        except ModuleNotFoundError as exc:
            logger.error("Voice dependency missing: %s", exc)
            return None
        except Exception as e:
            logger.debug("Listen ended without transcript: %s", e)
            return None
    
    async def _process_user_input(self, user_input: str) -> Optional[str]:
        """Process user input and generate a response via the LLM."""
        if self._on_user_speech:
            try:
                self._on_user_speech(user_input)
            except Exception as e:
                logger.error("User speech callback error: %s", e)

        try:
            from dash_backend.llm.service import build_chat_messages, collect_streamed_response

            history = [
                {"role": str(m.get("role")), "content": str(m.get("content"))}
                for m in self._conversation_history[-10:]
            ]
            messages = build_chat_messages(
                system_prompt=(
                    "You are DASH, a helpful voice assistant. Reply conversationally "
                    "and concisely (2-4 sentences) unless asked for detail."
                ),
                history=history,
                user_message=user_input,
            )
            response = await collect_streamed_response(messages)
            return response.strip() or None
        except Exception as e:
            logger.error("LLM response failed: %s", e)
            return None
    
    async def _speak_response(self, response: str) -> None:
        """Speak the assistant's response via TTS."""
        if self._on_assistant_response:
            try:
                self._on_assistant_response(response)
            except Exception as e:
                logger.error("Assistant response callback error: %s", e)

        # Best-effort local playback; callbacks above already delivered the text.
        try:
            import base64
            import os
            import tempfile

            from dash_backend.voice import synthesize_text

            audio_b64 = await synthesize_text(response)
            if not audio_b64:
                logger.debug("TTS returned no audio; skipping playback")
                return

            wav_bytes = base64.b64decode(audio_b64)
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                f.write(wav_bytes)

            import platform as _platform

            loop = asyncio.get_running_loop()
            system = _platform.system()
            try:
                if system == "Windows":
                    import winsound

                    await loop.run_in_executor(
                        None, lambda: winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
                    )
                elif system == "Darwin":
                    proc = await asyncio.create_subprocess_exec("afplay", tmp_path)
                    await proc.wait()
                else:
                    proc = await asyncio.create_subprocess_exec("aplay", tmp_path)
                    await proc.wait()
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception as e:
            logger.debug("TTS playback unavailable: %s", e)
    
    async def _set_state(self, state: ConversationState) -> None:
        """Set conversation state and notify callbacks."""
        self._state = state
        self._notify_state_change()
    
    def _notify_state_change(self) -> None:
        """Notify state change callbacks."""
        if self._on_state_change:
            try:
                self._on_state_change(self._state)
            except Exception as e:
                logger.error("State change callback error: %s", e)
    
    def on_user_speech(self, callback: Callable[[str], None]) -> None:
        """Register callback for user speech."""
        self._on_user_speech = callback
    
    def on_assistant_response(self, callback: Callable[[str], None]) -> None:
        """Register callback for assistant response."""
        self._on_assistant_response = callback
    
    def on_state_change(self, callback: Callable[[ConversationState], None]) -> None:
        """Register callback for state changes."""
        self._on_state_change = callback
    
    def interrupt(self) -> None:
        """Interrupt current turn."""
        if self._state == ConversationState.SPEAKING and self.config.enable_interruption:
            self._state = ConversationState.INTERRUPTED
            self._notify_state_change()
            logger.info("Conversation interrupted")
    
    def get_conversation_history(self) -> list[Dict[str, Any]]:
        """Get the conversation history."""
        return self._conversation_history.copy()
    
    @property
    def state(self) -> ConversationState:
        return self._state
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def turn_count(self) -> int:
        return self._turn_count


_conversation_mode: Optional[ConversationMode] = None


def get_conversation_mode(config: Optional[ConversationConfig] = None) -> ConversationMode:
    global _conversation_mode
    if _conversation_mode is None:
        _conversation_mode = ConversationMode(config)
    return _conversation_mode
