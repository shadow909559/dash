"""Voice Activity Detection (VAD) abstraction.

Provides a small interface for detecting speech segments and silence. By
default uses a naive energy-based VAD (works without native libs) but can be
extended to use webrtcvad or other native implementations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as _np

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class VADSegment:
    start: float
    end: float
    confidence: float = 1.0


class VAD:
    name: str = "base"

    def is_speech(self, audio_chunk: bytes) -> bool:
        raise NotImplementedError


class EnergyVAD(VAD):
    name = "energy"

    def __init__(self, threshold: float = 500.0):
        self.threshold = threshold

    def is_speech(self, audio_chunk: bytes) -> bool:
        """Naive energy-based VAD. Expects 16-bit PCM little-endian audio.

        For short chunks this is coarse but provides a working default without
        adding native dependencies.
        """
        try:
            if not audio_chunk:
                return False
            arr = _np.frombuffer(audio_chunk, dtype=_np.int16)
            energy = float(_np.abs(arr).mean())
            return energy > self.threshold
        except Exception:
            return False


# Factory

def get_default_vad() -> VAD:
    try:
        # Prefer energy VAD
        return EnergyVAD()
    except Exception:
        return VAD()
