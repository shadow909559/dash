"""Window Manager - Desktop window management for DASH AI OS.

Provides:
- List all open windows
- Get window info (title, position, size, process)
- Focus/bring window to front
- Minimize, maximize, restore, close windows
- Monitor window events (create, close, focus change)
- Window snapping and layout management
- Virtual desktop support
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class WindowState(Enum):
    """Window display state."""
    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    FULLSCREEN = "fullscreen"
    HIDDEN = "hidden"


@dataclass
class WindowInfo:
    """Information about a desktop window.
    
    Attributes:
        id: Window identifier (HWND on Windows)
        title: Window title
        process_name: Executable name
        process_id: Process ID
        bounds: (x, y, width, height)
        state: Window display state
        is_visible: Whether window is visible
        is_responsive: Whether window is responding
        monitor: Monitor number
        z_order: Z-order position
        opened_at: When the window was opened
        last_active: When last active
        metadata: Additional data
    """
    id: str = ""
    title: str = ""
    process_name: str = ""
    process_id: int = 0
    bounds: tuple = (0, 0, 800, 600)
    state: WindowState = WindowState.NORMAL
    is_visible: bool = True
    is_responsive: bool = True
    monitor: int = 0
    z_order: int = 0
    opened_at: float = 0.0
    last_active: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "process_name": self.process_name,
            "process_id": self.process_id,
            "bounds": {
                "x": self.bounds[0],
                "y": self.bounds[1],
                "width": self.bounds[2],
                "height": self.bounds[3],
            },
            "state": self.state.value,
            "is_visible": self.is_visible,
            "is_responsive": self.is_responsive,
            "monitor": self.monitor,
        }


@dataclass
class WindowLayout:
    """A window layout configuration.
    
    Attributes:
        name: Layout name
        windows: List of (window_id, bounds) tuples
        monitor: Target monitor
        created_at: When created
    """
    name: str = ""
    windows: List[tuple] = field(default_factory=list)
    monitor: int = 0
    created_at: float = 0.0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


class WindowManager:
    """Manages desktop windows.
    
    Features:
    - Window enumeration and information
    - Window state control (focus, minimize, maximize, close)
    - Window event monitoring
    - Window layouts and snapping
    - Virtual desktop support
    - Cross-platform (Windows primary, macOS/Linux fallback)
    """
    
    def __init__(self, poll_interval: float = 1.0):
        self._poll_interval = poll_interval
        self._windows: Dict[str, WindowInfo] = {}
        self._layouts: Dict[str, WindowLayout] = {}
        
        # Event callbacks
        self._window_created_callbacks: List[Callable] = []
        self._window_closed_callbacks: List[Callable] = []
        self._window_focus_callbacks: List[Callable] = []
        
        # Monitor task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._stats = {
            "windows_tracked": 0,
            "windows_managed": 0,
            "layouts_created": 0,
        }
    
    # ── Lifecycle ───────────────────────────────────────────
    
    async def start(self) -> None:
        """Start window monitoring."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("WindowManager started")
    
    async def stop(self) -> None:
        """Stop window monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("WindowManager stopped")
    
    # ── Window Enumeration ──────────────────────────────────
    
    async def list_windows(self) -> List[WindowInfo]:
        """List all open windows.
        
        Returns:
            List of WindowInfo
        """
        windows = []
        try:
            if self._is_windows():
                windows = await self._enum_windows_win32()
            else:
                windows = await self._enum_windows_xdg()
        except Exception as exc:
            logger.warning("Window enumeration failed: %s", exc)
        
        # Update cache
        self._windows = {w.id: w for w in windows}
        self._stats["windows_tracked"] = len(windows)
        
        return windows
    
    async def get_window(self, window_id: str) -> Optional[WindowInfo]:
        """Get window info by ID.
        
        Args:
            window_id: Window ID
            
        Returns:
            WindowInfo or None
        """
        if window_id in self._windows:
            return self._windows[window_id]
        
        # Refresh and check
        await self.list_windows()
        return self._windows.get(window_id)
    
    async def get_active_window(self) -> Optional[WindowInfo]:
        """Get the currently focused window.
        
        Returns:
            WindowInfo of active window
        """
        try:
            if self._is_windows():
                return await self._get_active_window_win32()
            else:
                return await self._get_active_window_xdg()
        except Exception as exc:
            logger.warning("Get active window failed: %s", exc)
            return None
    
    async def find_windows(self, process_name: Optional[str] = None,
                            title_contains: Optional[str] = None) -> List[WindowInfo]:
        """Find windows by criteria.
        
        Args:
            process_name: Filter by process name
            title_contains: Filter by title substring
            
        Returns:
            List of matching WindowInfo
        """
        results = []
        for window in self._windows.values():
            if process_name and process_name.lower() not in window.process_name.lower():
                continue
            if title_contains and title_contains.lower() not in window.title.lower():
                continue
            results.append(window)
        return results
    
    # ── Window Control ──────────────────────────────────────
    
    async def focus_window(self, window_id: str) -> bool:
        """Bring a window to focus.
        
        Args:
            window_id: Window ID
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                result = await self._focus_window_win32(window_id)
            else:
                result = await self._focus_window_xdg(window_id)
            
            if result:
                self._stats["windows_managed"] += 1
            return result
        except Exception as exc:
            logger.warning("Focus window failed: %s", exc)
            return False
    
    async def minimize_window(self, window_id: str) -> bool:
        """Minimize a window.
        
        Args:
            window_id: Window ID
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._minimize_window_win32(window_id)
            return False
        except Exception as exc:
            logger.warning("Minimize window failed: %s", exc)
            return False
    
    async def maximize_window(self, window_id: str) -> bool:
        """Maximize a window.
        
        Args:
            window_id: Window ID
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._maximize_window_win32(window_id)
            return False
        except Exception as exc:
            logger.warning("Maximize window failed: %s", exc)
            return False
    
    async def restore_window(self, window_id: str) -> bool:
        """Restore a minimized/maximized window.
        
        Args:
            window_id: Window ID
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._restore_window_win32(window_id)
            return False
        except Exception as exc:
            logger.warning("Restore window failed: %s", exc)
            return False
    
    async def close_window(self, window_id: str) -> bool:
        """Close a window.
        
        Args:
            window_id: Window ID
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._close_window_win32(window_id)
            return False
        except Exception as exc:
            logger.warning("Close window failed: %s", exc)
            return False
    
    async def move_window(self, window_id: str, x: int, y: int,
                           width: Optional[int] = None,
                           height: Optional[int] = None) -> bool:
        """Move and resize a window.
        
        Args:
            window_id: Window ID
            x: New X position
            y: New Y position
            width: Optional new width
            height: Optional new height
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                return await self._move_window_win32(window_id, x, y, width, height)
            return False
        except Exception as exc:
            logger.warning("Move window failed: %s", exc)
            return False
    
    # ── Window Layouts ──────────────────────────────────────
    
    async def create_layout(self, name: str) -> str:
        """Create a window layout from current window positions.
        
        Args:
            name: Layout name
            
        Returns:
            Layout ID
        """
        windows = await self.list_windows()
        
        layout = WindowLayout(
            name=name,
            windows=[(w.id, w.bounds) for w in windows if w.is_visible],
        )
        
        self._layouts[layout.name] = layout
        self._stats["layouts_created"] += 1
        
        return layout.name
    
    async def apply_layout(self, layout_name: str) -> bool:
        """Apply a saved window layout.
        
        Args:
            layout_name: Layout name
            
        Returns:
            True if applied
        """
        layout = self._layouts.get(layout_name)
        if not layout:
            return False
        
        for window_id, bounds in layout.windows:
            await self.move_window(window_id, *bounds)
        
        return True
    
    async def list_layouts(self) -> List[Dict[str, Any]]:
        """List saved window layouts.
        
        Returns:
            List of layout dicts
        """
        return [
            {"name": l.name, "window_count": len(l.windows), "created_at": l.created_at}
            for l in self._layouts.values()
        ]
    
    async def snap_window(self, window_id: str, position: str) -> bool:
        """Snap a window to a screen position.
        
        Args:
            window_id: Window ID
            position: "left", "right", "top", "bottom", "top-left", etc.
            
        Returns:
            True if snapped
        """
        window = await self.get_window(window_id)
        if not window:
            return False
        
        # Get monitor bounds
        import pygetwindow as gw
        monitors = await self._get_monitor_bounds()
        
        if not monitors:
            return False
        
        monitor = monitors[min(window.monitor, len(monitors) - 1)]
        mw, mh = monitor[2], monitor[3]
        
        # Calculate snap bounds
        positions = {
            "left": (0, 0, mw // 2, mh),
            "right": (mw // 2, 0, mw // 2, mh),
            "top": (0, 0, mw, mh // 2),
            "bottom": (0, mh // 2, mw, mh // 2),
            "top-left": (0, 0, mw // 2, mh // 2),
            "top-right": (mw // 2, 0, mw // 2, mh // 2),
            "bottom-left": (0, mh // 2, mw // 2, mh // 2),
            "bottom-right": (mw // 2, mh // 2, mw // 2, mh // 2),
            "center": (mw // 4, mh // 4, mw // 2, mh // 2),
            "full": (0, 0, mw, mh),
        }
        
        bounds = positions.get(position)
        if not bounds:
            return False
        
        return await self.move_window(window_id, *bounds)
    
    # ── Event Monitoring ────────────────────────────────────
    
    def on_window_created(self, callback: Callable) -> None:
        """Register callback for window creation events.
        
        Args:
            callback: Function receiving WindowInfo
        """
        self._window_created_callbacks.append(callback)
    
    def on_window_closed(self, callback: Callable) -> None:
        """Register callback for window close events.
        
        Args:
            callback: Function receiving window_id
        """
        self._window_closed_callbacks.append(callback)
    
    def on_window_focus_changed(self, callback: Callable) -> None:
        """Register callback for focus change events.
        
        Args:
            callback: Function receiving WindowInfo
        """
        self._window_focus_callbacks.append(callback)
    
    async def _monitor_loop(self) -> None:
        """Monitor window changes."""
        previous_windows: Set[str] = set()
        
        while self._running:
            try:
                current = await self.list_windows()
                current_ids = {w.id for w in current}
                
                # Detect new windows
                new_ids = current_ids - previous_windows
                for wid in new_ids:
                    window = self._windows.get(wid)
                    if window:
                        for cb in self._window_created_callbacks:
                            try:
                                cb(window)
                            except Exception:
                                pass
                
                # Detect closed windows
                closed_ids = previous_windows - current_ids
                for wid in closed_ids:
                    for cb in self._window_closed_callbacks:
                        try:
                            cb(wid)
                        except Exception:
                            pass
                
                previous_windows = current_ids
                await asyncio.sleep(self._poll_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Window monitor error: %s", exc)
                await asyncio.sleep(5.0)
    
    # ── Platform-specific Implementations ───────────────────
    
    @staticmethod
    def _is_windows() -> bool:
        import platform
        return platform.system() == "Windows"
    
    async def _enum_windows_win32(self) -> List[WindowInfo]:
        """Enumerate windows using Win32 API."""
        import win32gui
        import win32process
        import win32con
        
        windows = []
        
        def callback(hwnd, _windows):
            if not win32gui.IsWindowVisible(hwnd):
                return
            
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                import psutil
                process = psutil.Process(pid)
                process_name = process.name()
            except Exception:
                process_name = f"pid:{pid}"
            
            rect = win32gui.GetWindowRect(hwnd)
            placement = win32gui.GetWindowPlacement(hwnd)
            state_map = {
                win32con.SW_SHOWMINIMIZED: WindowState.MINIMIZED,
                win32con.SW_SHOWMAXIMIZED: WindowState.MAXIMIZED,
            }
            state = state_map.get(placement[1], WindowState.NORMAL)
            
            window = WindowInfo(
                id=str(hwnd),
                title=title,
                process_name=process_name,
                process_id=pid,
                bounds=(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]),
                state=state,
                is_visible=True,
            )
            _windows.append(window)
        
        win32gui.EnumWindows(callback, windows)
        return windows
    
    async def _get_active_window_win32(self) -> Optional[WindowInfo]:
        """Get active window using Win32 API."""
        import win32gui
        import win32process
        
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        
        windows = await self._enum_windows_win32()
        for w in windows:
            if w.id == str(hwnd):
                return w
        return None
    
    async def _focus_window_win32(self, window_id: str) -> bool:
        """Focus a window using Win32 API."""
        import win32gui
        import win32con
        
        hwnd = int(window_id)
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    
    async def _minimize_window_win32(self, window_id: str) -> bool:
        import win32gui
        import win32con
        hwnd = int(window_id)
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return True
    
    async def _maximize_window_win32(self, window_id: str) -> bool:
        import win32gui
        import win32con
        hwnd = int(window_id)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return True
    
    async def _restore_window_win32(self, window_id: str) -> bool:
        import win32gui
        import win32con
        hwnd = int(window_id)
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        return True
    
    async def _close_window_win32(self, window_id: str) -> bool:
        import win32gui
        import win32con
        hwnd = int(window_id)
        win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return True
    
    async def _move_window_win32(self, window_id: str, x: int, y: int,
                                   width: Optional[int] = None,
                                   height: Optional[int] = None) -> bool:
        import win32gui
        import win32con
        
        hwnd = int(window_id)
        if width and height:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, x, y, width, height,
                                   win32con.SWP_SHOWWINDOW)
        else:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, x, y, 0, 0,
                                   win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        return True
    
    async def _enum_windows_xdg(self) -> List[WindowInfo]:
        """Enumerate windows using XDG (Linux/macOS fallback)."""
        # Fallback using wmctrl or osascript
        import subprocess
        
        try:
            if self._is_windows():
                return []
            
            result = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True, text=True, timeout=5
            )
            windows = []
            for line in result.stdout.splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    win_id, desktop, pid, title = parts
                    windows.append(WindowInfo(
                        id=win_id,
                        title=title,
                        process_name=pid,
                        process_id=int(pid) if pid.isdigit() else 0,
                    ))
            return windows
        except Exception:
            return []
    
    async def _get_active_window_xdg(self) -> Optional[WindowInfo]:
        import subprocess
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout:
                windows = await self._enum_windows_xdg()
                for w in windows:
                    if w.title == result.stdout.strip():
                        return w
        except Exception:
            pass
        return None
    
    async def _focus_window_xdg(self, window_id: str) -> bool:
        import subprocess
        try:
            subprocess.run(["xdotool", "windowactivate", window_id], timeout=5)
            return True
        except Exception:
            return False
    
    async def _get_monitor_bounds(self) -> List[tuple]:
        """Get monitor bounds."""
        monitors = []
        try:
            import win32api
            import win32con
            
            i = 0
            while True:
                monitor = win32api.EnumDisplayMonitors(None, None)[i]
                monitors.append(monitor[2])  # (left, top, right, bottom)
                i += 1
        except Exception:
            # Fallback to single monitor
            monitors.append((0, 0, 1920, 1080))
        
        return monitors
    
    # ── Stats ───────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        return {**self._stats}


# Global singleton
_window_manager: Optional[WindowManager] = None


def get_window_manager() -> WindowManager:
    """Get or create the global WindowManager singleton."""
    global _window_manager
    if _window_manager is None:
        _window_manager = WindowManager()
    return _window_manager
