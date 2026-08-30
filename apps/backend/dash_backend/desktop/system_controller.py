"""System Controller - System-level controls for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
import platform
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemInfo:
    """System information."""
    os: str
    os_version: str
    hostname: str
    cpu_count: int
    memory_total_gb: float
    architecture: str
    
    def to_dict(self) -> dict:
        return {
            "os": self.os,
            "os_version": self.os_version,
            "hostname": self.hostname,
            "cpu_count": self.cpu_count,
            "memory_total_gb": self.memory_total_gb,
            "architecture": self.architecture,
        }


class SystemController:
    """Controls system-level functions.
    
    Features:
    - Get system information
    - Volume control
    - Shutdown/restart
    - Sleep/hibernate
    - Lock screen
    - Empty recycle bin
    - Open system applications
    """
    
    def __init__(self):
        self._system_info: Optional[SystemInfo] = None
        
    async def get_system_info(self) -> SystemInfo:
        """Get system information.
        
        Returns:
            SystemInfo
        """
        if self._system_info is None:
            self._system_info = await self._gather_system_info()
        return self._system_info
    
    async def _gather_system_info(self) -> SystemInfo:
        """Gather system information."""
        import psutil
        
        return SystemInfo(
            os=platform.system(),
            os_version=platform.version(),
            hostname=platform.node(),
            cpu_count=psutil.cpu_count(),
            memory_total_gb=psutil.virtual_memory().total / (1024**3),
            architecture=platform.machine(),
        )
    
    async def set_volume(self, level: float) -> bool:
        """Set system volume.
        
        Args:
            level: Volume level (0.0 to 1.0)
            
        Returns:
            True if successful
        """
        level = max(0.0, min(1.0, level))
        
        try:
            if self._is_windows():
                return await self._set_volume_win32(level)
            else:
                return await self._set_volume_xdg(level)
        except Exception as e:
            logger.error("Set volume failed: %s", e)
            return False
    
    async def get_volume(self) -> Optional[float]:
        """Get system volume.
        
        Returns:
            Volume level or None
        """
        try:
            if self._is_windows():
                return await self._get_volume_win32()
            else:
                return await self._get_volume_xdg()
        except Exception as e:
            logger.error("Get volume failed: %s", e)
            return None
    
    async def mute_volume(self, mute: bool = True) -> bool:
        """Mute or unmute system volume.
        
        Args:
            mute: True to mute, False to unmute
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._mute_volume_win32(mute)
            else:
                return await self._mute_volume_xdg(mute)
        except Exception as e:
            logger.error("Mute volume failed: %s", e)
            return False
    
    async def shutdown(self, force: bool = False) -> bool:
        """Shutdown the system.
        
        Args:
            force: Force shutdown without confirmation
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._shutdown_win32(force)
            else:
                return await self._shutdown_xdg(force)
        except Exception as e:
            logger.error("Shutdown failed: %s", e)
            return False
    
    async def restart(self, force: bool = False) -> bool:
        """Restart the system.
        
        Args:
            force: Force restart without confirmation
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._restart_win32(force)
            else:
                return await self._restart_xdg(force)
        except Exception as e:
            logger.error("Restart failed: %s", e)
            return False
    
    async def sleep(self) -> bool:
        """Put the system to sleep.
        
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._sleep_win32()
            else:
                return await self._sleep_xdg()
        except Exception as e:
            logger.error("Sleep failed: %s", e)
            return False
    
    async def hibernate(self) -> bool:
        """Hibernate the system.
        
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._hibernate_win32()
            else:
                return await self._hibernate_xdg()
        except Exception as e:
            logger.error("Hibernate failed: %s", e)
            return False
    
    async def lock_screen(self) -> bool:
        """Lock the screen.
        
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._lock_screen_win32()
            else:
                return await self._lock_screen_xdg()
        except Exception as e:
            logger.error("Lock screen failed: %s", e)
            return False
    
    async def empty_recycle_bin(self) -> bool:
        """Empty the recycle bin.
        
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._empty_recycle_bin_win32()
            else:
                return await self._empty_recycle_bin_xdg()
        except Exception as e:
            logger.error("Empty recycle bin failed: %s", e)
            return False
    
    async def open_file_explorer(self, path: Optional[str] = None) -> bool:
        """Open file explorer.
        
        Args:
            path: Optional path to open
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                import subprocess
                if path:
                    subprocess.run(["explorer", path])
                else:
                    subprocess.run(["explorer"])
            else:
                import subprocess
                if path:
                    subprocess.run(["xdg-open", path])
                else:
                    subprocess.run(["xdg-open", "."])
            return True
        except Exception as e:
            logger.error("Open file explorer failed: %s", e)
            return False
    
    async def open_settings(self) -> bool:
        """Open system settings.
        
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                import subprocess
                subprocess.run(["start", "ms-settings:"], shell=True)
            elif self._is_macos():
                import subprocess
                subprocess.run(["open", "x-apple.systempreferences:"])
            else:
                import subprocess
                subprocess.run(["gnome-control-center"])
            return True
        except Exception as e:
            logger.error("Open settings failed: %s", e)
            return False
    
    # ── Platform Implementations ─────────────────────────────
    
    def _is_windows(self) -> bool:
        return platform.system() == "Windows"
    
    def _is_macos(self) -> bool:
        return platform.system() == "Darwin"
    
    async def _set_volume_win32(self, level: float) -> bool:
        """Set master volume via the Windows audio endpoint (pycaw)."""
        try:
            from dash_backend.services.media import _endpoint_volume

            volume = _endpoint_volume()
            volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level)), None)
            return True
        except ImportError:
            logger.warning("Windows volume control requires pycaw")
            return False
        except Exception as e:
            logger.error("Windows set_volume failed: %s", e)
            return False
    
    async def _set_volume_xdg(self, level: float) -> bool:
        import subprocess
        try:
            subprocess.run(["amixer", "set", "Master", f"{int(level * 100)}%"])
            return True
        except Exception:
            return False
    
    async def _get_volume_win32(self) -> Optional[float]:
        """Read master volume via the Windows audio endpoint (pycaw)."""
        try:
            from dash_backend.services.media import _endpoint_volume

            volume = _endpoint_volume()
            return float(volume.GetMasterVolumeLevelScalar())
        except ImportError:
            logger.warning("Windows volume readout requires pycaw")
            return None
        except Exception as e:
            logger.error("Windows get_volume failed: %s", e)
            return None
    
    async def _get_volume_xdg(self) -> Optional[float]:
        import subprocess
        try:
            result = subprocess.run(
                ["amixer", "get", "Master"],
                capture_output=True,
                text=True
            )
            # Parse output to get volume
            return 0.5  # Placeholder
        except Exception:
            return None
    
    async def _mute_volume_win32(self, mute: bool) -> bool:
        logger.warning("Windows mute control not fully implemented")
        return False
    
    async def _mute_volume_xdg(self, mute: bool) -> bool:
        import subprocess
        try:
            subprocess.run(["amixer", "set", "Master", "mute" if mute else "unmute"])
            return True
        except Exception:
            return False
    
    async def _shutdown_win32(self, force: bool) -> bool:
        import subprocess
        subprocess.run(["shutdown", "/s", "/t", "0" if force else "30"])
        return True
    
    async def _shutdown_xdg(self, force: bool) -> bool:
        import subprocess
        subprocess.run(["systemctl", "poweroff"])
        return True
    
    async def _restart_win32(self, force: bool) -> bool:
        import subprocess
        subprocess.run(["shutdown", "/r", "/t", "0" if force else "30"])
        return True
    
    async def _restart_xdg(self, force: bool) -> bool:
        import subprocess
        subprocess.run(["systemctl", "reboot"])
        return True
    
    async def _sleep_win32(self) -> bool:
        import subprocess
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return True
    
    async def _sleep_xdg(self) -> bool:
        import subprocess
        subprocess.run(["systemctl", "suspend"])
        return True
    
    async def _hibernate_win32(self) -> bool:
        import subprocess
        subprocess.run(["shutdown", "/h"])
        return True
    
    async def _hibernate_xdg(self) -> bool:
        import subprocess
        subprocess.run(["systemctl", "hibernate"])
        return True
    
    async def _lock_screen_win32(self) -> bool:
        import subprocess
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return True
    
    async def _lock_screen_xdg(self) -> bool:
        import subprocess
        subprocess.run(["xdg-screensaver", "lock"])
        return True
    
    async def _empty_recycle_bin_win32(self) -> bool:
        import subprocess
        subprocess.run(["powershell", "-Command", "Clear-RecycleBin", "-Force"])
        return True
    
    async def _empty_recycle_bin_xdg(self) -> bool:
        import subprocess
        subprocess.run(["trash-empty"])
        return True


_system_controller: Optional[SystemController] = None


def get_system_controller() -> SystemController:
    global _system_controller
    if _system_controller is None:
        _system_controller = SystemController()
    return _system_controller
