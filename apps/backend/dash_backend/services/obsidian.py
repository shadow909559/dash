"""Obsidian vault integration service.

Provides read/write access to an Obsidian vault stored on the local filesystem.
All operations are path-contained to the configured vault directory.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ObsidianService:
    """Local-filesystem Obsidian vault client.

    Operations are restricted to the configured vault path.  No network/API
    calls are made — the vault is accessed directly as Markdown files.
    """

    def __init__(self, vault_path: str | None = None) -> None:
        settings = get_settings()
        self._vault = Path(vault_path or settings.obsidian_vault_path or "")
        if not self._vault.is_absolute():
            self._vault = Path.cwd() / self._vault
        # Ensure vault root exists
        self._vault.mkdir(parents=True, exist_ok=True)

    @property
    def vault_path(self) -> Path:
        return self._vault

    # ── Helpers ─────────────────────────────────────────────

    def _resolve(self, relative: str) -> Path:
        """Resolve a relative path inside the vault, blocking traversal."""
        target = (self._vault / relative).resolve()
        if not str(target).startswith(str(self._vault.resolve())):
            raise PermissionError(f"Path escapes vault: {relative}")
        return target

    def _md_path(self, path: str) -> Path:
        """Ensure path ends with .md."""
        if not path.endswith(".md"):
            path += ".md"
        return self._resolve(path)

    def _list_all_notes(self) -> list[dict[str, Any]]:
        """Recursively list all .md files in the vault."""
        notes = []
        for md_file in self._vault.rglob("*.md"):
            rel = md_file.relative_to(self._vault)
            notes.append({
                "path": str(rel),
                "name": md_file.stem,
                "folder": str(rel.parent),
                "size": md_file.stat().st_size,
                "modified": md_file.stat().st_mtime,
            })
        return notes

    def _search_notes(self, query: str) -> list[dict[str, Any]]:
        """Simple text search across all vault notes."""
        query_lower = query.lower()
        results = []
        for note in self._list_all_notes():
            try:
                content = self._resolve(note["path"]).read_text(encoding="utf-8")
                if query_lower in content.lower() or query_lower in note["name"].lower():
                    results.append(note)
            except Exception:
                pass
        return results

    # ── Public API ──────────────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """Check vault accessibility."""
        exists = self._vault.exists()
        readable = os.access(self._vault, os.R_OK) if exists else False
        notes = len(self._list_all_notes()) if exists else 0
        return {
            "healthy": exists and readable,
            "mode": "local",
            "vault_path": str(self._vault),
            "note_count": notes,
        }

    async def list_notes(self, folder: str | None = None) -> list[dict[str, Any]]:
        """List all notes in the vault, optionally filtered by folder."""
        if folder:
            folder_path = self._resolve(folder)
            if not folder_path.is_dir():
                return []
            return [
                n for n in self._list_all_notes()
                if n["folder"] == folder or n["folder"].startswith(folder + "/")
            ]
        return self._list_all_notes()

    async def search_notes(self, query: str) -> list[dict[str, Any]]:
        """Search vault notes by text content."""
        return self._search_notes(query)

    async def read_note(self, path: str) -> dict[str, Any]:
        """Read a note's content."""
        target = self._md_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Note not found: {path}")
        content = target.read_text(encoding="utf-8")
        # Extract frontmatter if present
        frontmatter = {}
        body = content
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if fm_match:
            for line in fm_match.group(1).split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    frontmatter[key.strip()] = value.strip()
            body = content[fm_match.end():]
        return {
            "path": str(target.relative_to(self._vault)),
            "content": body,
            "raw_content": content,
            "frontmatter": frontmatter,
            "size": target.stat().st_size,
        }

    async def create_note(self, path: str, content: str, frontmatter: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new note."""
        target = self._md_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        full_content = content
        if frontmatter:
            fm_lines = ["---"]
            for k, v in frontmatter.items():
                fm_lines.append(f"{k}: {v}")
            fm_lines.append("---")
            full_content = "\n".join(fm_lines) + "\n\n" + content
        target.write_text(full_content, encoding="utf-8")
        return {"path": str(target.relative_to(self._vault)), "created": True}

    async def update_note(self, path: str, content: str) -> dict[str, Any]:
        """Update an existing note's content."""
        target = self._md_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Note not found: {path}")
        target.write_text(content, encoding="utf-8")
        return {"path": str(target.relative_to(self._vault)), "updated": True}

    async def append_note(self, path: str, content: str) -> dict[str, Any]:
        """Append content to an existing note."""
        target = self._md_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Note not found: {path}")
        with open(target, "a", encoding="utf-8") as f:
            f.write(content)
        return {"path": str(target.relative_to(self._vault)), "appended": True}

    async def delete_note(self, path: str) -> dict[str, Any]:
        """Delete a note."""
        target = self._md_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Note not found: {path}")
        target.unlink()
        return {"path": str(target.relative_to(self._vault)), "deleted": True}

    async def get_note_links(self, path: str) -> list[str]:
        """Extract wiki-links from a note."""
        target = self._md_path(path)
        if not target.exists():
            return []
        content = target.read_text(encoding="utf-8")
        links = re.findall(r"\[\[([^\]]+)\]\]", content)
        return links

    async def create_project_note(self, project_name: str, content: str) -> dict[str, Any]:
        """Create a note in the Projects folder."""
        safe_name = re.sub(r'[<>:"/\\|?*]', "-", project_name)
        return await self.create_note(
            f"01 - Projects/{safe_name}.md",
            content,
            frontmatter={"type": "project", "status": "active"},
        )

    async def create_daily_note(self, content: str) -> dict[str, Any]:
        """Create a daily note using today's date."""
        from datetime import date
        today = date.today().isoformat()
        return await self.create_note(
            f"00 - DASH/Daily/{today}.md",
            content,
            frontmatter={"type": "daily", "date": today},
        )


# Singleton
_service: ObsidianService | None = None


def get_obsidian_service() -> ObsidianService:
    global _service
    if _service is None:
        _service = ObsidianService()
    return _service
