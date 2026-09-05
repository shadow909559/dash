"""Voice Activity Detection (VAD) abstraction.

Provides a small interface for detecting speech segments and silence. By
default uses a naive energy-based VAD (works without native libs) but can be
extended to use webrtcvad or other native implementations.
"""
from __future__ import annotations

import array
import sys
from dataclasses import dataclass

try:
    import numpy as _np
except ImportError:  # pragma: no cover - optional acceleration only
    _np = None

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

        Uses numpy when available; falls back to the stdlib ``array``
        module so this works with zero third-party dependencies.
        """
        try:
            if not audio_chunk:
                return False
            if _np is not None:
                arr = _np.frombuffer(audio_chunk, dtype=_np.int16)
                if arr.size == 0:
                    return False
                energy = float(_np.abs(arr).mean())
            else:
                buf = array.array("h")
                buf.frombytes(audio_chunk)
                if len(buf) == 0:
                    return False
                if sys.byteorder == "big":
                    buf.byteswap()
                energy = sum(abs(x) for x in buf) / len(buf)
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
