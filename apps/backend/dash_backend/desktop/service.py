from __future__ import annotations

from typing import Dict, Any, Optional

from dash_backend.logging_config import get_logger
from dash_backend.tools import tool_manager as _tool_manager_module

logger = get_logger(__name__)


class DesktopSkill:
    name = "desktop"

    def __init__(self, tool_manager: Optional[Any] = None):
        # Use the global singleton ToolManager if none provided.
        self.tool_manager = tool_manager or _tool_manager_module.get_tool_manager()

    async def handle(self, intent: str, args: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Handle desktop-related intents by translating them into tool calls.

        Supports the full range of desktop automation intents:
        open, close, restart, process listing, window (focus/restore/move/
        resize/snap), screenshot, clipboard, system info, power, and
        application discovery.
        """
        logger.info("DesktopSkill handling %s %s", intent, args)
        intent_l = intent.lower()

        # ── Application launch/close ─────────────────────────
        if intent_l.startswith("open"):
            target = args.get("target") or args.get("path") or args.get("name")
            if not target:
                return {"error": "no_target"}
            resolved = await self._resolve_app(target)
            path = resolved.get("path") if resolved else target
            return await self.tool_manager.execute("open_application", {"path": path, "name": target})

        if intent_l.startswith("close") or intent_l.startswith("kill"):
            name = args.get("name") or args.get("target")
            if not name:
                return {"error": "no_process"}
            return await self.tool_manager.execute("close_application", {"name": name})

        if intent_l.startswith("restart"):
            name = args.get("name") or args.get("target")
            path = args.get("path")
            if not name and not path:
                return {"error": "no_process"}
            return await self.tool_manager.execute("restart_application", {"name": name, "path": path})

        # ── Process management ───────────────────────────────
        if "process" in intent_l or ("list" in intent_l and "app" not in intent_l):
            return await self.tool_manager.execute("list_running_processes", {"limit": args.get("limit", 50)})

        # ── Window management ────────────────────────────────
        if "bring" in intent_l or "focus" in intent_l or "front" in intent_l:
            title = args.get("title") or args.get("target") or args.get("name")
            if not title:
                return {"error": "no_title"}
            return await self.tool_manager.execute("bring_window_to_front", {"title": title})

        if "restore" in intent_l:
            title = args.get("title") or args.get("target") or args.get("name")
            if not title:
                return {"error": "no_title"}
            return await self.tool_manager.execute("restore_window", {"title": title})

        if "move" in intent_l and "window" in intent_l:
            title = args.get("title") or args.get("target") or args.get("name")
            x = args.get("x", 0)
            y = args.get("y", 0)
            if not title:
                return {"error": "no_title"}
            return await self.tool_manager.execute("move_window", {"title": title, "x": x, "y": y})

        if "resize" in intent_l:
            title = args.get("title") or args.get("target") or args.get("name")
            width = args.get("width")
            height = args.get("height")
            if not title or not width or not height:
                return {"error": "resize_requires_title_width_height"}
            return await self.tool_manager.execute("resize_window", {"title": title, "width": width, "height": height})

        if "snap" in intent_l:
            title = args.get("title") or args.get("target") or args.get("name")
            position = args.get("position", "left")
            if not title:
                return {"error": "no_title"}
            return await self.tool_manager.execute("snap_window", {"title": title, "position": position})

        if "active" in intent_l and "window" in intent_l:
            return await self.tool_manager.execute("detect_active_window", {})

        # ── Screenshot ───────────────────────────────────────
        if "screenshot" in intent_l or "capture" in intent_l or "screen" in intent_l:
            return await self.tool_manager.execute("take_screenshot", {})

        # ── Clipboard ────────────────────────────────────────
        if "clipboard" in intent_l or "copy" in intent_l or "paste" in intent_l:
            if "read" in intent_l or "get" in intent_l or "paste" in intent_l:
                return await self.tool_manager.execute("read_clipboard", {})
            if "clear" in intent_l:
                return await self.tool_manager.execute("clear_clipboard", {})
            text = args.get("text", "")
            if text:
                return await self.tool_manager.execute("copy_text", {"text": text})
            return await self.tool_manager.execute("read_clipboard", {})

        # ── Power ────────────────────────────────────────────
        if "shutdown" in intent_l:
            return await self.tool_manager.execute("shutdown", {"force": args.get("force", False)})
        if "restart" in intent_l and "app" not in intent_l and "application" not in intent_l:
            return await self.tool_manager.execute("restart_system", {"force": args.get("force", False)})
        if "lock" in intent_l:
            return await self.tool_manager.execute("lock_workstation", {})
        if "sleep" in intent_l:
            return await self.tool_manager.execute("sleep_system", {})

        # ── System info ──────────────────────────────────────
        if "system" in intent_l or "info" in intent_l:
            return await self.tool_manager.execute("system_info", {})
        if "cpu" in intent_l:
            return await self.tool_manager.execute("cpu_usage", {})
        if "ram" in intent_l or "memory" in intent_l:
            return await self.tool_manager.execute("ram_usage", {})
        if "disk" in intent_l:
            return await self.tool_manager.execute("disk_usage", {"path": args.get("path", ".")})

        # ── Application discovery ────────────────────────────
        if intent_l.startswith("find") or "search app" in intent_l or "discover" in intent_l:
            query = args.get("query") or args.get("name") or args.get("target", "")
            if query:
                return await self.tool_manager.execute("resolve_application", {"name": query})
            return await self.tool_manager.execute("discover_applications", {})

        return {"error": "unknown_desktop_intent"}

    async def _resolve_app(self, name: str) -> Optional[Dict[str, Any]]:
        """Resolve a friendly app name to a discovered path."""
        try:
            from dash_backend.services.application_discovery import get_application_discovery
            service = get_application_discovery()
            return service.resolve(name)
        except Exception as exc:
            logger.warning("App resolution failed: %s", exc)
            return None
