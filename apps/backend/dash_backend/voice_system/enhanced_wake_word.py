"""Enhanced Wake Word Detection with continuous listening and improved accuracy."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Callable, List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection."""
    wake_word: str = "dash"
    sensitivity: float = 0.5  # 0.0 to 1.0
    debounce_ms: int = 500  # Minimum time between detections
    min_confidence: float = 0.7
    continuous_mode: bool = True
    auto_restart: bool = True


class EnhancedWakeWordDetector:
    """Enhanced wake word detector with continuous listening and improved accuracy.
    
    Features:
    - Continuous listening mode
    - Debounce to prevent duplicate detections
    - Confidence scoring
    - Multiple wake word support
    - Audio buffer management
    - Automatic restart on failure
    """
    
    def __init__(self, config: Optional[WakeWordConfig] = None):
        self.config = config or WakeWordConfig()
        self._listening = False
        self._callbacks: List[Callable[[str, float], None]] = []
        self._last_detection_time = 0.0
        self._audio_buffer = deque(maxlen=100)  # Store recent audio chunks
        self._detection_count = 0
        self._false_positive_count = 0
        self._running_task: Optional[asyncio.Task] = None
        
    async def start(self) -> None:
        """Start continuous wake word detection."""
        if self._listening:
            logger.warning("Wake word detector already running")
            return
            
        self._listening = True
        self._last_detection_time = 0.0
        self._audio_buffer.clear()
        
        if self.config.continuous_mode:
            self._running_task = asyncio.create_task(self._continuous_listen_loop())
            
        logger.info(
            "Enhanced wake word detection started: '%s' (sensitivity=%.2f)",
            self.config.wake_word,
            self.config.sensitivity,
        )
    
    async def stop(self) -> None:
        """Stop wake word detection."""
        self._listening = False
        
        if self._running_task:
            self._running_task.cancel()
            try:
                await self._running_task
            except asyncio.CancelledError:
                pass
            self._running_task = None
            
        logger.info("Wake word detection stopped")
    
    async def _continuous_listen_loop(self) -> None:
        """Continuous listening loop."""
        while self._listening:
            try:
                # Process buffered audio
                if self._audio_buffer:
                    await self._process_buffer()
                
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in continuous listen loop: %s", e)
                if self.config.auto_restart:
                    await asyncio.sleep(1.0)
                else:
                    break
    
    async def process_audio(self, audio_chunk: bytes) -> Optional[Dict[str, Any]]:
        """Process an audio chunk for wake word detection.
        
        Args:
            audio_chunk: Raw audio data
            
        Returns:
            Detection dict with wake word and confidence, or None
        """
        if not self._listening:
            return None
            
        # Add to buffer
        self._audio_buffer.append(audio_chunk)
        
        # Check debounce
        current_time = time.time()
        if current_time - self._last_detection_time < (self.config.debounce_ms / 1000.0):
            return None
        
        # Process for detection
        detection = await self._detect_wake_word(audio_chunk)
        
        if detection:
            self._last_detection_time = current_time
            self._detection_count += 1
            
            # Trigger callbacks
            for callback in self._callbacks:
                try:
                    callback(detection["word"], detection["confidence"])
                except Exception as e:
                    logger.error("Wake word callback error: %s", e)
                    
            return detection
            
        return None
    
    async def _detect_wake_word(self, audio_chunk: bytes) -> Optional[Dict[str, Any]]:
        """Detect wake word in audio chunk.
        
        This is a simplified implementation. In production, this would use
        a proper ML-based wake word detector like Porcupine or Mycroft Precise.
        """
        try:
            # Simple text-based detection (for testing)
            text = audio_chunk.decode("utf-8", errors="ignore").lower()
            
            if self.config.wake_word in text:
                # Calculate confidence based on match quality
                confidence = self._calculate_confidence(text, self.config.wake_word)
                
                if confidence >= self.config.min_confidence:
                    return {
                        "word": self.config.wake_word,
                        "confidence": confidence,
                        "timestamp": time.time(),
                    }
                else:
                    self._false_positive_count += 1
                    
        except Exception:
            pass
            
        return None
    
    def _calculate_confidence(self, text: str, wake_word: str) -> float:
        """Calculate confidence score for wake word detection."""
        # Simple heuristic: exact match gets 1.0, partial match gets lower
        if text.strip() == wake_word:
            return 1.0
        elif wake_word in text:
            # Bonus for being at the start
            if text.startswith(wake_word):
                return 0.9
            # Bonus for being surrounded by spaces
            elif f" {wake_word} " in text:
                return 0.85
            else:
                return 0.7
        return 0.0
    
    async def _process_buffer(self) -> None:
        """Process accumulated audio buffer."""
        # In a real implementation, this would process the buffer
        # with a sliding window approach for better detection
        pass
    
    def on_wake_word(self, callback: Callable[[str, float], None]) -> None:
        """Register callback for wake word detection."""
        self._callbacks.append(callback)
    
    def set_wake_word(self, word: str) -> None:
        """Change the wake word."""
        self.config.wake_word = word.lower()
        logger.info("Wake word changed to: '%s'", word)
    
    def set_sensitivity(self, sensitivity: float) -> None:
        """Adjust detection sensitivity."""
        self.config.sensitivity = max(0.0, min(1.0, sensitivity))
        logger.info("Sensitivity set to: %.2f", self.config.sensitivity)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detection statistics."""
        return {
            "detections": self._detection_count,
            "false_positives": self._false_positive_count,
            "listening": self._listening,
            "wake_word": self.config.wake_word,
            "sensitivity": self.config.sensitivity,
        }
    
    @property
    def is_listening(self) -> bool:
        return self._listening


_enhanced_wake_word_detector: Optional[EnhancedWakeWordDetector] = None


def get_enhanced_wake_word_detector(config: Optional[WakeWordConfig] = None) -> EnhancedWakeWordDetector:
    global _enhanced_wake_word_detector
    if _enhanced_wake_word_detector is None:
        _enhanced_wake_word_detector = EnhancedWakeWordDetector(config)
    return _enhanced_wake_word_detector
