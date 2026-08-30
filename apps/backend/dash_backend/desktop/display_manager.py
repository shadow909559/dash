"""Display Manager - Display and monitor control for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DisplayInfo:
    """Information about a display/monitor."""
    id: int
    name: str
    resolution: Tuple[int, int]  # (width, height)
    position: Tuple[int, int]  # (x, y)
    scale: float
    is_primary: bool
    refresh_rate: int
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "resolution": {"width": self.resolution[0], "height": self.resolution[1]},
            "position": {"x": self.position[0], "y": self.position[1]},
            "scale": self.scale,
            "is_primary": self.is_primary,
            "refresh_rate": self.refresh_rate,
        }


@dataclass
class BrightnessLevel:
    """Brightness level for a display."""
    display_id: int
    level: float  # 0.0 to 1.0


class DisplayManager:
    """Manages displays and monitors.
    
    Features:
    - List all displays
    - Get display information
    - Set brightness
    - Set resolution
    - Set refresh rate
    - Toggle primary display
    - Arrange displays
    """
    
    def __init__(self):
        self._displays: List[DisplayInfo] = []
        self._brightness_levels: dict[int, float] = {}
        
    async def list_displays(self) -> List[DisplayInfo]:
        """List all connected displays.
        
        Returns:
            List of DisplayInfo
        """
        try:
            if self._is_windows():
                self._displays = await self._enum_displays_win32()
            else:
                self._displays = await self._enum_displays_xdg()
            
            logger.info("Found %d displays", len(self._displays))
            return self._displays
        except Exception as e:
            logger.error("List displays failed: %s", e)
            return []
    
    async def get_display(self, display_id: int) -> Optional[DisplayInfo]:
        """Get display info by ID.
        
        Args:
            display_id: Display ID
            
        Returns:
            DisplayInfo or None
        """
        for display in self._displays:
            if display.id == display_id:
                return display
        return None
    
    async def get_primary_display(self) -> Optional[DisplayInfo]:
        """Get the primary display.
        
        Returns:
            DisplayInfo or None
        """
        for display in self._displays:
            if display.is_primary:
                return display
        return None
    
    async def set_brightness(self, display_id: int, level: float) -> bool:
        """Set display brightness.
        
        Args:
            display_id: Display ID
            level: Brightness level (0.0 to 1.0)
            
        Returns:
            True if successful
        """
        level = max(0.0, min(1.0, level))
        
        try:
            if self._is_windows():
                result = await self._set_brightness_win32(display_id, level)
            else:
                result = await self._set_brightness_xdg(display_id, level)
            
            if result:
                self._brightness_levels[display_id] = level
                logger.info("Set brightness for display %d to %.2f", display_id, level)
            return result
        except Exception as e:
            logger.error("Set brightness failed: %s", e)
            return False
    
    async def get_brightness(self, display_id: int) -> Optional[float]:
        """Get display brightness.
        
        Args:
            display_id: Display ID
            
        Returns:
            Brightness level or None
        """
        if display_id in self._brightness_levels:
            return self._brightness_levels[display_id]
        
        try:
            if self._is_windows():
                level = await self._get_brightness_win32(display_id)
            else:
                level = await self._get_brightness_xdg(display_id)
            
            if level is not None:
                self._brightness_levels[display_id] = level
            return level
        except Exception as e:
            logger.error("Get brightness failed: %s", e)
            return None
    
    async def set_resolution(self, display_id: int, width: int, height: int) -> bool:
        """Set display resolution.
        
        Args:
            display_id: Display ID
            width: Width in pixels
            height: Height in pixels
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                result = await self._set_resolution_win32(display_id, width, height)
            else:
                result = await self._set_resolution_xdg(display_id, width, height)
            
            if result:
                logger.info("Set resolution for display %d to %dx%d", display_id, width, height)
            return result
        except Exception as e:
            logger.error("Set resolution failed: %s", e)
            return False
    
    async def set_primary_display(self, display_id: int) -> bool:
        """Set a display as primary.
        
        Args:
            display_id: Display ID
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                result = await self._set_primary_win32(display_id)
            else:
                result = await self._set_primary_xdg(display_id)
            
            if result:
                logger.info("Set display %d as primary", display_id)
            return result
        except Exception as e:
            logger.error("Set primary display failed: %s", e)
            return False
    
    # ── Platform Implementations ─────────────────────────────
    
    def _is_windows(self) -> bool:
        import platform
        return platform.system() == "Windows"
    
    async def _enum_displays_win32(self) -> List[DisplayInfo]:
        import win32api
        import win32con
        
        displays = []
        display_info = win32api.EnumDisplayMonitors(None, None)
        
        for i, (monitor, dc, rect) in enumerate(display_info):
            displays.append(DisplayInfo(
                id=i,
                name=f"Display {i}",
                resolution=(rect[2] - rect[0], rect[3] - rect[1]),
                position=(rect[0], rect[1]),
                scale=1.0,
                is_primary=(i == 0),
                refresh_rate=60,
            ))
        
        return displays
    
    async def _enum_displays_xdg(self) -> List[DisplayInfo]:
        import subprocess
        
        displays = []
        try:
            result = subprocess.run(
                ["xrandr", "--query"],
                capture_output=True,
                text=True
            )
            
            for i, line in enumerate(result.stdout.split("\n")):
                if " connected" in line:
                    parts = line.split()
                    name = parts[0]
                    resolution = parts[2].split("x")
                    displays.append(DisplayInfo(
                        id=i,
                        name=name,
                        resolution=(int(resolution[0]), int(resolution[1])),
                        position=(0, 0),
                        scale=1.0,
                        is_primary=("primary" in line),
                        refresh_rate=60,
                    ))
        except Exception as e:
            logger.error("XDG display enumeration failed: %s", e)
        
        return displays
    
    async def _set_brightness_win32(self, display_id: int, level: float) -> bool:
        """Set brightness via WMI (WmiMonitorBrightnessMethods)."""
        try:
            import wmi

            c = wmi.WMI()
            level = max(0, min(100, int(level * 100)))
            for monitor in c.WmiMonitorBrightnessMethods():
                monitor.WmiSetBrightness(level, 0)
                break
            return True
        except ImportError:
            logger.warning("Windows brightness control requires wmi module")
            return False
        except Exception as e:
            logger.error("Windows set_brightness failed: %s", e)
            return False
    
    async def _set_brightness_xdg(self, display_id: int, level: float) -> bool:
        import subprocess
        
        try:
            # Try using brightnessctl or xbacklight
            display = await self.get_display(display_id)
            if display:
                subprocess.run(["brightnessctl", "-d", display.name, "s", f"{int(level * 100)}%"])
                return True
        except Exception:
            pass
        
        return False
    
    async def _get_brightness_win32(self, display_id: int) -> Optional[float]:
        """Read brightness via WMI; returns None when unavailable."""
        try:
            import wmi

            c = wmi.WMI()
            for monitor in c.WmiMonitorBrightness():
                return float(monitor.CurrentBrightness) / 100.0
            return None
        except ImportError:
            logger.warning("Windows brightness readout requires wmi module")
            return None
        except Exception as e:
            logger.error("Windows get_brightness failed: %s", e)
            return None
    
    async def _get_brightness_xdg(self, display_id: int) -> Optional[float]:
        import subprocess
        
        try:
            display = await self.get_display(display_id)
            if display:
                result = subprocess.run(
                    ["brightnessctl", "-d", display.name, "g"],
                    capture_output=True,
                    text=True
                )
                return float(result.stdout.strip()) / 100.0
        except Exception:
            pass
        
        return None
    
    async def _set_resolution_win32(self, display_id: int, width: int, height: int) -> bool:
        # Windows resolution change requires specific APIs
        logger.warning("Windows resolution control not fully implemented")
        return False
    
    async def _set_resolution_xdg(self, display_id: int, width: int, height: int) -> bool:
        import subprocess
        
        try:
            display = await self.get_display(display_id)
            if display:
                subprocess.run(["xrandr", "--output", display.name, "--mode", f"{width}x{height}"])
                return True
        except Exception as e:
            logger.error("XDG resolution change failed: %s", e)
        
        return False
    
    async def _set_primary_win32(self, display_id: int) -> bool:
        logger.warning("Windows primary display control not fully implemented")
        return False
    
    async def _set_primary_xdg(self, display_id: int) -> bool:
        import subprocess
        
        try:
            display = await self.get_display(display_id)
            if display:
                subprocess.run(["xrandr", "--output", display.name, "--primary"])
                return True
        except Exception as e:
            logger.error("XDG primary display change failed: %s", e)
        
        return False


_display_manager: Optional[DisplayManager] = None


def get_display_manager() -> DisplayManager:
    global _display_manager
    if _display_manager is None:
        _display_manager = DisplayManager()
    return _display_manager
