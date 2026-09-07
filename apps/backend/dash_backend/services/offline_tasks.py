"""Offline-First Desktop Task Manager.

All Windows tasks work locally without network:
- Window management (list, minimize, maximize, close, focus)
- Application launching and closing
- File browsing and management
- System monitoring (CPU, RAM, disk, GPU)
- Power controls (shutdown, restart, sleep, lock)
- Clipboard operations
- Media controls (play, pause, next, previous)
- Volume control
- Screenshot capture
- Keyboard/mouse automation

Cloud features (when network available):
- Push notifications to Android
- Remote command relay
- State sync to DynamoDB
- APK distribution via S3
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import subprocess
import ctypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class OfflineTaskManager:
    """Manages all desktop tasks that work offline."""

    def __init__(self):
        self._initialized = False
        self._network_available = False

    async def initialize(self):
        """Initialize the task manager."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("Offline task manager initialized")

    # ── Window Management (Always Works Offline) ──────────────────

    async def list_windows(self) -> List[Dict]:
        """List all open windows."""
        try:
            import psutil
            windows = []
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    if proc.info['status'] == 'psutil.RUNNING':
                        windows.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "status": proc.info['status'],
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return windows
        except Exception as e:
            logger.error(f"List windows failed: {e}")
            return []

    async def close_window(self, title: str) -> bool:
        """Close a window by title."""
        try:
            subprocess.run(["taskkill", "/IM", title, "/F"], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Close window failed: {e}")
            return False

    async def minimize_window(self, title: str) -> bool:
        """Minimize a window."""
        try:
            # Use PowerShell to minimize window
            ps = f'(Get-Process | Where-Object {{$_.MainWindowTitle -like "*{title}*"}}).MainWindowHandle | ForEach-Object {{ $sig = "[user32.dll]ShowWindow"; $type = Add-Type -MemberDefinition $sig -Name "Win32ShowWindow" -Namespace Win32Functions -PassThru; $type::ShowWindow($_, 6) }}'
            subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Minimize window failed: {e}")
            return False

    async def maximize_window(self, title: str) -> bool:
        """Maximize a window."""
        try:
            ps = f'(Get-Process | Where-Object {{$_.MainWindowTitle -like "*{title}*"}}).MainWindowHandle | ForEach-Object {{ $sig = "[user32.dll]ShowWindow"; $type = Add-Type -MemberDefinition $sig -Name "Win32ShowWindow" -Namespace Win32Functions -PassThru; $type::ShowWindow($_, 3) }}'
            subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Maximize window failed: {e}")
            return False

    # ── Application Management (Always Works Offline) ─────────────

    async def launch_application(self, name: str) -> bool:
        """Launch an application."""
        try:
            # Try common paths
            common_paths = [
                f"C:\\Program Files\\{name}\\{name}.exe",
                f"C:\\Program Files (x86)\\{name}\\{name}.exe",
                f"C:\\Users\\{os.getenv('USERNAME')}\\AppData\\Local\\{name}\\{name}.exe",
            ]
            for path in common_paths:
                if os.path.exists(path):
                    subprocess.Popen([path], shell=True)
                    return True

            # Try start command
            subprocess.run(["start", name], shell=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Launch application failed: {e}")
            return False

    async def close_application(self, name: str) -> bool:
        """Close an application."""
        try:
            subprocess.run(["taskkill", "/IM", f"{name}.exe", "/F"], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Close application failed: {e}")
            return False

    # ── File Management (Always Works Offline) ────────────────────

    async def list_directory(self, path: str = None) -> List[Dict]:
        """List directory contents."""
        if path is None:
            path = os.path.expanduser("~")

        try:
            items = []
            for item in Path(path).iterdir():
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0,
                    "modified": item.stat().st_mtime,
                })
            return sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower()))
        except Exception as e:
            logger.error(f"List directory failed: {e}")
            return []

    # ── System Monitoring (Always Works Offline) ──────────────────

    async def get_system_metrics(self) -> Dict:
        """Get system metrics (CPU, RAM, disk, GPU)."""
        try:
            import psutil

            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()

            # Memory
            mem = psutil.virtual_memory()

            # Disk
            disk = psutil.disk_usage('/')

            # GPU (if available)
            gpu_percent = 0
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_percent = gpus[0].load * 100
            except ImportError:
                pass

            return {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "ram_percent": mem.percent,
                "ram_used_gb": round(mem.used / (1024**3), 2),
                "ram_total_gb": round(mem.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "gpu_percent": gpu_percent,
                "hostname": platform.node(),
                "platform": platform.system(),
            }
        except Exception as e:
            logger.error(f"System metrics failed: {e}")
            return {}

    # ── Power Controls (Always Works Offline) ─────────────────────

    async def shutdown(self) -> bool:
        """Shutdown the PC."""
        try:
            subprocess.run(["shutdown", "/s", "/t", "0"], capture_output=True)
            return True
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            return False

    async def restart(self) -> bool:
        """Restart the PC."""
        try:
            subprocess.run(["shutdown", "/r", "/t", "0"], capture_output=True)
            return True
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            return False

    async def sleep(self) -> bool:
        """Put PC to sleep."""
        try:
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], capture_output=True)
            return True
        except Exception as e:
            logger.error(f"Sleep failed: {e}")
            return False

    async def lock(self) -> bool:
        """Lock the workstation."""
        try:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True)
            return True
        except Exception as e:
            logger.error(f"Lock failed: {e}")
            return False

    # ── Media Controls (Always Works Offline) ─────────────────────

    async def media_play_pause(self) -> bool:
        """Toggle play/pause."""
        try:
            # Send media key via PowerShell
            ps = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{MEDIA_PLAY_PAUSE}')"
            subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Media play/pause failed: {e}")
            return False

    async def media_next(self) -> bool:
        """Next track."""
        try:
            ps = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{MEDIA_NEXT_TRACK}')"
            subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Media next failed: {e}")
            return False

    async def media_previous(self) -> bool:
        """Previous track."""
        try:
            ps = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{MEDIA_PREV_TRACK}')"
            subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Media previous failed: {e}")
            return False

    # ── Volume Control (Always Works Offline) ─────────────────────

    async def get_volume(self) -> int:
        """Get current volume (0-100)."""
        try:
            ps = """
            $wmi = Get-WmiObject -Class Win32_SoundDevice
            $volume = (Get-WmiObject -Namespace "root\wmi" -Class MPS_NamespaceWMI).CurrentVolume
            Write-Output $volume
            """
            result = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True, timeout=5)
            return int(result.stdout.strip() or 0)
        except Exception:
            return 0

    async def set_volume(self, level: int) -> bool:
        """Set volume (0-100)."""
        try:
            # Use nircmd if available, otherwise PowerShell
            ps = f"""
            $wsh = New-Object -ComObject WScript.Shell
            1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }}
            1..{level // 2} | ForEach-Object {{ $wsh.SendKeys([char]175) }}
            """
            subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Set volume failed: {e}")
            return False

    # ── Clipboard (Always Works Offline) ──────────────────────────

    async def get_clipboard(self) -> str:
        """Get clipboard content."""
        try:
            result = subprocess.run(["powershell", "-Command", "Get-Clipboard"],
                                    capture_output=True, text=True, timeout=5)
            return result.stdout.strip()
        except Exception:
            return ""

    async def set_clipboard(self, text: str) -> bool:
        """Set clipboard content."""
        try:
            subprocess.run(["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
                           capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Set clipboard failed: {e}")
            return False

    # ── Screenshot (Always Works Offline) ─────────────────────────

    async def take_screenshot(self) -> Optional[bytes]:
        """Take a screenshot."""
        try:
            import io
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            return buffer.getvalue()
        except ImportError:
            # Fallback to PowerShell
            try:
                path = os.path.join(os.environ['TEMP'], 'dash_screenshot.png')
                ps = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object {{ $bmp = New-Object System.Drawing.Bitmap($_.Bounds.Width, $_.Bounds.Height); $gfx = [System.Drawing.Graphics]::FromImage($bmp); $gfx.CopyFromScreen($_.Bounds.Location, [System.Drawing.Point]::Empty, $_.Bounds.Size); $bmp.Save('{path}') }}"
                subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=10)
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        return f.read()
            except Exception:
                pass
            return None
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    # ── Network State ─────────────────────────────────────────────

    def set_network_state(self, available: bool):
        """Update network availability state."""
        self._network_available = available

    def is_network_available(self) -> bool:
        """Check if network is available."""
        return self._network_available


# Singleton
_offline_task_manager: Optional[OfflineTaskManager] = None


def get_offline_task_manager() -> OfflineTaskManager:
    """Get the offline task manager singleton."""
    global _offline_task_manager
    if _offline_task_manager is None:
        _offline_task_manager = OfflineTaskManager()
    return _offline_task_manager
