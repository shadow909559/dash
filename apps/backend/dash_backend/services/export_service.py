"""Export service: chat, memory, settings, and data export in multiple formats."""
from __future__ import annotations

import json
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExportFormat:
    JSON = "json"
    MARKDOWN = "markdown"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"  # placeholder — needs reportlab


class ChatExporter:
    """Export conversations in multiple formats."""

    @staticmethod
    def to_markdown(messages: list[dict], title: str = "Conversation") -> str:
        lines = [f"# {title}\n"]
        for msg in messages:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")
            lines.append(f"### {role}")
            if timestamp:
                lines.append(f"*{timestamp}*\n")
            lines.append(f"{content}\n")
            lines.append("---\n")
        return "\n".join(lines)

    @staticmethod
    def to_json(messages: list[dict]) -> str:
        return json.dumps({
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "dash-conversation-v1",
            "message_count": len(messages),
            "messages": messages,
        }, indent=2, default=str)

    @staticmethod
    def to_csv(messages: list[dict]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "role", "content", "model", "tokens"])
        for msg in messages:
            writer.writerow([
                msg.get("timestamp", ""),
                msg.get("role", ""),
                msg.get("content", ""),
                msg.get("model", ""),
                msg.get("tokens", ""),
            ])
        return output.getvalue()

    @staticmethod
    def to_html(messages: list[dict], title: str = "DASH Conversation") -> str:
        rows = []
        for msg in messages:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "").replace("<", "&lt;").replace(">", "&gt;")
            ts = msg.get("timestamp", "")
            rows.append(f'<tr><td class="role">{role}</td><td class="ts">{ts}</td><td>{content}</td></tr>')

        return f"""<!DOCTYPE html>
<html><head><title>{title}</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #0a0a0f; color: #e5e5e5; }}
h1 {{ color: #22c55e; }}
table {{ width: 100%; border-collapse: collapse; }}
td, th {{ padding: 8px 12px; border-bottom: 1px solid #222; text-align: left; }}
.role {{ font-weight: 600; color: #22c55e; white-space: nowrap; }}
.ts {{ color: #666; white-space: nowrap; font-size: 12px; }}
</style></head><body>
<h1>{title}</h1>
<p>Exported: {datetime.now(timezone.utc).isoformat()}</p>
<table><thead><tr><th>Role</th><th>Time</th><th>Content</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></body></html>"""


class MemoryExporter:
    """Export memories in multiple formats."""

    @staticmethod
    def to_markdown(memories: list[dict]) -> str:
        lines = ["# DASH Memory Export\n"]
        lines.append(f"*Exported: {datetime.now(timezone.utc).isoformat()}*\n")
        for mem in memories:
            mem_type = mem.get("type", "unknown")
            importance = mem.get("importance", 0)
            content = mem.get("content", "")
            project = mem.get("project_id", "")
            lines.append(f"## [{mem_type.upper()}] (importance: {importance})")
            if project:
                lines.append(f"**Project:** {project}")
            lines.append(f"\n{content}\n")
            lines.append("---\n")
        return "\n".join(lines)

    @staticmethod
    def to_json(memories: list[dict]) -> str:
        return json.dumps({
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "dash-memory-v1",
            "memory_count": len(memories),
            "memories": memories,
        }, indent=2, default=str)

    @staticmethod
    def to_csv(memories: list[dict]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "type", "content", "importance", "confidence", "source", "project", "created_at"])
        for mem in memories:
            writer.writerow([
                mem.get("id", ""),
                mem.get("type", ""),
                mem.get("content", ""),
                mem.get("importance", ""),
                mem.get("confidence", ""),
                mem.get("source", ""),
                mem.get("project_id", ""),
                mem.get("created_at", ""),
            ])
        return output.getvalue()


class SettingsExporter:
    """Export and import user settings."""

    @staticmethod
    def export(settings: dict) -> str:
        return json.dumps({
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "dash-settings-v1",
            "settings": settings,
        }, indent=2, default=str)

    @staticmethod
    def import_settings(json_str: str) -> dict:
        try:
            data = json.loads(json_str)
            if data.get("format") != "dash-settings-v1":
                return {"ok": False, "reason": "Invalid format"}
            return {"ok": True, "settings": data.get("settings", {})}
        except json.JSONDecodeError as e:
            return {"ok": False, "reason": f"Invalid JSON: {e}"}

    @staticmethod
    def get_default_settings() -> dict:
        return {
            "theme": "dark",
            "accent_color": "#22c55e",
            "font_size": 14,
            "font_family": "Inter",
            "code_font": "JetBrains Mono",
            "language": "en",
            "notifications": True,
            "sounds": True,
            "auto_save": True,
            "compact_mode": False,
            "show_line_numbers": True,
            "word_wrap": True,
            "tab_size": 2,
            "dnd_enabled": False,
            "dnd_schedule": {"start": "22:00", "end": "07:00"},
            "session_timeout_minutes": 480,
            "max_conversation_length": 200,
            "auto_summarize_threshold": 100,
            "backup_enabled": True,
            "backup_interval_hours": 24,
        }


class DataExporter:
    """Export all user data."""

    @staticmethod
    def export_all(memories: list[dict], conversations: list[dict], settings: dict,
                    goals: list[dict], notifications: list[dict]) -> str:
        return json.dumps({
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "dash-full-export-v1",
            "summary": {
                "memories": len(memories),
                "conversations": len(conversations),
                "goals": len(goals),
                "notifications": len(notifications),
            },
            "memories": memories,
            "conversations": conversations,
            "settings": settings,
            "goals": goals,
            "notifications": notifications,
        }, indent=2, default=str)


# Singletons
chat_exporter = ChatExporter()
memory_exporter = MemoryExporter()
settings_exporter = SettingsExporter()
data_exporter = DataExporter()
