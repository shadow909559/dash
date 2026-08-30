"""Enhanced Streaming TTS with interrupt support and audio management."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator, Callable, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TTSConfig:
    """Configuration for TTS."""
    provider: str = "piper"
    voice: str = "en_US-lessac-medium"
    sample_rate: int = 22050
    speed: float = 1.0
    volume: float = 1.0
    enable_interrupt: bool = True


class EnhancedStreamingTTS:
    """Enhanced streaming TTS with interrupt support and audio management.
    
    Features:
    - Streaming text-to-speech
    - Interrupt capability
    - Voice selection
    - Speed and volume control
    - Audio chunk management
    - Error recovery
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self._is_speaking = False
        self._interrupt_requested = False
        self._current_task: Optional[asyncio.Task] = None
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
        self._callbacks: List[Callable[[bytes], None]] = []
        
    async def synthesize_streaming(
        self,
        text: str,
        chunk_size: int = 1024,
    ) -> AsyncIterator[bytes]:
        """Synthesize text to speech with streaming output.
        
        Args:
            text: Text to synthesize
            chunk_size: Size of audio chunks to yield
            
        Yields:
            Audio chunks as bytes
        """
        if not text or not text.strip():
            return
            
        self._is_speaking = True
        self._interrupt_requested = False
        
        try:
            # Get audio from provider
            audio = await self._get_audio_from_provider(text)
            
            if not audio:
                logger.warning("TTS produced empty audio for: %s", text[:50])
                return
                
            # Stream in chunks
            for i in range(0, len(audio), chunk_size):
                if self._interrupt_requested:
                    logger.info("TTS interrupted during streaming")
                    break
                    
                chunk = audio[i:i + chunk_size]
                yield chunk
                
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(chunk)
                    except Exception as e:
                        logger.error("TTS callback error: %s", e)
                        
        except Exception as e:
            logger.error("TTS streaming error: %s", e)
        finally:
            self._is_speaking = False
            self._interrupt_requested = False
    
    async def synthesize(self, text: str) -> Optional[bytes]:
        """Synthesize text to speech (non-streaming).
        
        Args:
            text: Text to synthesize
            
        Returns:
            Complete audio as bytes
        """
        if not text or not text.strip():
            return None
            
        try:
            return await self._get_audio_from_provider(text)
        except Exception as e:
            logger.error("TTS synthesis error: %s", e)
            return None
    
    async def _get_audio_from_provider(self, text: str) -> Optional[bytes]:
        """Get audio from configured TTS provider."""
        try:
            from dash_backend.voice import get_provider
            provider = get_provider("tts", self.config.provider)
            
            if provider and hasattr(provider, "synthesize"):
                return await provider.synthesize(text)
            else:
                logger.error("TTS provider '%s' not available", self.config.provider)
                return None
                
        except Exception as e:
            logger.error("Error getting audio from provider: %s", e)
            return None
    
    async def interrupt(self) -> None:
        """Interrupt current TTS playback."""
        if not self.config.enable_interrupt:
            return
            
        self._interrupt_requested = True
        
        if self._current_task:
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
            self._current_task = None
            
        # Try to interrupt provider directly
        try:
            from dash_backend.voice import get_provider
            provider = get_provider("tts", self.config.provider)
            if provider and hasattr(provider, "interrupt"):
                provider.interrupt()
        except Exception as e:
            logger.error("Error interrupting provider: %s", e)
            
        logger.info("TTS playback interrupted")
    
    def on_audio_chunk(self, callback: Callable[[bytes], None]) -> None:
        """Register callback for audio chunks."""
        self._callbacks.append(callback)
    
    def set_voice(self, voice: str) -> None:
        """Change the TTS voice."""
        self.config.voice = voice
        logger.info("TTS voice changed to: %s", voice)
    
    def set_speed(self, speed: float) -> None:
        """Set speech speed."""
        self.config.speed = max(0.5, min(2.0, speed))
        logger.info("TTS speed set to: %.2f", self.config.speed)
    
    def set_volume(self, volume: float) -> None:
        """Set volume."""
        self.config.volume = max(0.0, min(1.0, volume))
        logger.info("TTS volume set to: %.2f", self.config.volume)
    
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
    
    @property
    def is_interrupted(self) -> bool:
        return self._interrupt_requested


_enhanced_streaming_tts: Optional[EnhancedStreamingTTS] = None


def get_enhanced_streaming_tts(config: Optional[TTSConfig] = None) -> EnhancedStreamingTTS:
    global _enhanced_streaming_tts
    if _enhanced_streaming_tts is None:
        _enhanced_streaming_tts = EnhancedStreamingTTS(config)
    return _enhanced_streaming_tts
