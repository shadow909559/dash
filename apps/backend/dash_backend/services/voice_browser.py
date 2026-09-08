"""Voice system and browser management."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VoiceService:
    """Voice wake word, continuous listening, voice commands, voice memo."""

    def __init__(self) -> None:
        self._wake_words = ["hey dash", "dash", "ok dash"]
        self._commands: dict[str, dict] = {
            "open_settings": {"patterns": ["open settings", "show settings"], "action": "navigate", "target": "/settings"},
            "new_chat": {"patterns": ["new chat", "start conversation"], "action": "chat", "target": "new"},
            "search_memory": {"patterns": ["search memory", "find memory", "remember when"], "action": "memory", "target": "search"},
            "take_note": {"patterns": ["take note", "remember this", "save note"], "action": "memory", "target": "create"},
            "read_email": {"patterns": ["read email", "check email", "any emails"], "action": "email", "target": "inbox"},
            "show_calendar": {"patterns": ["show calendar", "what's today", "today's schedule"], "action": "calendar", "target": "today"},
            "set_reminder": {"patterns": ["remind me", "set reminder", "don't forget"], "action": "reminder", "target": "create"},
            "screenshot": {"patterns": ["take screenshot", "capture screen"], "action": "system", "target": "screenshot"},
            "volume_up": {"patterns": ["volume up", "louder"], "action": "system", "target": "volume_up"},
            "volume_down": {"patterns": ["volume down", "quieter"], "action": "system", "target": "volume_down"},
            "minimize": {"patterns": ["minimize", "hide window"], "action": "window", "target": "minimize"},
            "maximize": {"patterns": ["maximize", "full screen"], "action": "window", "target": "maximize"},
            "summarize": {"patterns": ["summarize this", "tldr", "too long"], "action": "ai", "target": "summarize"},
            "code_review": {"patterns": ["review code", "check code", "code review"], "action": "ai", "target": "code_review"},
        }
        self._memos: list[dict] = []
        self._listening = False
        self._language = "en"

    def detect_wake_word(self, text: str) -> bool:
        text_lower = text.lower().strip()
        return any(ww in text_lower for ww in self._wake_words)

    def parse_command(self, text: str) -> dict:
        text_lower = text.lower().strip()
        # Remove wake word prefix
        for ww in self._wake_words:
            text_lower = text_lower.replace(ww, "").strip()

        for cmd_id, cmd in self._commands.items():
            for pattern in cmd["patterns"]:
                if pattern in text_lower:
                    return {"matched": True, "command": cmd_id, "action": cmd["action"],
                            "target": cmd["target"], "original_text": text}
        return {"matched": False, "original_text": text}

    def add_command(self, command_id: str, patterns: list[str], action: str, target: str) -> dict:
        self._commands[command_id] = {"patterns": patterns, "action": action, "target": target}
        return {"ok": True}

    def get_commands(self) -> dict:
        return dict(self._commands)

    def record_memo(self, title: str, transcript: str, duration_seconds: float = 0) -> dict:
        memo = {
            "id": f"memo_{len(self._memos)}",
            "title": title,
            "transcript": transcript,
            "duration_seconds": duration_seconds,
            "language": self._language,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._memos.append(memo)
        return {"ok": True, "memo": memo}

    def get_memos(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._memos[-limit:]))

    def search_memos(self, query: str) -> list[dict]:
        q = query.lower()
        return [m for m in self._memos if q in m.get("title", "").lower() or q in m.get("transcript", "").lower()]

    def set_language(self, language: str) -> dict:
        self._language = language
        return {"ok": True, "language": language}

    def get_config(self) -> dict:
        return {"wake_words": self._wake_words, "language": self._language,
                "command_count": len(self._commands), "listening": self._listening}

    def set_listening(self, enabled: bool) -> dict:
        self._listening = enabled
        return {"ok": True, "listening": enabled}

    def get_stats(self) -> dict:
        return {"total_memos": len(self._memos), "commands_registered": len(self._commands),
                "wake_words": len(self._wake_words), "language": self._language}


class BrowserService:
    """Browser tab management, page summarization, web scraping, bookmark AI."""

    def __init__(self) -> None:
        self._tabs: list[dict] = []
        self._bookmarks: list[dict] = []
        self._history: list[dict] = []
        self._summaries: dict[str, dict] = {}

    def open_tab(self, url: str, title: str = "", active: bool = True) -> dict:
        tab = {
            "id": f"tab_{len(self._tabs)}",
            "url": url,
            "title": title or url.split("//")[-1][:50],
            "active": active,
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        }
        if active:
            for t in self._tabs:
                t["active"] = False
        self._tabs.append(tab)
        self._history.append({"url": url, "title": tab["title"], "timestamp": tab["loaded_at"]})
        return {"ok": True, "tab": tab}

    def close_tab(self, tab_id: str) -> dict:
        self._tabs = [t for t in self._tabs if t["id"] != tab_id]
        return {"ok": True}

    def get_tabs(self) -> list[dict]:
        return self._tabs

    def switch_tab(self, tab_id: str) -> dict:
        for t in self._tabs:
            t["active"] = t["id"] == tab_id
        return {"ok": True}

    def navigate(self, tab_id: str, url: str) -> dict:
        for t in self._tabs:
            if t["id"] == tab_id:
                t["url"] = url
                t["loaded_at"] = datetime.now(timezone.utc).isoformat()
                self._history.append({"url": url, "title": t["title"], "timestamp": t["loaded_at"]})
                return {"ok": True, "tab": t}
        return {"ok": False, "reason": "Tab not found"}

    def summarize_page(self, tab_id: str, content: str) -> dict:
        tab = next((t for t in self._tabs if t["id"] == tab_id), None)
        if not tab:
            return {"ok": False, "reason": "Tab not found"}
        words = content.split()
        word_count = len(words)
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        summary = " ".join(sentences[:3]) if sentences else content[:500]
        result = {"tab_id": tab_id, "url": tab["url"], "summary": summary,
                  "word_count": word_count, "sentence_count": len(sentences)}
        self._summaries[tab_id] = result
        return result

    def add_bookmark(self, url: str, title: str, folder: str = "default", tags: list[str] | None = None) -> dict:
        bookmark = {
            "id": f"bm_{len(self._bookmarks)}", "url": url, "title": title,
            "folder": folder, "tags": tags or [], "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._bookmarks.append(bookmark)
        return {"ok": True, "bookmark": bookmark}

    def get_bookmarks(self, folder: Optional[str] = None) -> list[dict]:
        result = self._bookmarks
        if folder:
            result = [b for b in result if b.get("folder") == folder]
        return result

    def search_bookmarks(self, query: str) -> list[dict]:
        q = query.lower()
        return [b for b in self._bookmarks if q in b.get("title", "").lower() or q in b.get("url", "").lower()]

    def delete_bookmark(self, bookmark_id: str) -> dict:
        self._bookmarks = [b for b in self._bookmarks if b["id"] != bookmark_id]
        return {"ok": True}

    def get_history(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._history[-limit:]))

    def scrape_page(self, url: str) -> dict:
        return {"ok": True, "url": url, "content": f"[Scraped content from {url}]",
                "title": url.split("//")[-1][:50], "timestamp": datetime.now(timezone.utc).isoformat()}

    def get_stats(self) -> dict:
        return {"open_tabs": len(self._tabs), "bookmarks": len(self._bookmarks),
                "history_entries": len(self._history), "summaries": len(self._summaries)}


voice_service = VoiceService()
browser_service = BrowserService()
