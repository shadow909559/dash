from __future__ import annotations

from typing import Dict, Any, Optional

from dash_backend.logging_config import get_logger
from dash_backend.tools.tool_manager import get_tool_manager
from dash_backend.phone.adb_service import get_adb_service

logger = get_logger(__name__)


class PhoneSkill:
    name = "phone"

    def __init__(self, tool_manager: Optional[Any] = None):
        self.tool_manager = tool_manager or get_tool_manager()
        self.adb = get_adb_service()

    async def handle(self, intent: str, args: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Handle phone-related intents by routing to the ADB service.

        Supports: devices, battery, clipboard, files, apps, sms, call status,
        location, notifications.
        """
        logger.info("PhoneSkill handling %s %s", intent, args)
        serial = args.get("serial")

        if intent.startswith("devices") or intent == "list_devices":
            devices = await self.adb.discover_devices()
            return {"status": "ok", "devices": devices, "count": len(devices)}

        if intent.startswith("battery"):
            result = await self.adb.get_battery(serial)
            return {"status": "ok" if result.get("ok") else "error", "battery": result.get("battery", {})}

        if intent.startswith("clipboard") and "read" in intent:
            result = await self.adb.read_clipboard(serial)
            return {"status": "ok" if result.get("ok") else "error", "text": result.get("text", "")}

        if intent.startswith("clipboard") or intent.startswith("write_clipboard"):
            text = args.get("text", "")
            result = await self.adb.write_clipboard(text, serial)
            return {"status": "ok" if result.get("ok") else "error", "message": result.get("summary", "")}

        if intent.startswith("list_files") or intent.startswith("files"):
            path = args.get("path", "/sdcard")
            result = await self.adb.list_files(path, serial)
            return {"status": "ok" if result.get("ok") else "error", "files": result.get("files", [])}

        if intent.startswith("open_app") or intent.startswith("open"):
            package = args.get("package") or args.get("app")
            if not package:
                return {"error": "no_package"}
            result = await self.adb.open_app(package, serial)
            return {"status": "ok" if result.get("ok") else "error", "message": result.get("summary", "")}

        if intent.startswith("sms") or intent.startswith("message"):
            number = args.get("number") or args.get("contact")
            message = args.get("message") or args.get("text", "")
            if not number:
                return {"error": "no_number"}
            result = await self.adb.send_sms(number, message, serial)
            return {"status": "ok" if result.get("ok") else "error", "message": result.get("summary", "")}

        if intent.startswith("call_status") or intent.startswith("call"):
            result = await self.adb.get_call_status(serial)
            return {"status": "ok" if result.get("ok") else "error", "status": result.get("status", "unknown")}

        if intent.startswith("location"):
            result = await self.adb.get_location(serial)
            return {"status": "ok" if result.get("ok") else "error", "location": result.get("location")}

        if intent.startswith("notifications"):
            result = await self.adb.get_notifications(serial)
            return {"status": "ok" if result.get("ok") else "error", "notifications": result.get("notifications", [])}

        return {"error": "unknown_phone_intent"}
