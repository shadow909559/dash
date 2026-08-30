"""Research Mode - Multi-tab research, comparison, and analysis."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.llm.service import collect_streamed_response, build_chat_messages

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    query: str = ""
    summary: str = ""
    sources: List[Dict[str, str]] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)
    confidence: float = 0.0


class ResearchMode:
    def __init__(self):
        self._page = None
        self._active_research: Optional[ResearchResult] = None
    
    async def set_page(self, page) -> None:
        self._page = page
    
    async def research(self, query: str, num_sources: int = 5) -> ResearchResult:
        result = ResearchResult(query=query)
        try:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            await self._page.goto(search_url)
            await asyncio.sleep(2)
            
            links = await self._page.eval_on_selector_all(
                "a[href^='http']",
                "elements => elements.map(e => ({text: e.innerText, href: e.href})).filter(e => e.text && e.href)"
            )
            
            sources = []
            for link in links[:num_sources]:
                sources.append({"title": link["text"][:100], "url": link["href"]})
            result.sources = sources
            
            for source in sources[:3]:
                try:
                    await self._page.goto(source["url"])
                    await asyncio.sleep(1)
                    content = await self._page.text_content("body") or ""
                    clean = ' '.join(content.split())[:3000]
                    source["content"] = clean
                except Exception:
                    continue
            
            contents = "\n\n".join([
                f"Source: {s['title']}\n{s.get('content', '')}"
                for s in sources if s.get('content')
            ])
            
            if contents:
                messages = build_chat_messages(
                    system_prompt="You are a research analyst. Summarize findings from multiple sources.",
                    user_message=f"Research Query: {query}\n\nSource Materials:\n{contents[:8000]}",
                )
                summary = await collect_streamed_response(messages)
                result.summary = summary
            
        except Exception as exc:
            logger.warning("Research failed: %s", exc)
            result.summary = f"Research interrupted: {exc}"
        
        self._active_research = result
        return result
    
    async def compare_products(self, product: str) -> Dict[str, Any]:
        result = await self.research(f"{product} review comparison")
        return {
            "product": product,
            "summary": result.summary,
            "sources": result.sources,
        }


_research_mode: Optional[ResearchMode] = None


def get_research_mode() -> ResearchMode:
    global _research_mode
    if _research_mode is None:
        _research_mode = ResearchMode()
    return _research_mode
