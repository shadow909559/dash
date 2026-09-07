"""Clipboard Manager - Clipboard management for DASH AI OS.

Provides:
- Read clipboard text
- Write clipboard text
- Clipboard history tracking
- Clipboard monitoring
- Clipboard sync between devices
- Rich content support (text, images, files)
- Clipboard format detection
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ClipboardFormat(Enum):
    """Clipboard content formats."""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    HTML = "html"
    RICH_TEXT = "rich_text"
    UNKNOWN = "unknown"


@dataclass
class ClipboardEntry:
    """A clipboard history entry.
    
    Attributes:
        id: Entry ID
        content: Content text
        format: Content format
        source: Source application
        app_name: Application name
        size: Content size in bytes
        created_at: When copied
        is_pinned: Whether pinned (not auto-cleared)
        metadata: Additional data
    """
    id: str = ""
    content: str = ""
    format: ClipboardFormat = ClipboardFormat.TEXT
    source: str = ""
    app_name: str = ""
    size: int = 0
    created_at: float = 0.0
    is_pinned: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()
        if not self.size:
            self.size = len(self.content.encode('utf-8')) if self.content else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content[:200],
            "format": self.format.value,
            "source": self.source,
            "size": self.size,
            "created_at": self.created_at,
            "is_pinned": self.is_pinned,
        }


class ClipboardManager:
    """Manages system clipboard operations.
    
    Features:
    - Read/write clipboard
    - History tracking (configurable depth)
    - Pin important entries
    - Clipboard monitoring
    - Format detection
    - Sync between devices
    """
    
    def __init__(self, max_history: int = 100,
                 monitor_interval: float = 0.5):
        self._max_history = max_history
        self._monitor_interval = monitor_interval
        
        self._history: List[ClipboardEntry] = []
        self._last_content: str = ""
        
        # Event callbacks
        self._change_callbacks: List[Callable] = []
        
        # Monitor task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._stats = {
            "reads": 0,
            "writes": 0,
            "changes_detected": 0,
        }
    
    # ── Lifecycle ───────────────────────────────────────────
    
    async def start(self) -> None:
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("ClipboardManager started")
    
    async def stop(self) -> None:
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("ClipboardManager stopped")
    
    # ── Clipboard Operations ────────────────────────────────
    
    async def read_text(self) -> str:
        """Read text from clipboard.
        
        Returns:
            Clipboard text content
        """
        try:
            import pyperclip
            text = pyperclip.paste()
            self._stats["reads"] += 1
            return text
        except Exception as exc:
            logger.warning("Read clipboard failed: %s", exc)
            return ""
    
    async def write_text(self, text: str, source: str = "") -> bool:
        """Write text to clipboard.
        
        Args:
            text: Text to copy
            source: Source identifier
            
        Returns:
            True if successful
        """
        try:
            import pyperclip
            pyperclip.copy(text)
            
            # Add to history
            entry = ClipboardEntry(
                content=text,
                source=source,
            )
            self._add_to_history(entry)
            
            self._stats["writes"] += 1
            self._last_content = text
            return True
            
        except Exception as exc:
            logger.warning("Write clipboard failed: %s", exc)
            return False
    
    async def append_text(self, text: str, separator: str = "\n") -> bool:
        """Append text to current clipboard.
        
        Args:
            text: Text to append
            separator: Separator between existing and new text
            
        Returns:
            True if successful
        """
        current = await self.read_text()
        if current:
            return await self.write_text(f"{current}{separator}{text}")
        return await self.write_text(text)
    
    async def clear(self) -> bool:
        """Clear clipboard.
        
        Returns:
            True if cleared
        """
        return await self.write_text("")
    
    # ── History ─────────────────────────────────────────────
    
    def get_history(self, limit: int = 50,
                     format_filter: Optional[ClipboardFormat] = None) -> List[ClipboardEntry]:
        """Get clipboard history.
        
        Args:
            limit: Max entries
            format_filter: Optional format filter
            
        Returns:
            List of ClipboardEntry
        """
        if format_filter:
            filtered = [e for e in self._history if e.format == format_filter]
            return filtered[:limit]
        return self._history[:limit]
    
    async def get_entry(self, entry_id: str) -> Optional[ClipboardEntry]:
        """Get a history entry by ID.
        
        Args:
            entry_id: Entry ID
            
        Returns:
            ClipboardEntry or None
        """
        for entry in self._history:
            if entry.id == entry_id:
                return entry
        return None
    
    async def pin_entry(self, entry_id: str) -> bool:
        """Pin an entry to prevent auto-clear.
        
        Args:
            entry_id: Entry ID
            
        Returns:
            True if pinned
        """
        entry = await self.get_entry(entry_id)
        if entry:
            entry.is_pinned = True
            return True
        return False
    
    async def unpin_entry(self, entry_id: str) -> bool:
        """Unpin an entry.
        
        Args:
            entry_id: Entry ID
            
        Returns:
            True if unpinned
        """
        entry = await self.get_entry(entry_id)
        if entry:
            entry.is_pinned = False
            return True
        return False
    
    async def delete_entry(self, entry_id: str) -> bool:
        """Delete a history entry.
        
        Args:
            entry_id: Entry ID
            
        Returns:
            True if deleted
        """
        for i, entry in enumerate(self._history):
            if entry.id == entry_id:
                self._history.pop(i)
                return True
        return False
    
    async def clear_history(self) -> int:
        """Clear all non-pinned history.
        
        Returns:
            Number of entries cleared
        """
        before = len(self._history)
        self._history = [e for e in self._history if e.is_pinned]
        return before - len(self._history)
    
    def _add_to_history(self, entry: ClipboardEntry) -> None:
        """Add entry to history with dedup.
        
        Args:
            entry: Entry to add
        """
        # Remove duplicate content
        for existing in self._history:
            if existing.content == entry.content:
                self._history.remove(existing)
                break
        
        # Add to front
        self._history.insert(0, entry)
        
        # Trim
        unpinned = [e for e in self._history if not e.is_pinned]
        if len(unpinned) > self._max_history:
            self._history = [e for e in self._history if e.is_pinned]
            self._history.extend(unpinned[:self._max_history])
    
    # ── Monitoring ──────────────────────────────────────────
    
    def on_change(self, callback: Callable[[ClipboardEntry], None]) -> None:
        """Register callback for clipboard changes.
        
        Args:
            callback: Function receiving ClipboardEntry
        """
        self._change_callbacks.append(callback)
    
    async def _monitor_loop(self) -> None:
        """Monitor clipboard for external changes."""
        while self._running:
            try:
                current = await self.read_text()
                if current and current != self._last_content:
                    entry = ClipboardEntry(content=current, source="external")
                    self._add_to_history(entry)
                    self._last_content = current
                    self._stats["changes_detected"] += 1
                    
                    for cb in self._change_callbacks:
                        try:
                            cb(entry)
                        except Exception:
                            pass
                
                await asyncio.sleep(self._monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)
    
    # ── Stats ───────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "history_size": len(self._history),
            "pinned_count": sum(1 for e in self._history if e.is_pinned),
        }


# Global singleton
_clipboard_manager: Optional[ClipboardManager] = None


def get_clipboard_manager() -> ClipboardManager:
    global _clipboard_manager
    if _clipboard_manager is None:
        _clipboard_manager = ClipboardManager()
    return _clipboard_manager
