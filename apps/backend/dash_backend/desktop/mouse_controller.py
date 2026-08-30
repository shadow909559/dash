"""Mouse Controller - Mouse input automation for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Screen position."""
    x: int
    y: int


class MouseController:
    """Controls mouse input.
    
    Features:
    - Move mouse to position
    - Click (left, right, middle)
    - Double click
    - Drag and drop
    - Scroll
    - Get current position
    """
    
    def __init__(self):
        self._current_position = Position(0, 0)
        self._is_dragging = False
        self._drag_start: Optional[Position] = None
        
    async def move_to(self, x: int, y: int, duration: float = 0.1) -> bool:
        """Move mouse to position.
        
        Args:
            x: X coordinate
            y: Y coordinate
            duration: Movement duration in seconds
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                await self._move_to_win32(x, y, duration)
            else:
                await self._move_to_xdg(x, y, duration)
            
            self._current_position = Position(x, y)
            logger.debug("Mouse moved to (%d, %d)", x, y)
            return True
        except Exception as e:
            logger.error("Move mouse failed: %s", e)
            return False
    
    async def click(self, button: str = "left", count: int = 1) -> bool:
        """Click mouse button.
        
        Args:
            button: Button to click (left, right, middle)
            count: Number of clicks
            
        Returns:
            True if successful
        """
        try:
            for _ in range(count):
                if self._is_windows():
                    await self._click_win32(button)
                else:
                    await self._click_xdg(button)
                
                if count > 1:
                    await asyncio.sleep(0.1)
            
            logger.debug("Mouse clicked: %s x%d", button, count)
            return True
        except Exception as e:
            logger.error("Click failed: %s", e)
            return False
    
    async def double_click(self, button: str = "left") -> bool:
        """Double click mouse button.
        
        Args:
            button: Button to click
            
        Returns:
            True if successful
        """
        return await self.click(button, count=2)
    
    async def drag_start(self, x: int, y: int, button: str = "left") -> bool:
        """Start drag operation.
        
        Args:
            x: Start X position
            y: Start Y position
            button: Button to drag with
            
        Returns:
            True if successful
        """
        await self.move_to(x, y)
        self._is_dragging = True
        self._drag_start = Position(x, y)
        
        try:
            if self._is_windows():
                await self._mouse_down_win32(button)
            else:
                await self._mouse_down_xdg(button)
            
            logger.debug("Drag started at (%d, %d)", x, y)
            return True
        except Exception as e:
            logger.error("Drag start failed: %s", e)
            return False
    
    async def drag_to(self, x: int, y: int) -> bool:
        """Continue drag to new position.
        
        Args:
            x: Target X position
            y: Target Y position
            
        Returns:
            True if successful
        """
        if not self._is_dragging:
            logger.warning("No drag in progress")
            return False
        
        await self.move_to(x, y)
        logger.debug("Dragged to (%d, %d)", x, y)
        return True
    
    async def drag_end(self) -> bool:
        """End drag operation.
        
        Returns:
            True if successful
        """
        if not self._is_dragging:
            logger.warning("No drag in progress")
            return False
        
        self._is_dragging = False
        self._drag_start = None
        
        try:
            if self._is_windows():
                await self._mouse_up_win32("left")
            else:
                await self._mouse_up_xdg("left")
            
            logger.debug("Drag ended")
            return True
        except Exception as e:
            logger.error("Drag end failed: %s", e)
            return False
    
    async def scroll(self, amount: int, direction: str = "vertical") -> bool:
        """Scroll mouse wheel.
        
        Args:
            amount: Scroll amount (positive = up/right, negative = down/left)
            direction: Scroll direction (vertical, horizontal)
            
        Returns:
            True if successful
        """
        try:
            if self._is_windows():
                await self._scroll_win32(amount, direction)
            else:
                await self._scroll_xdg(amount, direction)
            
            logger.debug("Scrolled: %d %s", amount, direction)
            return True
        except Exception as e:
            logger.error("Scroll failed: %s", e)
            return False
    
    async def get_position(self) -> Position:
        """Get current mouse position.
        
        Returns:
            Current position
        """
        try:
            if self._is_windows():
                x, y = await self._get_position_win32()
            else:
                x, y = await self._get_position_xdg()
            
            self._current_position = Position(x, y)
            return self._current_position
        except Exception as e:
            logger.error("Get position failed: %s", e)
            return self._current_position
    
    # ── Platform Implementations ─────────────────────────────
    
    def _is_windows(self) -> bool:
        import platform
        return platform.system() == "Windows"
    
    async def _move_to_win32(self, x: int, y: int, duration: float) -> None:
        import ctypes
        import win32api
        import win32con
        
        # Smooth movement
        start_x, start_y = win32api.GetCursorPos()
        steps = int(duration * 60)  # 60 FPS
        for i in range(steps + 1):
            t = i / steps
            curr_x = int(start_x + (x - start_x) * t)
            curr_y = int(start_y + (y - start_y) * t)
            ctypes.windll.user32.SetCursorPos(curr_x, curr_y)
            await asyncio.sleep(duration / steps)
    
    async def _move_to_xdg(self, x: int, y: int, duration: float) -> None:
        import subprocess
        subprocess.run(["xdotool", "mousemove", str(x), str(y)])
    
    async def _click_win32(self, button: str) -> None:
        import win32api
        import win32con
        
        button_map = {
            "left": win32con.MOUSEEVENTF_LEFTDOWN,
            "right": win32con.MOUSEEVENTF_RIGHTDOWN,
            "middle": win32con.MOUSEEVENTF_MIDDLEDOWN,
        }
        
        flags = button_map.get(button, win32con.MOUSEEVENTF_LEFTDOWN)
        win32api.mouse_event(flags, 0, 0, 0, 0)
        win32api.mouse_event(flags | 0x0002, 0, 0, 0, 0)  # UP
    
    async def _click_xdg(self, button: str) -> None:
        import subprocess
        button_map = {
            "left": "1",
            "middle": "2",
            "right": "3",
        }
        btn = button_map.get(button, "1")
        subprocess.run(["xdotool", "click", btn])
    
    async def _mouse_down_win32(self, button: str) -> None:
        import win32api
        import win32con
        
        button_map = {
            "left": win32con.MOUSEEVENTF_LEFTDOWN,
            "right": win32con.MOUSEEVENTF_RIGHTDOWN,
            "middle": win32con.MOUSEEVENTF_MIDDLEDOWN,
        }
        
        flags = button_map.get(button, win32con.MOUSEEVENTF_LEFTDOWN)
        win32api.mouse_event(flags, 0, 0, 0, 0)
    
    async def _mouse_up_win32(self, button: str) -> None:
        import win32api
        import win32con
        
        button_map = {
            "left": win32con.MOUSEEVENTF_LEFTUP,
            "right": win32con.MOUSEEVENTF_RIGHTUP,
            "middle": win32con.MOUSEEVENTF_MIDDLEUP,
        }
        
        flags = button_map.get(button, win32con.MOUSEEVENTF_LEFTUP)
        win32api.mouse_event(flags, 0, 0, 0, 0)
    
    async def _mouse_down_xdg(self, button: str) -> None:
        import subprocess
        button_map = {
            "left": "1",
            "middle": "2",
            "right": "3",
        }
        btn = button_map.get(button, "1")
        subprocess.run(["xdotool", "mousedown", btn])
    
    async def _mouse_up_xdg(self, button: str) -> None:
        import subprocess
        button_map = {
            "left": "1",
            "middle": "2",
            "right": "3",
        }
        btn = button_map.get(button, "1")
        subprocess.run(["xdotool", "mouseup", btn])
    
    async def _scroll_win32(self, amount: int, direction: str) -> None:
        import win32api
        import win32con
        
        if direction == "vertical":
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, amount, 0, 0)
        else:
            win32api.mouse_event(win32con.MOUSEEVENTF_HWHEEL, 0, amount, 0, 0)
    
    async def _scroll_xdg(self, amount: int, direction: str) -> None:
        import subprocess
        if direction == "vertical":
            subprocess.run(["xdotool", "click", str(4 if amount > 0 else 5)])
        else:
            subprocess.run(["xdotool", "click", str(6 if amount > 0 else 7)])
    
    async def _get_position_win32(self) -> Tuple[int, int]:
        import win32api
        return win32api.GetCursorPos()
    
    async def _get_position_xdg(self) -> Tuple[int, int]:
        import subprocess
        result = subprocess.run(
            ["xdotool", "getmouselocation"],
            capture_output=True,
            text=True
        )
        # Parse output: "x:123 y:456 screen:0"
        parts = result.stdout.strip().split()
        x = int(parts[0].split(":")[1])
        y = int(parts[1].split(":")[1])
        return x, y


_mouse_controller: Optional[MouseController] = None


def get_mouse_controller() -> MouseController:
    global _mouse_controller
    if _mouse_controller is None:
        _mouse_controller = MouseController()
    return _mouse_controller
