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


def _promote_to_executable(path: str, app_name: str) -> str:
    """Promote a resolved install directory to its launchable exe.

    Registry discovery entries sometimes declare a directory (Brave's
    resolves to ``...\\Brave-Browser\\Application``). ``os.startfile`` on a
    directory opens Explorer instead of the app — found live when
    "open brave" claimed success while only Explorer windows appeared.
    Chrome-family layout puts the exe either directly in that folder
    (``Application\\brave.exe``) or in a version subfolder
    (``Application\\<ver>\\chrome.exe``); prefer name-matching exes.
    """
    from pathlib import Path

    p = Path(path)
    if p.is_file():
        return str(p)
    if not p.is_dir():
        return str(p)

    direct = list(p.glob("*.exe"))
    nested = list(p.glob("*/*.exe"))
    needle = (app_name or "").lower()

    def _prefer(cands):
        named = [c for c in cands if needle and needle in c.stem.lower()]
        return named or cands

    for pool in (_prefer(direct), _prefer(nested)):
        if pool:
            best = sorted(pool, key=lambda c: len(c.name))[0]
            return str(best)
    return str(p)


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

        path = _promote_to_executable(app["path"], app.get("name") or name)

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
        """Find a running process by name.

        Matching is precise: the exe basename must equal ``name`` (or be a
        dotted child like ``Zoom.features.exe`` for needle ``zoom``). The
        old substring check matched ``BraveCrashHandler.exe`` for "brave"
        and ``PowerToys.ZoomIt.exe`` for "zoom" — so "open brave" reported
        "already running" and never launched the real app (found live).
        """
        import psutil

        needle = (name or "").lower().strip()
        if not needle:
            return None

        def _matches(img_name: str) -> bool:
            base = (img_name or "").lower()
            if base.endswith(".exe"):
                base = base[:-4]
            return base == needle or base.endswith("." + needle)

        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                proc_name = proc.info["name"] or ""
                if _matches(proc_name):
                    return {
                        "pid": proc.info["pid"],
                        "name": proc_name,
                        "exe": proc.info.get("exe", "") or "",
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