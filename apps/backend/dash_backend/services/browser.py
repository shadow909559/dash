"""BrowserService - open URLs, open tabs in default browser."""

from __future__ import annotations

import webbrowser
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)


class BrowserService(Singleton):
    """Open URLs and manage browser tabs."""

    async def open_url(self, url: str) -> dict[str, Any]:
        """Open a URL in the default browser."""
        if not url:
            raise ValueError("url is required")
        try:
            webbrowser.open(url)
            return {"summary": f"Opened URL: {url}", "url": url}
        except Exception as exc:
            logger.exception("Failed to open URL %s", url)
            raise RuntimeError(f"Failed to open URL: {exc}") from exc

    async def open_tab(self, url: str) -> dict[str, Any]:
        """Open a URL in a new browser tab."""
        if not url:
            raise ValueError("url is required")
        try:
            webbrowser.open_new_tab(url)
            return {"summary": f"Opened new tab: {url}", "url": url}
        except Exception as exc:
            logger.exception("Failed to open tab %s", url)
            raise RuntimeError(f"Failed to open tab: {exc}") from exc

    async def search(self, query: str) -> dict[str, Any]:
        """Search the web with the given query."""
        if not query:
            raise ValueError("query is required")
        try:
            import subprocess

            encoded = subprocess.quote(query)
            url = f"https://www.google.com/search?q={encoded}"
            webbrowser.open(url)
            return {"summary": f"Searched for: {query}", "url": url}
        except Exception as exc:
            logger.exception("Failed to search")
            raise RuntimeError(f"Failed to search: {exc}") from exc
