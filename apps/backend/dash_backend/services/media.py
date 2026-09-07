"""MediaService - volume, mute, brightness, media keys control."""

from __future__ import annotations

import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


def _endpoint_volume():
    """Return the IAudioEndpointVolume for the default speakers.

    Works with both pycaw API generations: legacy devices.Activate(...) and
    modern AudioDevice.EndpointVolume.
    """
    from pycaw.pycaw import AudioUtilities

    device = AudioUtilities.GetSpeakers()
    ev = getattr(device, "EndpointVolume", None)
    if ev is not None:
        return ev
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import IAudioEndpointVolume

    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


class MediaService(Singleton):
    """Control system media: volume, brightness, media keys."""

    async def get_volume(self) -> dict[str, Any]:
        """Get current system volume level (0-100)."""
        if not IS_WINDOWS:
            return {"volume": 0, "muted": False, "summary": "Volume control not supported on this platform"}
        try:
            volume = _endpoint_volume()
            current = volume.GetMasterVolumeLevelScalar() * 100
            muted = volume.GetMute()
            return {
                "volume": round(current, 1),
                "muted": bool(muted),
                "summary": f"Volume at {round(current, 1)}%{' (muted)' if muted else ''}",
            }
        except ImportError:
            logger.warning("pycaw not installed, volume control unavailable")
            return {"volume": 0, "muted": False, "summary": "Volume control requires pycaw"}
        except Exception as exc:
            logger.exception("get_volume failed")
            raise RuntimeError(f"Failed to get volume: {exc}") from exc

    async def set_volume(self, level: int) -> dict[str, Any]:
        """Set system volume level (0-100)."""
        if not IS_WINDOWS:
            return {"summary": "Volume control not supported on this platform"}
        try:
            volume = _endpoint_volume()
            volume.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100, None)
            return {"summary": f"Volume set to {level}%"}
        except ImportError:
            logger.warning("pycaw not installed, volume control unavailable")
            return {"summary": "Volume control requires pycaw"}
        except Exception as exc:
            logger.exception("set_volume failed")
            raise RuntimeError(f"Failed to set volume: {exc}") from exc

    async def set_mute(self, muted: bool = True) -> dict[str, Any]:
        """Mute or unmute system audio."""
        if not IS_WINDOWS:
            return {"summary": "Mute not supported on this platform"}
        try:
            volume = _endpoint_volume()
            volume.SetMute(int(muted), None)
            return {"summary": "Audio muted" if muted else "Audio unmuted"}
        except ImportError:
            logger.warning("pycaw not installed")
            return {"summary": "Mute control requires pycaw"}
        except Exception as exc:
            logger.exception("set_mute failed")
            raise RuntimeError(f"Failed to set mute: {exc}") from exc

    async def toggle_mute(self) -> dict[str, Any]:
        """Toggle mute state."""
        current = await self.get_volume()
        return await self.set_mute(not current.get("muted", False))

    async def volume_up(self, amount: int = 5) -> dict[str, Any]:
        """Increase volume by amount."""
        try:
            import pyautogui
            for _ in range(amount):
                pyautogui.press("volumeup")
            return {"summary": f"Volume increased by {amount} steps"}
        except ImportError:
            current = await self.get_volume()
            new_level = min(100, int(current.get("volume", 0)) + amount)
            return await self.set_volume(new_level)
        except Exception as exc:
            logger.exception("volume_up failed")
            raise RuntimeError(f"Failed to increase volume: {exc}") from exc

    async def volume_down(self, amount: int = 5) -> dict[str, Any]:
        """Decrease volume by amount."""
        try:
            import pyautogui
            for _ in range(amount):
                pyautogui.press("volumedown")
            return {"summary": f"Volume decreased by {amount} steps"}
        except ImportError:
            current = await self.get_volume()
            new_level = max(0, int(current.get("volume", 0)) - amount)
            return await self.set_volume(new_level)
        except Exception as exc:
            logger.exception("volume_down failed")
            raise RuntimeError(f"Failed to decrease volume: {exc}") from exc

    async def media_play_pause(self) -> dict[str, Any]:
        """Toggle play/pause."""
        try:
            import pyautogui
            pyautogui.press("playpause")
            return {"summary": "Play/Pause toggled"}
        except Exception as exc:
            raise RuntimeError(f"Failed: {exc}") from exc

    async def media_next(self) -> dict[str, Any]:
        """Skip to next track."""
        try:
            import pyautogui
            pyautogui.press("nexttrack")
            return {"summary": "Next track"}
        except Exception as exc:
            raise RuntimeError(f"Failed: {exc}") from exc

    async def media_prev(self) -> dict[str, Any]:
        """Go to previous track."""
        try:
            import pyautogui
            pyautogui.press("prevtrack")
            return {"summary": "Previous track"}
        except Exception as exc:
            raise RuntimeError(f"Failed: {exc}") from exc

    async def media_stop(self) -> dict[str, Any]:
        """Stop playback."""
        try:
            import pyautogui
            pyautogui.press("stop")
            return {"summary": "Playback stopped"}
        except Exception as exc:
            raise RuntimeError(f"Failed: {exc}") from exc

    async def get_brightness(self) -> dict[str, Any]:
        """Get current screen brightness.
        
        Tries multiple methods:
        1. WMI (laptop panels)
        2. PowerShell (desktop monitors via DDC/CI or Windows API)
        3. Returns current OS night light status as fallback
        """
        if not IS_WINDOWS:
            return {"brightness": 50, "summary": "Brightness not available on non-Windows"}
        
        # Method 1: WMI (laptop panels)
        try:
            import wmi
            c = wmi.WMI()
            for monitor in c.WmiMonitorBrightness():
                brightness = monitor.CurrentBrightness
                return {"brightness": brightness, "summary": f"Brightness at {brightness}%"}
        except Exception:
            pass
        
        # Method 2: PowerShell Get-Luminance (Windows 10 1803+)
        try:
            import subprocess
            result = subprocess.run(
                ["powershell", "-Command", r"(Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightness).CurrentBrightness"],
                capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
            )
            brightness = int(result.stdout.strip())
            if 0 <= brightness <= 100:
                return {"brightness": brightness, "summary": f"Brightness at {brightness}%"}
        except Exception:
            pass
        
        # Method 3: Default to 50 for desktop monitors (brightness is usually manual)
        return {"brightness": 50, "summary": "Desktop monitor brightness (manual control)"}

    async def set_brightness(self, level: int) -> dict[str, Any]:
        """Set screen brightness (0-100).
        
        Tries WMI first, then PowerShell, then returns success for manual control.
        """
        if not IS_WINDOWS:
            return {"summary": "Brightness not available on non-Windows"}
        
        level = max(0, min(100, level))
        
        # Method 1: WMI
        try:
            import wmi
            c = wmi.WMI()
            for monitor in c.WmiMonitorBrightnessMethods():
                monitor.WmiSetBrightness(level, 0)
                return {"summary": f"Brightness set to {level}%"}
        except Exception:
            pass
        
        # Method 2: PowerShell
        try:
            import subprocess
            ps_cmd = f"(Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return {"summary": f"Brightness set to {level}%"}
        except Exception:
            pass
        
        # Method 3: Desktop monitors don't support software brightness
        return {"summary": f"Brightness: {level}% (use monitor buttons for desktop)"}

