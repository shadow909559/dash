"""Tab Manager - Browser tab management for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TabInfo:
    id: str = ""
    title: str = ""
    url: str = ""
    favicon: str = ""
    is_active: bool = False
    is_loading: bool = False
    created_at: float = 0.0
    order: int = 0
    muted: bool = False
    pinned: bool = False
    group_id: Optional[str] = None


class TabManager:
    def __init__(self):
        self._tabs: Dict[str, TabInfo] = {}
        self._active_tab_id: Optional[str] = None
        self._change_callbacks: List[Callable] = []
        self._page = None  # Playwright page
    
    async def initialize(self, page) -> None:
        self._page = page
    
    async def list_tabs(self) -> List[TabInfo]:
        if not self._page:
            return list(self._tabs.values())
        try:
            context = self._page.context
            pages = context.pages
            tabs = []
            for i, p in enumerate(pages):
                tab = TabInfo(
                    id=str(id(p)),
                    title=await p.title(),
                    url=p.url,
                    is_active=p == self._page,
                    order=i,
                )
                tabs.append(tab)
                self._tabs[tab.id] = tab
            return tabs
        except Exception as exc:
            logger.warning("List tabs failed: %s", exc)
            return list(self._tabs.values())
    
    async def switch_tab(self, tab_id: str) -> bool:
        try:
            context = self._page.context
            for p in context.pages:
                if str(id(p)) == tab_id:
                    await p.bring_to_front()
                    self._page = p
                    return True
            return False
        except Exception:
            return False
    
    async def close_tab(self, tab_id: str) -> bool:
        try:
            context = self._page.context
            for p in context.pages:
                if str(id(p)) == tab_id:
                    await p.close()
                    self._tabs.pop(tab_id, None)
                    return True
            return False
        except Exception:
            return False
    
    async def create_tab(self, url: str = "") -> Optional[str]:
        try:
            context = self._page.context
            p = await context.new_page()
            if url:
                await p.goto(url)
            tab_id = str(id(p))
            self._tabs[tab_id] = TabInfo(id=tab_id, url=url, title=url or "New Tab")
            return tab_id
        except Exception:
            return None
    
    def on_tab_changed(self, callback: Callable) -> None:
        self._change_callbacks.append(callback)


# Global singleton
_tab_manager: Optional[TabManager] = None


def get_tab_manager() -> TabManager:
    global _tab_manager
    if _tab_manager is None:
        _tab_manager = TabManager()
    return _tab_manager
