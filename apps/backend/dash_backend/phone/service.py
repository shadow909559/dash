from __future__ import annotations

from typing import Dict, Any, Optional

from dash_backend.logging_config import get_logger
from dash_backend.tools.tool_manager import get_tool_manager

logger = get_logger(__name__)


class PhoneSkill:
    name = "phone"

    def __init__(self, tool_manager: Optional[Any] = None):
        self.tool_manager = tool_manager or get_tool_manager()

    async def handle(self, intent: str, args: Dict[str, Any], context: Any) -> Dict[str, Any]:
        logger.info("PhoneSkill handling %s %s", intent, args)
        if intent.startswith("call"):
            number = args.get("number") or args.get("contact")
            if not number:
                return {"error": "no_number"}
            # Placeholder: integrate with companion app
            return {"status": "ok", "action": "call_requested", "number": number}
        if intent.startswith("sms") or intent.startswith("message"):
            return {"status": "ok", "action": "sms_requested", "args": args}
        return {"error": "unknown_phone_intent"}
