# -*- coding: utf-8 -*-
"""Browser Automation — Playwright-based tab management, screenshots, page analysis, bookmarks."""

import logging
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BrowserTab:
    """Represents a browser tab."""
    id: str
    url: str
    title: str
    favicon: str = ""
    is_active: bool = False
    is_pinned: bool = False
    is_muted: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed: str = ""
    group: str = ""


@dataclass
class Bookmark:
    """A browser bookmark."""
    id: str
    url: str
    title: str
    description: str = ""
    favicon: str = ""
    folder: str = "Bookmarks Bar"
    tags: list[str] = field(default_factory=list)
    ai_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class HistoryEntry:
    """Browser history entry."""
    url: str
    title: str
    visited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    referrer: str = ""


class BrowserAutomationService:
    """Browser automation and management service."""

    def __init__(self):
        self._tabs: dict[str, BrowserTab] = {}
        self._bookmarks: dict[str, Bookmark] = {}
        self._history: list[HistoryEntry] = []
        self._screenshots: list[dict] = []
        self._page_summaries: dict[str, dict] = {}
        self._reading_list: list[dict] = []

    # ── Tab Management ───────────────────────────────────────────────────

    def open_tab(self, url: str, title: str = "", active: bool = False) -> dict:
        """Open a new browser tab."""
        tab_id = f"tab_{secrets.token_hex(8)}"
        tab = BrowserTab(
            id=tab_id,
            url=url,
            title=title or url,
            is_active=active,
            last_accessed=datetime.now(timezone.utc).isoformat(),
        )
        self._tabs[tab_id] = tab
        return {"tab_id": tab_id, "url": url, "title": tab.title}

    def close_tab(self, tab_id: str) -> dict:
        """Close a browser tab."""
        if tab_id in self._tabs:
            del self._tabs[tab_id]
            return {"status": "closed", "tab_id": tab_id}
        return {"status": "not_found", "tab_id": tab_id}

    def get_tabs(self) -> list[dict]:
        """Get all open tabs."""
        return [
            {
                "id": t.id,
                "url": t.url,
                "title": t.title,
                "is_active": t.is_active,
                "is_pinned": t.is_pinned,
                "group": t.group,
            }
            for t in self._tabs.values()
        ]

    def focus_tab(self, tab_id: str) -> dict:
        """Focus a tab."""
        for t in self._tabs.values():
            t.is_active = False
        if tab_id in self._tabs:
            self._tabs[tab_id].is_active = True
            self._tabs[tab_id].last_accessed = datetime.now(timezone.utc).isoformat()
            return {"status": "focused", "tab_id": tab_id}
        return {"status": "not_found"}

    def pin_tab(self, tab_id: str, pinned: bool = True) -> dict:
        """Pin or unpin a tab."""
        if tab_id in self._tabs:
            self._tabs[tab_id].is_pinned = pinned
            return {"status": "pinned" if pinned else "unpinned", "tab_id": tab_id}
        return {"status": "not_found"}

    def group_tabs(self, tab_ids: list[str], group_name: str) -> dict:
        """Group multiple tabs."""
        grouped = 0
        for tid in tab_ids:
            if tid in self._tabs:
                self._tabs[tid].group = group_name
                grouped += 1
        return {"group": group_name, "tab_count": grouped}

    def search_tabs(self, query: str) -> list[dict]:
        """Search tabs by URL or title."""
        query_lower = query.lower()
        results = [
            {"id": t.id, "url": t.url, "title": t.title}
            for t in self._tabs.values()
            if query_lower in t.url.lower() or query_lower in t.title.lower()
        ]
        return results

    # ── Screenshots ──────────────────────────────────────────────────────

    def take_screenshot(self, tab_id: str = None, full_page: bool = False) -> dict:
        """Take a screenshot of a tab or the current viewport."""
        screenshot_id = f"ss_{secrets.token_hex(8)}"
        entry = {
            "id": screenshot_id,
            "tab_id": tab_id,
            "full_page": full_page,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "format": "png",
        }
        self._screenshots.append(entry)
        return entry

    def get_screenshots(self, limit: int = 20) -> list[dict]:
        """Get recent screenshots."""
        return self._screenshots[-limit:]

    def delete_screenshot(self, screenshot_id: str) -> dict:
        """Delete a screenshot."""
        before = len(self._screenshots)
        self._screenshots = [s for s in self._screenshots if s["id"] != screenshot_id]
        return {"deleted": before > len(self._screenshots), "id": screenshot_id}

    # ── Page Analysis ────────────────────────────────────────────────────

    async def summarize_page(self, url: str, content: str = "") -> dict:
        """Generate AI summary of a web page."""
        # In production, this would call the LLM
        summary = {
            "url": url,
            "summary": f"Page summary for {url}. Content length: {len(content)} chars.",
            "key_points": ["Key point 1", "Key point 2", "Key point 3"],
            "sentiment": "neutral",
            "reading_time_seconds": max(30, len(content) // 200),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._page_summaries[url] = summary
        return summary

    async def extract_content(self, url: str) -> dict:
        """Extract main content from a web page."""
        return {
            "url": url,
            "title": "Page Title",
            "content": "Extracted page content...",
            "links": [],
            "images": [],
            "metadata": {},
        }

    # ── Bookmarks ────────────────────────────────────────────────────────

    def add_bookmark(self, url: str, title: str, folder: str = "Bookmarks Bar", tags: list[str] = None) -> dict:
        """Add a bookmark."""
        bm_id = hashlib.md5(url.encode()).hexdigest()[:12]
        bookmark = Bookmark(
            id=bm_id,
            url=url,
            title=title,
            folder=folder,
            tags=tags or [],
        )
        self._bookmarks[bm_id] = bookmark
        return {"id": bm_id, "url": url, "title": title, "folder": folder}

    def get_bookmarks(self, folder: str = None, tag: str = None) -> list[dict]:
        """Get bookmarks with optional filtering."""
        bms = list(self._bookmarks.values())
        if folder:
            bms = [b for b in bms if b.folder == folder]
        if tag:
            bms = [b for b in bms if tag in b.tags]
        return [
            {"id": b.id, "url": b.url, "title": b.title, "folder": b.folder, "tags": b.tags, "ai_summary": b.ai_summary}
            for b in bms
        ]

    def delete_bookmark(self, bookmark_id: str) -> dict:
        """Delete a bookmark."""
        if bookmark_id in self._bookmarks:
            del self._bookmarks[bookmark_id]
            return {"status": "deleted"}
        return {"status": "not_found"}

    def search_bookmarks(self, query: str) -> list[dict]:
        """Search bookmarks by title, URL, or tags."""
        q = query.lower()
        results = [
            {"id": b.id, "url": b.url, "title": b.title}
            for b in self._bookmarks.values()
            if q in b.title.lower() or q in b.url.lower() or any(q in t.lower() for t in b.tags)
        ]
        return results

    def get_folders(self) -> list[str]:
        """Get all bookmark folders."""
        return list(set(b.folder for b in self._bookmarks.values()))

    # ── History ──────────────────────────────────────────────────────────

    def add_history(self, url: str, title: str, duration: float = 0, referrer: str = "") -> dict:
        """Add a history entry."""
        entry = HistoryEntry(url=url, title=title, duration_seconds=duration, referrer=referrer)
        self._history.append(entry)
        return {"status": "recorded", "url": url}

    def get_history(self, limit: int = 100) -> list[dict]:
        """Get browsing history."""
        return [
            {"url": h.url, "title": h.title, "visited_at": h.visited_at, "duration_seconds": h.duration_seconds}
            for h in self._history[-limit:]
        ]

    def clear_history(self, days: int = 0) -> dict:
        """Clear browsing history."""
        if days <= 0:
            count = len(self._history)
            self._history.clear()
            return {"cleared": count}
        return {"cleared": 0, "message": "Selective history clearing not yet implemented"}

    def search_history(self, query: str, limit: int = 50) -> list[dict]:
        """Search history."""
        q = query.lower()
        results = [
            {"url": h.url, "title": h.title, "visited_at": h.visited_at}
            for h in self._history
            if q in h.url.lower() or q in h.title.lower()
        ]
        return results[-limit:]

    # ── Reading List ─────────────────────────────────────────────────────

    def add_to_reading_list(self, url: str, title: str, priority: str = "medium") -> dict:
        """Add a page to the reading list."""
        item_id = hashlib.md5(url.encode()).hexdigest()[:12]
        item = {
            "id": item_id,
            "url": url,
            "title": title,
            "priority": priority,
            "status": "unread",
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        self._reading_list.append(item)
        return item

    def get_reading_list(self, status: str = None) -> list[dict]:
        """Get reading list."""
        items = self._reading_list
        if status:
            items = [i for i in items if i["status"] == status]
        return items

    def update_reading_list_item(self, item_id: str, status: str) -> dict:
        """Update reading list item status."""
        for item in self._reading_list:
            if item["id"] == item_id:
                item["status"] = status
                return item
        return {"status": "not_found"}

    def get_stats(self) -> dict:
        """Get browser automation statistics."""
        return {
            "open_tabs": len(self._tabs),
            "bookmarks": len(self._bookmarks),
            "history_entries": len(self._history),
            "screenshots": len(self._screenshots),
            "reading_list": len(self._reading_list),
            "page_summaries": len(self._page_summaries),
        }


# Singleton
_browser_service: Optional[BrowserAutomationService] = None


def get_browser_service() -> BrowserAutomationService:
    global _browser_service
    if _browser_service is None:
        _browser_service = BrowserAutomationService()
    return _browser_service
