"""Audio IO helpers: microphone manager, audio routing, device discovery.

This module intentionally provides safe, test-friendly stubs for audio device
management. In production, these can be extended to use pyaudio, sounddevice,
wasapi, or platform-specific APIs. The key is to centralize audio device state
so the rest of the voice subsystem can perform automatic switching, headset
detection, and routing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Callable
import asyncio
import time

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class AudioDevice:
    id: str
    name: str
    is_input: bool
    is_default: bool = False


class MicrophoneManager:
    """Simple microphone manager: maintains a list of devices and allows
    switching. Implementations should integrate with platform audio APIs.
    """

    def __init__(self):
        # Start with a single default pseudo-device
        self._devices = [AudioDevice(id="default", name="default-mic", is_input=True, is_default=True)]
        self._active_device = self._devices[0]
        self._callbacks: List[Callable[[AudioDevice], None]] = []

    def list_devices(self) -> List[AudioDevice]:
        return list(self._devices)

    def get_active(self) -> AudioDevice:
        return self._active_device

    def set_active(self, device_id: str) -> Optional[AudioDevice]:
        for d in self._devices:
            if d.id == device_id:
                self._active_device = d
                for cb in self._callbacks:
                    try:
                        cb(d)
                    except Exception:
                        logger.exception("mic callback failed")
                return d
        return None

    def on_change(self, cb: Callable[[AudioDevice], None]) -> None:
        self._callbacks.append(cb)

    # Device detection stub
    async def detect_headset(self) -> Optional[AudioDevice]:
        await asyncio.sleep(0)
        return None


# Single global manager instance used by the voice subsystem
_global_mic_manager: Optional[MicrophoneManager] = None


def get_microphone_manager() -> MicrophoneManager:
    global _global_mic_manager
    if _global_mic_manager is None:
        _global_mic_manager = MicrophoneManager()
    return _global_mic_manager
