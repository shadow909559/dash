"""Instagram integration tools - placeholder with limitation reporting.

Instagram Basic Display API is very limited:
- Only allows access to user profile and media
- No direct messaging API for personal accounts
- No notification API
- Requires OAuth2 app approval from Meta
- Read-only access to user's own media only

Instagram Graph API (for business accounts) has more features but:
- Requires business/creator account
- Requires app review and approval
- Complex setup process

This implementation reports the limitations as requested.
"""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


_INSTAGRAM_LIMITATIONS = """
Instagram Integration Limitations:
- Instagram Basic Display API: Read-only, user's own media only
- No messaging API for personal accounts
- No notification API available
- Instagram Graph API requires business/creator account
- Requires Meta app review and approval
- Complex OAuth2 setup with app permissions

Available with Basic Display API (after setup):
- Get user profile information
- Get user's media (photos, videos)
- Get media comments (own media only)

Not Available:
- Send messages
- Read notifications
- Access other users' content
- Real-time events

To enable Instagram integration:
1. Create Meta Developer account
2. Create Instagram Basic Display app
3. Configure OAuth2 redirect URI
4. Install: pip install requests
5. Set INSTAGRAM_CLIENT_ID and INSTAGRAM_CLIENT_SECRET
"""


class InstagramNotificationsTool(BaseTool):
    name = "instagram_notifications"
    description = "Get Instagram notifications (UNSUPPORTED - no notification API available)."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "instagram"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Instagram notifications not supported - no notification API available",
            output={
                "limitations": _INSTAGRAM_LIMITATIONS.strip(),
                "operation": "get_notifications",
                "unsupported_reason": "Instagram does not provide a notification API"
            },
            summary="Instagram notifications are not supported - API limitation"
        )


class InstagramReadMessagesTool(BaseTool):
    name = "instagram_read_messages"
    description = "Read Instagram messages (UNSUPPORTED - no messaging API for personal accounts)."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "instagram"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Instagram messaging not supported for personal accounts",
            output={
                "limitations": _INSTAGRAM_LIMITATIONS.strip(),
                "operation": "read_messages",
                "unsupported_reason": "Instagram messaging API only available for business accounts with special approval"
            },
            summary="Instagram message reading is not supported - requires business account"
        )


class InstagramSendMessagesTool(BaseTool):
    name = "instagram_send_message"
    description = "Send Instagram message (UNSUPPORTED - no messaging API for personal accounts)."
    parameters = [
        ToolParameter("to", "Recipient username", required=True),
        ToolParameter("message", "Message content", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "instagram"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Instagram messaging not supported for personal accounts",
            output={
                "limitations": _INSTAGRAM_LIMITATIONS.strip(),
                "operation": "send_message",
                "parameters": kwargs,
                "unsupported_reason": "Instagram messaging API only available for business accounts with special approval"
            },
            summary="Instagram message sending is not supported - requires business account"
        )


class InstagramGetProfileTool(BaseTool):
    name = "instagram_get_profile"
    description = "Get Instagram user profile (requires OAuth2 setup - see tool error for details)."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "instagram"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Instagram API not configured",
            output={
                "setup_required": _INSTAGRAM_LIMITATIONS.strip(),
                "operation": "get_profile",
                "note": "Requires Instagram Basic Display API OAuth2 setup"
            },
            summary="Instagram profile access requires API credentials setup"
        )


class InstagramGetMediaTool(BaseTool):
    name = "instagram_get_media"
    description = "Get Instagram user media (requires OAuth2 setup - see tool error for details)."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "instagram"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Instagram API not configured",
            output={
                "setup_required": _INSTAGRAM_LIMITATIONS.strip(),
                "operation": "get_media",
                "note": "Requires Instagram Basic Display API OAuth2 setup"
            },
            summary="Instagram media access requires API credentials setup"
        )
