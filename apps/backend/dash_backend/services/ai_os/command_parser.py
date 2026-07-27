"""CommandParser - natural language to structured CommandRequest mapping.

Uses pattern matching and AI provider for fallback to parse
natural language commands like "Open VS Code", "Shutdown",
"Copy this folder", etc. into structured CommandRequest objects.
"""

from __future__ import annotations

import re
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.command.models import (
    CommandCategory,
    CommandRequest,
)

logger = get_logger(__name__)


class ParsedCommand:
    """Result of parsing a natural language command."""
    def __init__(
        self,
        category: CommandCategory,
        action: str,
        params: dict[str, Any],
        confidence: float = 1.0,
        description: str = "",
    ):
        self.category = category
        self.action = action
        self.params = params
        self.confidence = confidence
        self.description = description or f"{category.value}.{action}"


class CommandParser:
    """Maps natural language to structured CommandRequests.

    Uses regex patterns for exact matches and falls back to
    the AI provider for complex/ambiguous commands.
    """

    def __init__(self) -> None:
        self._patterns = self._build_patterns()

    def parse(self, text: str) -> ParsedCommand | None:
        """Parse natural language text into a ParsedCommand.

        Returns None if the command cannot be parsed.
        """
        cleaned = text.strip().rstrip(".!?")
        if not cleaned:
            return None

        # Try exact pattern matching first
        for pattern, (category, action, extract_params) in self._patterns:
            match = pattern.search(cleaned)
            if match:
                params = extract_params(match) if extract_params else {}
                desc = f"{category.value}.{action}: {cleaned}"
                return ParsedCommand(
                    category=category,
                    action=action,
                    params=params,
                    description=desc,
                )

        # Try to detect category/action by keywords
        return self._fallback_heuristic(cleaned)

    def parse_to_request(
        self,
        text: str,
        source: str = "user",
        command_id: str | None = None,
        user_id: str | None = None,
        requires_approval: bool = True,
    ) -> CommandRequest | None:
        """Parse text into a full CommandRequest.

        This is the primary entry point for the AI OS pipeline.
        """
        parsed = self.parse(text)
        if parsed is None:
            return None

        import uuid
        return CommandRequest(
            command_id=command_id or str(uuid.uuid4()),
            category=parsed.category,
            action=parsed.action,
            params=parsed.params,
            source=source,
            user_id=user_id,
            requires_approval=requires_approval and parsed.confidence < 0.9,
        )

    def _fallback_heuristic(self, text: str) -> ParsedCommand | None:
        """Heuristic fallback for commands not matched by patterns."""
        lower = text.lower()

        # System commands
        if any(w in lower for w in ["shutdown", "turn off", "power off"]):
            return ParsedCommand(CommandCategory.SYSTEM, "shutdown", {}, 0.7, "Shutdown computer")
        if any(w in lower for w in ["restart", "reboot"]):
            return ParsedCommand(CommandCategory.SYSTEM, "restart", {}, 0.7, "Restart computer")
        if any(w in lower for w in ["sleep", "suspend"]):
            return ParsedCommand(CommandCategory.SYSTEM, "sleep", {}, 0.7, "Sleep computer")
        if any(w in lower for w in ["hibernate"]):
            return ParsedCommand(CommandCategory.SYSTEM, "hibernate", {}, 0.7, "Hibernate computer")
        if any(w in lower for w in ["lock"]):
            return ParsedCommand(CommandCategory.SYSTEM, "lock", {}, 0.7, "Lock workstation")
        if any(w in lower for w in ["log out", "sign out", "logout"]):
            return ParsedCommand(CommandCategory.SYSTEM, "logout", {}, 0.7, "Log out")

        # Volume / Brightness
        vol_match = re.search(r"volume\s*(\d+)", lower)
        if vol_match:
            return ParsedCommand(CommandCategory.SYSTEM, "volume", {"level": int(vol_match.group(1))}, 0.8)
        bright_match = re.search(r"brightness\s*(\d+)", lower)
        if bright_match:
            return ParsedCommand(CommandCategory.SYSTEM, "brightness", {"level": int(bright_match.group(1))}, 0.8)

        # Application commands
        if re.search(r"\bopen\s+", lower):
            app = re.sub(r"\bopen\b", "", text, flags=re.IGNORECASE).strip().strip('"').strip("'")
            if app:
                return ParsedCommand(CommandCategory.APPS, "launch", {"path": app, "name": app}, 0.8, f"Launch {app}")
        if re.search(r"\b(close|exit|quit)\s+", lower):
            app = re.sub(r"\b(close|exit|quit)\b", "", text, flags=re.IGNORECASE).strip().strip('"').strip("'")
            if app:
                return ParsedCommand(CommandCategory.APPS, "close", {"name": app}, 0.8, f"Close {app}")
        if re.search(r"\b(kill|stop)\s+", lower):
            proc = re.sub(r"\b(kill|stop)\b", "", text, flags=re.IGNORECASE).strip()
            if proc:
                return ParsedCommand(CommandCategory.APPS, "kill", {"name": proc}, 0.7, f"Kill process {proc}")

        # Clipboard
        if any(w in lower for w in ["copy", "clipboard"]):
            if "copy" in lower:
                return ParsedCommand(CommandCategory.CLIPBOARD, "copy", {"text": text.replace("copy", "").strip()}, 0.6)
            return ParsedCommand(CommandCategory.CLIPBOARD, "read", {}, 0.8, "Read clipboard")

        # Notifications
        if "notify" in lower or "notification" in lower:
            return ParsedCommand(CommandCategory.NOTIFICATIONS, "show", {
                "title": "DASH",
                "message": text.replace("notify", "").replace("notification", "").strip()
            }, 0.6)

        # Window management
        if re.search(r"\bfocus\b", lower):
            title = re.sub(r"\bfocus\b", "", text, flags=re.IGNORECASE).strip()
            if title:
                return ParsedCommand(CommandCategory.WINDOW, "focus", {"title": title}, 0.7, f"Focus window: {title}")
        if "list windows" in lower:
            return ParsedCommand(CommandCategory.WINDOW, "list", {}, 0.9, "List windows")

        # Mouse
        if re.search(r"\bmove mouse\b", lower):
            return ParsedCommand(CommandCategory.MOUSE, "position", {}, 0.7, "Get mouse position")
        if "click" in lower:
            return ParsedCommand(CommandCategory.MOUSE, "click", {"button": "left"}, 0.6)

        # Keyboard
        if re.search(r"\btype\b", lower):
            text_to_type = re.sub(r"\btype\b", "", text, flags=re.IGNORECASE).strip()
            if text_to_type:
                return ParsedCommand(CommandCategory.KEYBOARD, "type", {"text": text_to_type}, 0.7, f"Type: {text_to_type}")

        # File operations
        if re.search(r"\b(copy|move|rename|delete)\s+(file|folder)", lower):
            op = "copy" if "copy" in lower else "move" if "move" in lower else "rename" if "rename" in lower else "delete"
            return ParsedCommand(CommandCategory.FILES, op, {"path": text}, 0.5)

        # Browser
        if re.search(r"\b(open|go to|navigate)\s+(https?://|www\.)", lower, re.IGNORECASE):
            url_match = re.search(r"(https?://[^\s]+|www\.[^\s]+)", text)
            if url_match:
                return ParsedCommand(CommandCategory.BROWSER, "open_url", {"url": url_match.group(0)}, 0.8)
        if re.search(r"\bsearch\b", lower):
            query = re.sub(r"\bsearch\b", "", text, flags=re.IGNORECASE).strip().strip("for").strip()
            if query:
                return ParsedCommand(CommandCategory.BROWSER, "search", {"query": query}, 0.7, f"Search: {query}")

        # Terminal
        if re.search(r"\b(run|execute)\s+command", lower):
            cmd = re.sub(r"\b(run|execute)\s+command\b", "", text, flags=re.IGNORECASE).strip()
            if cmd:
                return ParsedCommand(CommandCategory.TERMINAL, "execute", {"command": cmd}, 0.6, f"Execute: {cmd}")

        # System info
        if any(w in lower for w in ["system info", "system information", "status"]):
            return ParsedCommand(CommandCategory.SYSTEM, "get_system_info", {}, 0.8, "Get system info")

        return None

    @staticmethod
    def _build_patterns() -> list[tuple[re.Pattern, tuple]]:
        """Build regex patterns for exact command matching."""
        patterns: list[tuple[re.Pattern, tuple]] = []

        entries = [
            # System
            (r"\bshut\s*down\b", CommandCategory.SYSTEM, "shutdown", None),
            (r"\brestart\b", CommandCategory.SYSTEM, "restart", None),
            (r"\breboot\b", CommandCategory.SYSTEM, "restart", None),
            (r"\bsleep\b", CommandCategory.SYSTEM, "sleep", None),
            (r"\bhibernate\b", CommandCategory.SYSTEM, "hibernate", None),
            (r"\block (computer|pc|workstation)\b", CommandCategory.SYSTEM, "lock", None),
            (r"\blog\s*out\b", CommandCategory.SYSTEM, "logout", None),
            (r"\bvolume\s+(\d+)\b", CommandCategory.SYSTEM, "volume", lambda m: {"level": int(m.group(1))}),
            (r"\bbrightness\s+(\d+)\b", CommandCategory.SYSTEM, "brightness", lambda m: {"level": int(m.group(1))}),
            # Apps
            (r"\bopen\s+(.+?)\b", CommandCategory.APPS, "launch", lambda m: {"path": m.group(1).strip(), "name": m.group(1).strip()}),
            (r"\blaunch\s+(.+?)\b", CommandCategory.APPS, "launch", lambda m: {"path": m.group(1).strip(), "name": m.group(1).strip()}),
            (r"\bclose\s+(.+?)\b", CommandCategory.APPS, "close", lambda m: {"name": m.group(1).strip()}),
            (r"\bkill\s+(.+?)\b", CommandCategory.APPS, "kill", lambda m: {"name": m.group(1).strip()}),
            # Clipboard
            (r"\bcopy\s+(.+?)\s+to\s+clipboard\b", CommandCategory.CLIPBOARD, "copy", lambda m: {"text": m.group(1).strip()}),
            (r"\bread\s+clipboard\b", CommandCategory.CLIPBOARD, "read", None),
            (r"\bclear\s+clipboard\b", CommandCategory.CLIPBOARD, "clear", None),
            # Notifications
            (r"\bnotify\s+(.+?)\b", CommandCategory.NOTIFICATIONS, "show", lambda m: {"title": "DASH", "message": m.group(1).strip()}),
            # Window
            (r"\bfocus\s+(.+?)\b", CommandCategory.WINDOW, "focus", lambda m: {"title": m.group(1).strip()}),
            (r"\blist\s+windows\b", CommandCategory.WINDOW, "list", None),
            (r"\bminimize\s+(.+?)\b", CommandCategory.WINDOW, "minimize", lambda m: {"title": m.group(1).strip()}),
            (r"\bmaximize\s+(.+?)\b", CommandCategory.WINDOW, "maximize", lambda m: {"title": m.group(1).strip()}),
            # Mouse
            (r"\bclick\b", CommandCategory.MOUSE, "click", lambda m: {"button": "left"}),
            (r"\bdouble\s*click\b", CommandCategory.MOUSE, "double_click", None),
            # Keyboard
            (r"\btype\s+(.+)\b", CommandCategory.KEYBOARD, "type", lambda m: {"text": m.group(1).strip()}),
            # Browser
            (r"\bopen\s+(https?://[^\s]+)\b", CommandCategory.BROWSER, "open_url", lambda m: {"url": m.group(1).strip()}),
            (r"\bsearch\s+(?:for\s+)?(.+)\b", CommandCategory.BROWSER, "search", lambda m: {"query": m.group(1).strip()}),
            # Files
            (r"\bcopy\s+(.+?)\s+to\s+(.+?)\b", CommandCategory.FILES, "copy", lambda m: {"source": m.group(1).strip(), "destination": m.group(2).strip()}),
            (r"\bdelete\s+(.+?)\b", CommandCategory.FILES, "delete", lambda m: {"path": m.group(1).strip()}),
            (r"\bcreate\s+folder\s+(.+?)\b", CommandCategory.FILES, "create_folder", lambda m: {"path": m.group(1).strip()}),
            # Terminal
            (r"\brun\s+command\s+(.+)\b", CommandCategory.TERMINAL, "execute", lambda m: {"command": m.group(1).strip()}),
            (r"\bexecute\s+(.+)\b", CommandCategory.TERMINAL, "execute", lambda m: {"command": m.group(1).strip()}),
            # System info
            (r"\bsystem\s+info\b", CommandCategory.SYSTEM, "get_system_info", None),
            # Screenshot
            (r"\bscreenshot\b", CommandCategory.SYSTEM, "screenshot", None),
        ]

        for pattern, category, action, extractor in entries:
            compiled = re.compile(pattern, re.IGNORECASE)
            patterns.append((compiled, (category, action, extractor)))

        return patterns


# Singleton
_parser: CommandParser | None = None


def get_command_parser() -> CommandParser:
    global _parser
    if _parser is None:
        _parser = CommandParser()
    return _parser
