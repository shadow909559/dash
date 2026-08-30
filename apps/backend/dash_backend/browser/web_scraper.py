"""Web Scraper - Scrape and extract data from websites."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebScraper:
    def __init__(self):
        self._page = None
    
    async def set_page(self, page) -> None:
        self._page = page
    
    async def scrape_text(self, selector: str = "body") -> str:
        if not self._page:
            return ""
        try:
            element = await self._page.query_selector(selector)
            if element:
                return await element.text_content() or ""
            return await self._page.text_content(selector) or ""
        except Exception as exc:
            logger.warning("Scrape text failed: %s", exc)
            return ""
    
    async def scrape_links(self) -> List[Dict[str, str]]:
        if not self._page:
            return []
        try:
            links = await self._page.eval_on_selector_all(
                "a[href]",
                "elements => elements.map(e => ({text: e.innerText, href: e.href, title: e.title}))"
            )
            return [l for l in links if l.get("href") and not l["href"].startswith("javascript:")]
        except Exception as exc:
            logger.warning("Scrape links failed: %s", exc)
            return []
    
    async def scrape_images(self) -> List[Dict[str, str]]:
        if not self._page:
            return []
        try:
            return await self._page.eval_on_selector_all(
                "img[src]",
                "elements => elements.map(e => ({src: e.src, alt: e.alt, width: e.naturalWidth, height: e.naturalHeight}))"
            )
        except Exception as exc:
            logger.warning("Scrape images failed: %s", exc)
            return []
    
    async def scrape_table(self, selector: str) -> List[Dict[str, str]]:
        if not self._page:
            return []
        try:
            html = await self._page.inner_html(selector)
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')
            if not table:
                return []
            
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            rows = []
            for tr in table.find_all('tr')[1:]:
                cells = tr.find_all('td')
                if headers and len(cells) == len(headers):
                    row = {h: c.get_text(strip=True) for h, c in zip(headers, cells)}
                    rows.append(row)
            return rows
        except Exception as exc:
            logger.warning("Scrape table failed: %s", exc)
            return []
    
    async def extract_structured_data(self, schema: Dict[str, str]) -> Dict[str, Any]:
        if not self._page:
            return {}
        try:
            result = {}
            for key, selector in schema.items():
                try:
                    elements = await self._page.query_selector_all(selector)
                    if elements:
                        texts = [await el.text_content() for el in elements if el]
                        result[key] = [t.strip() for t in texts if t and t.strip()]
                    else:
                        result[key] = []
                except Exception:
                    result[key] = []
            return result
        except Exception as exc:
            logger.warning("Extract structured data failed: %s", exc)
            return {}
    
    async def export_json(self, page, selectors: Dict[str, str]) -> str:
        data = await self.extract_structured_data(selectors)
        return json.dumps(data, indent=2)


_web_scraper: Optional[WebScraper] = None


def get_web_scraper() -> WebScraper:
    global _web_scraper
    if _web_scraper is None:
        _web_scraper = WebScraper()
    return _web_scraper
