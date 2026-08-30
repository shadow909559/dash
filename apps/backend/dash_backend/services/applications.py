"""ApplicationService - launch, close, kill, and restart applications."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton
from dash_backend.services.application_discovery import get_application_discovery

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


class ApplicationService(Singleton):
    """Manage application lifecycle."""

    def __init__(self) -> None:
        self._discovery = get_application_discovery()

    async def search_applications(self, query: str) -> list[dict[str, Any]]:
        """Search for installed applications by name."""
        return self._discovery.search(query)

    async def launch_by_name(
        self, name: str, bring_to_foreground: bool = True
    ) -> dict[str, Any]:
        """Launch an application by friendly name."""
        if not name:
            raise ValueError("name is required")

        # First check if already running
        running = await self.find_running_process(name)
        if running:
            if bring_to_foreground:
                await self.bring_to_foreground(running["pid"])
            return {
                "summary": f"Application '{name}' is already running",
                "status": "already_running",
                "pid": running["pid"],
            }

        # Search for installed application
        app = self._discovery.resolve(name)
        if not app or not app.get("path"):
            raise RuntimeError(f"Application '{name}' not found or path is missing")

        path = app["path"]

        try:
            if IS_WINDOWS:
                # Use os.startfile for .lnk and executables
                os.startfile(path)
            else:
                # On non-Windows, subprocess.Popen is more reliable
                subprocess.Popen(
                    [path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            return {
                "summary": f"Launched {name}",
                "status": "launched",
                "app_name": app["name"],
            }
        except Exception as exc:
            logger.exception("Failed to launch %s by name", name)
            raise RuntimeError(f"Failed to launch {name}: {exc}") from exc

    async def find_running_process(self, name: str) -> dict[str, Any] | None:
        """Find a running process by name."""
        import psutil
        
        name_lower = name.lower()
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                proc_name = proc.info["name"]
                proc_exe = proc.info.get("exe", "")
                
                if name_lower in proc_name.lower() or (proc_exe and name_lower in proc_exe.lower()):
                    return {
                        "pid": proc.info["pid"],
                        "name": proc_name,
                        "exe": proc_exe
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return None

    async def bring_to_foreground(self, pid: int) -> dict[str, Any]:
        """Bring a window to the foreground by process ID."""
        if not IS_WINDOWS:
            return {"summary": "bring_to_foreground is Windows-only", "status": "unsupported"}
        
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # Find the main window for this process
            def callback(hwnd, lParam):
                _, found_pid = ctypes.wintypes.DWORD(), ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
                if found_pid.value == pid:
                    # Check if window is visible
                    if user32.IsWindowVisible(hwnd):
                        # Bring to front
                        user32.SetForegroundWindow(hwnd)
                        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        return False  # Stop enumeration
                return True
            
            user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(callback), 0)
            
            return {"summary": f"Brought process {pid} to foreground", "status": "success"}
        except Exception as exc:
            logger.exception("Failed to bring process %d to foreground", pid)
            raise RuntimeError(f"Failed to bring to foreground: {exc}") from exc

    async def launch(
        self, path: str, args: list[str] | None = None
    ) -> dict[str, Any]:
        """Launch an application by path."""
        if not path:
            raise ValueError("path is required")
        try:
            if IS_WINDOWS:
                os.startfile(path)
                return {"summary": f"Launched {path}", "status": "launched"}
            else:
                cmd = [path] + (args or [])
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return {
                    "summary": f"Launched {path}",
                    "status": "launched",
                    "pid": proc.pid,
                }
        except Exception as exc:
            logger.exception("Failed to launch %s", path)
            raise RuntimeError(f"Failed to launch: {exc}") from exc

    async def close(self, name: str) -> dict[str, Any]:
        """Close an application by name."""
        if not name:
            raise ValueError("name is required")
        try:
            if IS_WINDOWS:
                result = subprocess.run(
                    ["taskkill", "/IM", name, "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return {"summary": f"Closed {name}", "status": "closed"}
                else:
                    return {"summary": f"Failed to close {name}: {result.stderr}", "status": "failed"}
            else:
                result = subprocess.run(
                    ["pkill", "-f", name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return {"summary": f"Closed {name}", "status": "closed"}
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Timed out closing {name}")
        except Exception as exc:
            logger.exception("Failed to close %s", name)
            raise RuntimeError(f"Failed to close: {exc}") from exc

    async def kill(self, name: str) -> dict[str, Any]:
        """Kill a process by name."""
        return await self.close(name)

    async def restart(
        self, name: str, path: str | None = None
    ) -> dict[str, Any]:
        """Restart an application."""
        await self.close(name)
        if path:
            await self.launch(path)
        else:
            # Try to find and relaunch by name
            await self.launch_by_name(name, bring_to_foreground=False)
        return {"summary": f"Restarted {name}", "status": "restarted"}

    async def list_processes(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List running processes."""
        import psutil

        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if len(processes) >= limit:
                break
        return processes