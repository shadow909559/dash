"""Gmail integration tools - requires Google API credentials and OAuth2 setup.

To enable Gmail integration:
1. Create a Google Cloud project at https://console.cloud.google.com
2. Enable Gmail API
3. Create OAuth2 credentials (client_id.json)
4. Install: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
5. Set GOOGLE_CREDENTIALS_PATH environment variable to client_id.json path

This is a placeholder implementation that reports the setup requirements.
"""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


_GMAIL_SETUP_REQUIRED = """
Gmail integration requires setup:
1. Create Google Cloud project and enable Gmail API
2. Install: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
3. Set GOOGLE_CREDENTIALS_PATH environment variable
4. Run OAuth2 consent flow to authorize access
See: https://developers.google.com/gmail/api/quickstart/python
"""


class GmailSendTool(BaseTool):
    name = "gmail_send"
    description = "Send an email via Gmail (requires Google API setup - see tool error for details)."
    parameters = [
        ToolParameter("to", "Recipient email address", required=True),
        ToolParameter("subject", "Email subject", required=True),
        ToolParameter("body", "Email body content", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "gmail"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Gmail API not configured",
            output={
                "setup_required": _GMAIL_SETUP_REQUIRED.strip(),
                "operation": "send_email",
                "parameters": kwargs
            },
            summary="Gmail integration requires Google API credentials setup"
        )


class GmailReadTool(BaseTool):
    name = "gmail_read"
    description = "Read Gmail inbox messages (requires Google API setup - see tool error for details)."
    parameters = [
        ToolParameter("max_results", "Maximum number of messages to retrieve", required=False, default=10, type="integer"),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "gmail"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Gmail API not configured",
            output={
                "setup_required": _GMAIL_SETUP_REQUIRED.strip(),
                "operation": "read_inbox",
                "parameters": kwargs
            },
            summary="Gmail integration requires Google API credentials setup"
        )


class GmailSearchTool(BaseTool):
    name = "gmail_search"
    description = "Search Gmail messages (requires Google API setup - see tool error for details)."
    parameters = [
        ToolParameter("query", "Gmail search query", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "gmail"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Gmail API not configured",
            output={
                "setup_required": _GMAIL_SETUP_REQUIRED.strip(),
                "operation": "search_messages",
                "parameters": kwargs
            },
            summary="Gmail integration requires Google API credentials setup"
        )


class GmailReplyTool(BaseTool):
    name = "gmail_reply"
    description = "Reply to a Gmail message (requires Google API setup - see tool error for details)."
    parameters = [
        ToolParameter("message_id", "Gmail message ID to reply to", required=True),
        ToolParameter("body", "Reply body content", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "gmail"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Gmail API not configured",
            output={
                "setup_required": _GMAIL_SETUP_REQUIRED.strip(),
                "operation": "reply_to_message",
                "parameters": kwargs
            },
            summary="Gmail integration requires Google API credentials setup"
        )


class GmailArchiveTool(BaseTool):
    name = "gmail_archive"
    description = "Archive Gmail messages (requires Google API setup - see tool error for details)."
    parameters = [
        ToolParameter("message_id", "Gmail message ID to archive", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "gmail"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Gmail API not configured",
            output={
                "setup_required": _GMAIL_SETUP_REQUIRED.strip(),
                "operation": "archive_message",
                "parameters": kwargs
            },
            summary="Gmail integration requires Google API credentials setup"
        )


class GmailDeleteTool(BaseTool):
    name = "gmail_delete"
    description = "Delete Gmail messages (requires Google API setup - see tool error for details)."
    parameters = [
        ToolParameter("message_id", "Gmail message ID to delete", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "gmail"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Gmail API not configured",
            output={
                "setup_required": _GMAIL_SETUP_REQUIRED.strip(),
                "operation": "delete_message",
                "parameters": kwargs
            },
            summary="Gmail integration requires Google API credentials setup"
        )


class GmailSummarizeTool(BaseTool):
    name = "gmail_summarize"
    description = "Summarize Gmail inbox (requires Google API setup - see tool error for details)."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "gmail"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message="Gmail API not configured",
            output={
                "setup_required": _GMAIL_SETUP_REQUIRED.strip(),
                "operation": "summarize_inbox",
                "parameters": kwargs
            },
            summary="Gmail integration requires Google API credentials setup"
        )
