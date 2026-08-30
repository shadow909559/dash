"""Unit tests for the tool-confirmation flow in the chat pipeline.

Verifies that when the executor reports PENDING_CONFIRMATION for a tool,
the chat handler surfaces a tool.confirmation_required frame containing the
token (instead of silently swallowing it), and ends the turn.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class _FakeStatus:
    def __init__(self, value: str) -> None:
        self.value = value


class _FakeResult:
    def __init__(self, token: str) -> None:
        self.status = _FakeStatus("pending_confirmation")
        self.confirmation_token = token
        self.tool_name = "create_file"
        self.summary = "Tool 'create_file' requires your confirmation to proceed."


class _FakeCall:
    tool_name = "create_file"
    arguments = {"path": "x.txt", "content": "hi"}


class _FakeStreamManager:
    """Mimics ToolManager.execute_tool_stream with one confirmation event."""

    def __init__(self, token: str) -> None:
        self.token = token

    def select_tool_definitions(self, _query=None):
        return []

    def parse_tool_calls(self, _payload):
        from dash_backend.tools.tool_manager import ToolCallRequest

        return [ToolCallRequest(tool_name="create_file", arguments={}, call_id="call1")]

    def format_result_for_llm(self, call, result):
        return None

    def execute_tool_stream(self, call, context):
        async def gen():
            yield "tool.started", {"summary": "started"}
            yield "tool.confirmation_required", {
                "tool_name": "create_file",
                "status": "pending_confirmation",
                "confirmation_token": self.token,
                "summary": "Tool 'create_file' requires your confirmation to proceed.",
            }

        return gen()


async def _run_handler(monkeypatch, token: str):
    from dash_backend.api.websocket import handlers as h
    from dash_backend.api.websocket.protocol import ChatSendMessage
    import dash_backend.tools.tool_manager as tm_mod

    monkeypatch.setattr(tm_mod, "get_tool_manager", lambda: _FakeStreamManager(token))

    # Avoid LLM/network: patch native completion to request the tool once.
    class _Native:
        assistant_text = ""
        tool_calls = [{"id": "call1", "type": "function",
                       "function": {"name": "create_file", "arguments": "{}"}}]

    async def fake_native(messages, tools=None):
        return _Native()

    async def fake_stream_native(messages, tools=None):
        yield ("final", _Native())

    monkeypatch.setattr(
        h, "chat_completion_with_native_tool_calls", fake_native
    )
    monkeypatch.setattr(
        h, "stream_chat_completion_with_native_tool_calls", fake_stream_native
    )

    # get_tool_protocol is imported at module level into handlers; patch it there.
    class _TP:
        OPENAI_NATIVE = "openai_native"

    monkeypatch.setattr(h, "get_tool_protocol", lambda: _TP.OPENAI_NATIVE)

    # Rate limiter no-op (imported into handlers namespace)
    async def noop_rate(*a, **k):
        return None

    monkeypatch.setattr(h, "websocket_rate_limit_user", noop_rate)

    msg = ChatSendMessage(message_id="m1", conversation_id=None, content="make a file")
    out = []
    async for event in h.handle_chat_send(msg, session=None, user_id="u1"):
        out.append(event)
    return out


async def test_confirmation_token_reaches_client(monkeypatch):
    out = await _run_handler(monkeypatch, token="tok-123")
    types = [e.type for e in out]
    assert "tool.confirmation_required" in types, types
    conf = [e for e in out if e.type == "tool.confirmation_required"][0]
    assert conf.confirmation_token == "tok-123"
    assert conf.tool_name == "create_file"
    # The turn must end cleanly after requesting approval.
    assert types[-1] == "chat.done"
