"""WhatsApp integration tools - placeholder with limitation reporting.

WhatsApp does not provide an official public API for sending messages programmatically.
Third-party solutions exist but have significant limitations:
- WhatsApp Business API: Requires business verification and approval
- Unofficial libraries (whatsapp-web.js, yowsup): May violate ToS, unstable
- Desktop automation: Requires WhatsApp Web to be open, fragile

This implementation reports the limitations as requested.
"""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


_WHATSAPP_LIMITATIONS = """
WhatsApp Integration Limitations:
- No official public API for personal accounts
- WhatsApp Business API requires business verification
- Unofficial libraries may violate Terms of Service
- Desktop automation requires WhatsApp Web to be open
- No reliable way to send messages programmatically without user interaction

Alternatives:
1. Use WhatsApp Business API (requires business account)
2. Use desktop automation with WhatsApp Web (fragile)
3. Use email or other messaging platforms with official APIs
"""


class WhatsAppSendTool(BaseTool):
    name = "whatsapp_send"
    description = "Send a WhatsApp message (UNSUPPORTED - no official API available)."
    parameters = [
        ToolParameter("to", "Phone number or contact", required=True),
        ToolParameter("message", "Message content", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "whatsapp"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="WhatsApp send operation not supported - no official API available",
            output={
                "limitations": _WHATSAPP_LIMITATIONS.strip(),
                "operation": "send_message",
                "parameters": kwargs,
                "unsupported_reason": "No official public API for personal WhatsApp accounts"
            },
            summary="WhatsApp message sending is not supported - lacks official API"
        )


class WhatsAppSearchContactsTool(BaseTool):
    name = "whatsapp_search_contacts"
    description = "Search WhatsApp contacts (UNSUPPORTED - no official API available)."
    parameters = [
        ToolParameter("query", "Search query for contacts", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "whatsapp"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="WhatsApp contact search not supported - no official API available",
            output={
                "limitations": _WHATSAPP_LIMITATIONS.strip(),
                "operation": "search_contacts",
                "parameters": kwargs,
                "unsupported_reason": "No official public API for personal WhatsApp accounts"
            },
            summary="WhatsApp contact search is not supported - lacks official API"
        )


class WhatsAppNotificationsTool(BaseTool):
    name = "whatsapp_notifications"
    description = "Get WhatsApp notifications (UNSUPPORTED - no official API available)."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "whatsapp"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="WhatsApp notifications not supported - no official API available",
            output={
                "limitations": _WHATSAPP_LIMITATIONS.strip(),
                "operation": "get_notifications",
                "unsupported_reason": "No official public API for personal WhatsApp accounts"
            },
            summary="WhatsApp notifications are not supported - lacks official API"
        )
