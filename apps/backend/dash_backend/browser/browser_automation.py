"""Browser Automation - Playwright integration for DASH AI OS.

Provides:
- Browser automation (navigation, clicks, form filling)
- Tab management
- Bookmark management
- Downloads management
- Reading mode
- Website summarization
- Fact checking
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class BrowserType(Enum):
    """Browser types."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


@dataclass
class TabInfo:
    """Information about a browser tab."""
    id: str
    url: str
    title: str
    is_active: bool = False
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "is_active": self.is_active,
        }


@dataclass
class Bookmark:
    """Browser bookmark."""
    id: str
    url: str
    title: str
    folder: str = ""
    created_at: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "folder": self.folder,
            "created_at": self.created_at,
        }


class BrowserAutomation:
    """Browser automation using Playwright.
    
    Features:
    - Browser lifecycle management
    - Tab management (create, close, switch)
    - Navigation (go to, back, forward, refresh)
    - Element interaction (click, type, select)
    - Form filling
    - Screenshot capture
    - Content extraction
    - Bookmark management
    - Download management
    """
    
    def __init__(
        self,
        browser_type: BrowserType = BrowserType.CHROMIUM,
        headless: bool = True,
    ):
        self.browser_type = browser_type
        self.headless = headless
        self._browser = None
        self._context = None
        self._tabs: Dict[str, Any] = {}
        self._active_tab_id: Optional[str] = None
        self._bookmarks: List[Bookmark] = []
        self._running = False
        
    async def start(self) -> bool:
        """Start the browser.
        
        Returns:
            True if successful
        """
        try:
            from playwright.async_api import async_playwright
            
            self._playwright = await async_playwright().start()
            
            browser_map = {
                BrowserType.CHROMIUM: self._playwright.chromium,
                BrowserType.FIREFOX: self._playwright.firefox,
                BrowserType.WEBKIT: self._playwright.webkit,
            }
            
            browser_launcher = browser_map.get(self.browser_type, self._playwright.chromium)
            self._browser = await browser_launcher.launch(headless=self.headless)
            self._context = await self._browser.new_context()
            
            # Create initial tab
            initial_page = await self._context.new_page()
            tab_id = str(id(initial_page))
            self._tabs[tab_id] = initial_page
            self._active_tab_id = tab_id
            
            self._running = True
            logger.info("Browser started: %s (headless=%s)", self.browser_type.value, self.headless)
            return True
            
        except ImportError:
            logger.error("Playwright not installed")
            return False
        except Exception as e:
            logger.error("Browser start failed: %s", e)
            return False
    
    async def stop(self) -> None:
        """Stop the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if hasattr(self, '_playwright'):
            await self._playwright.stop()
        
        self._tabs.clear()
        self._active_tab_id = None
        self._running = False
        logger.info("Browser stopped")
    
    async def navigate(self, url: str, tab_id: Optional[str] = None) -> bool:
        """Navigate to a URL.
        
        Args:
            url: URL to navigate to
            tab_id: Tab ID (uses active tab if None)
            
        Returns:
            True if successful
        """
        page = self._get_page(tab_id)
        if not page:
            return False
        
        try:
            await page.goto(url)
            logger.info("Navigated to: %s", url)
            return True
        except Exception as e:
            logger.error("Navigation failed: %s", e)
            return False
    
    async def go_back(self, tab_id: Optional[str] = None) -> bool:
        """Go back in history.
        
        Args:
            tab_id: Tab ID
            
        Returns:
            True if successful
        """
        page = self._get_page(tab_id)
        if not page:
            return False
        
        try:
            await page.go_back()
            return True
        except Exception as e:
            logger.error("Go back failed: %s", e)
            return False
    
    async def go_forward(self, tab_id: Optional[str] = None) -> bool:
        """Go forward in history.
        
        Args:
            tab_id: Tab ID
            
        Returns:
            True if successful
        """
        page = self._get_page(tab_id)
        if not page:
            return False
        
        try:
            await page.go_forward()
            return True
        except Exception as e:
            logger.error("Go forward failed: %s", e)
            return False
    
    async def refresh(self, tab_id: Optional[str] = None) -> bool:
        """Refresh the current page.
        
        Args:
            tab_id: Tab ID
            
        Returns:
            True if successful
        """
        page = self._get_page(tab_id)
        if not page:
            return False
        
        try:
            await page.reload()
            return True
        except Exception as e:
            logger.error("Refresh failed: %s", e)
            return False
    
    async def click(self, selector: str, tab_id: Optional[str] = None) -> bool:
        """Click an element.
        
        Args:
            selector: CSS selector
            tab_id: Tab ID
            
        Returns:
            True if successful
        """
        page = self._get_page(tab_id)
        if not page:
            return False
        
        try:
            await page.click(selector)
            return True
        except Exception as e:
            logger.error("Click failed: %s", e)
            return False
    
    async def type_text(self, selector: str, text: str, tab_id: Optional[str] = None) -> bool:
        """Type text into an element.
        
        Args:
            selector: CSS selector
            text: Text to type
            tab_id: Tab ID
            
        Returns:
            True if successful
        """
        page = self._get_page(tab_id)
        if not page:
            return False
        
        try:
            await page.fill(selector, text)
            return True
        except Exception as e:
            logger.error("Type text failed: %s", e)
            return False
    
    async def get_text(self, selector: str, tab_id: Optional[str] = None) -> Optional[str]:
        """Get text from an element.
        
        Args:
            selector: CSS selector
            tab_id: Tab ID
            
        Returns:
            Element text or None
        """
        page = self._get_page(tab_id)
        if not page:
            return None
        
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.text_content()
        except Exception as e:
            logger.error("Get text failed: %s", e)
        
        return None
    
    async def screenshot(self, path: str, tab_id: Optional[str] = None) -> bool:
        """Take a screenshot.
        
        Args:
            path: Save path
            tab_id: Tab ID
            
        Returns:
            True if successful
        """
        page = self._get_page(tab_id)
        if not page:
            return False
        
        try:
            await page.screenshot(path=path)
            return True
        except Exception as e:
            logger.error("Screenshot failed: %s", e)
            return False
    
    async def get_page_content(self, tab_id: Optional[str] = None) -> Optional[str]:
        """Get the full page content.
        
        Args:
            tab_id: Tab ID
            
        Returns:
            Page content or None
        """
        page = self._get_page(tab_id)
        if not page:
            return None
        
        try:
            return await page.content()
        except Exception as e:
            logger.error("Get page content failed: %s", e)
            return None
    
    async def create_tab(self, url: str = "about:blank") -> Optional[str]:
        """Create a new tab.
        
        Args:
            url: Initial URL
            
        Returns:
            New tab ID or None
        """
        if not self._context:
            return None
        
        try:
            page = await self._context.new_page()
            await page.goto(url)
            
            tab_id = str(id(page))
            self._tabs[tab_id] = page
            
            logger.info("Created tab: %s", tab_id)
            return tab_id
        except Exception as e:
            logger.error("Create tab failed: %s", e)
            return None
    
    async def close_tab(self, tab_id: str) -> bool:
        """Close a tab.
        
        Args:
            tab_id: Tab ID
            
        Returns:
            True if successful
        """
        page = self._tabs.get(tab_id)
        if not page:
            return False
        
        try:
            await page.close()
            del self._tabs[tab_id]
            
            if self._active_tab_id == tab_id:
                self._active_tab_id = next(iter(self._tabs), None)
            
            logger.info("Closed tab: %s", tab_id)
            return True
        except Exception as e:
            logger.error("Close tab failed: %s", e)
            return False
    
    async def switch_tab(self, tab_id: str) -> bool:
        """Switch to a tab.
        
        Args:
            tab_id: Tab ID
            
        Returns:
            True if successful
        """
        if tab_id not in self._tabs:
            return False
        
        self._active_tab_id = tab_id
        logger.info("Switched to tab: %s", tab_id)
        return True
    
    async def list_tabs(self) -> List[TabInfo]:
        """List all tabs.
        
        Returns:
            List of TabInfo
        """
        tabs = []
        for tab_id, page in self._tabs.items():
            try:
                title = await page.title()
                url = page.url
                tabs.append(TabInfo(
                    id=tab_id,
                    url=url,
                    title=title,
                    is_active=(tab_id == self._active_tab_id),
                ))
            except Exception:
                tabs.append(TabInfo(
                    id=tab_id,
                    url="",
                    title="Error loading",
                    is_active=(tab_id == self._active_tab_id),
                ))
        
        return tabs
    
    async def add_bookmark(self, url: str, title: str, folder: str = "") -> Optional[str]:
        """Add a bookmark.
        
        Args:
            url: Bookmark URL
            title: Bookmark title
            folder: Bookmark folder
            
        Returns:
            Bookmark ID or None
        """
        import time
        
        bookmark_id = str(hash(url + title))
        bookmark = Bookmark(
            id=bookmark_id,
            url=url,
            title=title,
            folder=folder,
            created_at=time.time(),
        )
        
        self._bookmarks.append(bookmark)
        logger.info("Added bookmark: %s", title)
        return bookmark_id
    
    async def remove_bookmark(self, bookmark_id: str) -> bool:
        """Remove a bookmark.
        
        Args:
            bookmark_id: Bookmark ID
            
        Returns:
            True if successful
        """
        for i, bookmark in enumerate(self._bookmarks):
            if bookmark.id == bookmark_id:
                del self._bookmarks[i]
                logger.info("Removed bookmark: %s", bookmark_id)
                return True
        return False
    
    async def list_bookmarks(self, folder: Optional[str] = None) -> List[Bookmark]:
        """List bookmarks.
        
        Args:
            folder: Filter by folder
            
        Returns:
            List of Bookmark
        """
        if folder:
            return [b for b in self._bookmarks if b.folder == folder]
        return self._bookmarks.copy()
    
    def _get_page(self, tab_id: Optional[str] = None) -> Optional[Any]:
        """Get a page by ID."""
        tid = tab_id or self._active_tab_id
        return self._tabs.get(tid)
    
    @property
    def is_running(self) -> bool:
        return self._running


_browser_automation: Optional[BrowserAutomation] = None


def get_browser_automation() -> BrowserAutomation:
    global _browser_automation
    if _browser_automation is None:
        _browser_automation = BrowserAutomation()
    return _browser_automation
