"""Keyboard Controller - Keyboard input automation for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class KeyCombo:
    """Keyboard key combination."""
    modifiers: List[str]
    key: str


class KeyboardController:
    """Controls keyboard input.
    
    Features:
    - Type text
    - Press individual keys
    - Press key combinations (hotkeys)
    - Hold and release keys
    - Special keys (Enter, Tab, etc.)
    """
    
    def __init__(self):
        self._pressed_keys: set = set()
        
    async def type_text(self, text: str, delay: float = 0.01) -> bool:
        """Type text character by character.
        
        Args:
            text: Text to type
            delay: Delay between keystrokes
            
        Returns:
            True if successful
        """
        try:
            for char in text:
                await self._type_char(char, delay)
            logger.debug("Typed text: %s", text[:50])
            return True
        except Exception as e:
            logger.error("Type text failed: %s", e)
            return False
    
    async def press_key(self, key: str) -> bool:
        """Press and release a single key.
        
        Args:
            key: Key to press
            
        Returns:
            True if successful
        """
        try:
            await self._key_down(key)
            await asyncio.sleep(0.05)
            await self._key_up(key)
            logger.debug("Pressed key: %s", key)
            return True
        except Exception as e:
            logger.error("Press key failed: %s", e)
            return False
    
    async def press_combo(self, combo: KeyCombo) -> bool:
        """Press a key combination (hotkey).
        
        Args:
            combo: Key combination
            
        Returns:
            True if successful
        """
        try:
            # Press modifiers
            for modifier in combo.modifiers:
                await self._key_down(modifier)
            
            await asyncio.sleep(0.05)
            
            # Press main key
            await self._key_down(combo.key)
            await asyncio.sleep(0.05)
            await self._key_up(combo.key)
            
            # Release modifiers
            for modifier in reversed(combo.modifiers):
                await self._key_up(modifier)
            
            logger.debug("Pressed combo: %s+%s", "+".join(combo.modifiers), combo.key)
            return True
        except Exception as e:
            logger.error("Press combo failed: %s", e)
            return False
    
    async def key_down(self, key: str) -> bool:
        """Hold a key down.
        
        Args:
            key: Key to hold
            
        Returns:
            True if successful
        """
        try:
            await self._key_down(key)
            self._pressed_keys.add(key)
            logger.debug("Key down: %s", key)
            return True
        except Exception as e:
            logger.error("Key down failed: %s", e)
            return False
    
    async def key_up(self, key: str) -> bool:
        """Release a held key.
        
        Args:
            key: Key to release
            
        Returns:
            True if successful
        """
        try:
            await self._key_up(key)
            self._pressed_keys.discard(key)
            logger.debug("Key up: %s", key)
            return True
        except Exception as e:
            logger.error("Key up failed: %s", e)
            return False
    
    async def release_all(self) -> bool:
        """Release all pressed keys.
        
        Returns:
            True if successful
        """
        for key in list(self._pressed_keys):
            await self.key_up(key)
        logger.debug("Released all keys")
        return True
    
    # ── Platform Implementations ─────────────────────────────
    
    def _is_windows(self) -> bool:
        import platform
        return platform.system() == "Windows"
    
    async def _type_char(self, char: str, delay: float) -> None:
        """Type a single character."""
        if self._is_windows():
            await self._type_char_win32(char)
        else:
            await self._type_char_xdg(char)
        await asyncio.sleep(delay)
    
    async def _type_char_win32(self, char: str) -> None:
        import win32api
        import win32con
        
        # Send the character
        win32api.keybd_event(
            win32con.VK_SPACE,  # This is a placeholder
            0,
            win32con.KEYEVENTF_UNICODE,
            ord(char)
        )
        win32api.keybd_event(
            win32con.VK_SPACE,
            0,
            win32con.KEYEVENTF_UNICODE | win32con.KEYEVENTF_KEYUP,
            ord(char)
        )
    
    async def _type_char_xdg(self, char: str) -> None:
        import subprocess
        subprocess.run(["xdotool", "type", char])
    
    async def _key_down(self, key: str) -> None:
        if self._is_windows():
            await self._key_down_win32(key)
        else:
            await self._key_down_xdg(key)
    
    async def _key_up(self, key: str) -> None:
        if self._is_windows():
            await self._key_up_win32(key)
        else:
            await self._key_up_xdg(key)
    
    async def _key_down_win32(self, key: str) -> None:
        import win32api
        import win32con
        
        vk_code = self._get_vk_code(key)
        if vk_code:
            win32api.keybd_event(vk_code, 0, 0, 0)
    
    async def _key_up_win32(self, key: str) -> None:
        import win32api
        import win32con
        
        vk_code = self._get_vk_code(key)
        if vk_code:
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
    
    async def _key_down_xdg(self, key: str) -> None:
        import subprocess
        key_code = self._get_xdg_key_code(key)
        if key_code:
            subprocess.run(["xdotool", "keydown", key_code])
    
    async def _key_up_xdg(self, key: str) -> None:
        import subprocess
        key_code = self._get_xdg_key_code(key)
        if key_code:
            subprocess.run(["xdotool", "keyup", key_code])
    
    def _get_vk_code(self, key: str) -> Optional[int]:
        """Get Windows virtual key code."""
        import win32con
        
        key_map = {
            "enter": win32con.VK_RETURN,
            "return": win32con.VK_RETURN,
            "tab": win32con.VK_TAB,
            "space": win32con.VK_SPACE,
            "escape": win32con.VK_ESCAPE,
            "esc": win32con.VK_ESCAPE,
            "backspace": win32con.VK_BACK,
            "delete": win32con.VK_DELETE,
            "home": win32con.VK_HOME,
            "end": win32con.VK_END,
            "up": win32con.VK_UP,
            "down": win32con.VK_DOWN,
            "left": win32con.VK_LEFT,
            "right": win32con.VK_RIGHT,
            "ctrl": win32con.VK_CONTROL,
            "control": win32con.VK_CONTROL,
            "shift": win32con.VK_SHIFT,
            "alt": win32con.VK_MENU,
            "f1": win32con.VK_F1,
            "f2": win32con.VK_F2,
            "f3": win32con.VK_F3,
            "f4": win32con.VK_F4,
            "f5": win32con.VK_F5,
            "f6": win32con.VK_F6,
            "f7": win32con.VK_F7,
            "f8": win32con.VK_F8,
            "f9": win32con.VK_F9,
            "f10": win32con.VK_F10,
            "f11": win32con.VK_F11,
            "f12": win32con.VK_F12,
        }
        
        return key_map.get(key.lower())
    
    def _get_xdg_key_code(self, key: str) -> Optional[str]:
        """Get XDG key code."""
        key_map = {
            "enter": "Return",
            "return": "Return",
            "tab": "Tab",
            "space": "space",
            "escape": "Escape",
            "esc": "Escape",
            "backspace": "BackSpace",
            "delete": "Delete",
            "home": "Home",
            "end": "End",
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
            "ctrl": "Control",
            "control": "Control",
            "shift": "Shift",
            "alt": "Alt",
            "f1": "F1",
            "f2": "F2",
            "f3": "F3",
            "f4": "F4",
            "f5": "F5",
            "f6": "F6",
            "f7": "F7",
            "f8": "F8",
            "f9": "F9",
            "f10": "F10",
            "f11": "F11",
            "f12": "F12",
        }
        
        return key_map.get(key.lower(), key)


_keyboard_controller: Optional[KeyboardController] = None


def get_keyboard_controller() -> KeyboardController:
    global _keyboard_controller
    if _keyboard_controller is None:
        _keyboard_controller = KeyboardController()
    return _keyboard_controller
