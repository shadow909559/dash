"""Hotkey management for voice control."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Hotkey:
    """Represents a hotkey binding."""
    key: str
    modifiers: list[str]
    action: str
    description: str


class HotkeyManager:
    """Manages hotkey bindings for voice control.
    
    Features:
    - Global hotkey registration
    - Push-to-talk hotkeys
    - Voice toggle hotkeys
    - Custom hotkey bindings
    """
    
    def __init__(self):
        self._hotkeys: Dict[str, Hotkey] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._enabled = True
        
        # Default hotkeys
        self._register_defaults()
    
    def _register_defaults(self) -> None:
        """Register default hotkey bindings."""
        defaults = [
            Hotkey(
                key="space",
                modifiers=["ctrl"],
                action="push_to_talk",
                description="Push to talk (hold to speak)",
            ),
            Hotkey(
                key="v",
                modifiers=["ctrl", "shift"],
                action="toggle_voice",
                description="Toggle voice mode",
            ),
            Hotkey(
                key="i",
                modifiers=["ctrl"],
                action="interrupt",
                description="Interrupt speech",
            ),
            Hotkey(
                key="m",
                modifiers=["ctrl"],
                action="toggle_mute",
                description="Toggle microphone",
            ),
        ]
        
        for hotkey in defaults:
            self.register(hotkey)
    
    def register(self, hotkey: Hotkey) -> None:
        """Register a hotkey binding."""
        key_id = self._make_key_id(hotkey.key, hotkey.modifiers)
        self._hotkeys[key_id] = hotkey
        logger.info("Registered hotkey: %s -> %s", key_id, hotkey.action)
    
    def unregister(self, key: str, modifiers: list[str]) -> None:
        """Unregister a hotkey binding."""
        key_id = self._make_key_id(key, modifiers)
        self._hotkeys.pop(key_id, None)
        self._callbacks.pop(key_id, None)
        logger.info("Unregistered hotkey: %s", key_id)
    
    def bind(self, key: str, modifiers: list[str], callback: Callable) -> None:
        """Bind a callback to a hotkey."""
        key_id = self._make_key_id(key, modifiers)
        self._callbacks[key_id] = callback
        logger.info("Bound callback to hotkey: %s", key_id)
    
    async def trigger(self, key: str, modifiers: list[str]) -> Optional[Any]:
        """Trigger a hotkey action."""
        if not self._enabled:
            return None
            
        key_id = self._make_key_id(key, modifiers)
        
        # Check for callback first
        if key_id in self._callbacks:
            try:
                result = self._callbacks[key_id]()
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            except Exception as e:
                logger.error("Hotkey callback error: %s", e)
        
        # Check for registered hotkey
        if key_id in self._hotkeys:
            hotkey = self._hotkeys[key_id]
            logger.info("Hotkey triggered: %s (%s)", key_id, hotkey.action)
            return hotkey.action
        
        return None
    
    def _make_key_id(self, key: str, modifiers: list[str]) -> str:
        """Create a unique ID for a hotkey combination."""
        sorted_modifiers = sorted(modifiers)
        return "+".join(sorted_modifiers + [key])
    
    def get_hotkeys(self) -> Dict[str, Hotkey]:
        """Get all registered hotkeys."""
        return self._hotkeys.copy()
    
    def enable(self) -> None:
        """Enable hotkey processing."""
        self._enabled = True
        logger.info("Hotkeys enabled")
    
    def disable(self) -> None:
        """Disable hotkey processing."""
        self._enabled = False
        logger.info("Hotkeys disabled")
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled


_hotkey_manager: Optional[HotkeyManager] = None


def get_hotkey_manager() -> HotkeyManager:
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = HotkeyManager()
    return _hotkey_manager
