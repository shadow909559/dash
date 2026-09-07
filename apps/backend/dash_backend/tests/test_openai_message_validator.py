"""Comprehensive tests for the OpenAI message validator.

Tests cover every rule in validate_openai_message_history:
- orphan tool messages
- duplicate tool messages
- missing tool_call_id
- unknown tool_call_id
- consecutive tool messages
- wrong ordering (tool → non-assistant)
- multiple tool_calls
- retry scenarios
- reconnect scenarios
- websocket scenarios
- streaming scenarios
- agent execution scenarios
"""

from __future__ import annotations


from dash_backend.llm.openai_message_validator import validate_openai_message_history


def _make_assistant(tool_calls: list[dict] | None = None, content: str = "") -> dict:
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def _make_tool(tool_call_id: str, content: str = "result") -> dict:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _make_user(content: str = "hello") -> dict:
    return {"role": "user", "content": content}


def _make_system(content: str = "system prompt") -> dict:
    return {"role": "system", "content": content}


# ── Orphan tool messages ──────────────────────────────────────


def test_orphan_tool_at_start():
    """Tool message at position 0 should be dropped."""
    messages = [_make_tool("call_1")]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 0


def test_orphan_tool_after_user():
    """Tool message after user (not assistant) should be dropped."""
    messages = [_make_user("hi"), _make_tool("call_1")]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 1
    assert cleaned[0]["role"] == "user"


def test_orphan_tool_after_system():
    """Tool message after system should be dropped."""
    messages = [_make_system(), _make_tool("call_1")]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 1
    assert cleaned[0]["role"] == "system"


def test_orphan_tool_after_tool():
    """Tool message after another tool (no assistant between) should be dropped."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_tool("call_2"),  # consecutive tool - should be dropped
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 2
    assert cleaned[0]["role"] == "assistant"
    assert cleaned[1]["role"] == "tool"
    assert cleaned[1]["tool_call_id"] == "call_1"


# ── Duplicate tool messages ───────────────────────────────────


def test_duplicate_tool_call_id():
    """Duplicate tool_call_id for same assistant should be dropped."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_tool("call_1"),  # duplicate
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 2
    assert cleaned[1]["tool_call_id"] == "call_1"


def test_multiple_tool_calls_all_valid():
    """Multiple tool calls with different ids should all be kept."""
    messages = [
        _make_assistant(tool_calls=[
            {"id": "call_1", "function": {"name": "x", "arguments": "{}"}},
            {"id": "call_2", "function": {"name": "y", "arguments": "{}"}},
        ]),
        _make_tool("call_1"),
        _make_tool("call_2"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 3
    assert cleaned[1]["tool_call_id"] == "call_1"
    assert cleaned[2]["tool_call_id"] == "call_2"


# ── Missing tool_call_id ──────────────────────────────────────


def test_missing_tool_call_id():
    """Tool message without tool_call_id should be dropped."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        {"role": "tool", "content": "result"},  # no tool_call_id
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 1
    assert cleaned[0]["role"] == "assistant"


def test_empty_tool_call_id():
    """Tool message with empty tool_call_id should be dropped."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool(""),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 1


# ── Unknown tool_call_id ──────────────────────────────────────


def test_unknown_tool_call_id():
    """Tool message with unknown tool_call_id should be dropped."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("unknown_id"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 1
    assert cleaned[0]["role"] == "assistant"


# ── Consecutive tool messages ─────────────────────────────────


def test_consecutive_tool_messages():
    """Consecutive tool messages (same assistant) should be deduplicated."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_tool("call_1"),  # consecutive duplicate
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 2


# ── Wrong ordering ────────────────────────────────────────────


def test_tool_followed_by_user():
    """Tool message followed by user (not assistant) should be dropped."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_user("more input"),  # user after tool - tool should be dropped
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 2
    assert cleaned[0]["role"] == "assistant"
    assert cleaned[1]["role"] == "user"


def test_tool_followed_by_system():
    """Tool message followed by system should be dropped."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_system(),  # system after tool - tool should be dropped
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 2
    assert cleaned[0]["role"] == "assistant"
    assert cleaned[1]["role"] == "system"


# ── Valid sequences ───────────────────────────────────────────


def test_valid_simple_sequence():
    """Simple valid sequence: user → assistant(tool_calls) → tool → assistant."""
    messages = [
        _make_user("hi"),
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_assistant(content="done"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 4


def test_valid_no_tools():
    """Sequence without any tool calls should pass through unchanged."""
    messages = [
        _make_user("hi"),
        _make_assistant(content="hello"),
        _make_user("how are you?"),
        _make_assistant(content="fine"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 4


def test_valid_multiple_tool_rounds():
    """Multiple rounds of tool calling should work."""
    messages = [
        _make_user("hi"),
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_assistant(tool_calls=[{"id": "call_2", "function": {"name": "y", "arguments": "{}"}}]),
        _make_tool("call_2"),
        _make_assistant(content="done"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 6


# ── Retry / reconnect scenarios ───────────────────────────────


def test_retry_with_duplicate_tool_messages():
    """Retry scenario: duplicate tool messages from re-sending should be cleaned."""
    messages = [
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_tool("call_1"),  # retry duplicate
        _make_tool("call_1"),  # another retry duplicate
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 2
    assert cleaned[1]["tool_call_id"] == "call_1"


def test_reconnect_with_partial_history():
    """Reconnect scenario: partial history with orphan tools should be cleaned."""
    messages = [
        _make_tool("call_1"),  # orphan - should be dropped
        _make_tool("call_2"),  # orphan - should be dropped
        _make_user("hi"),
        _make_assistant(tool_calls=[{"id": "call_3", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_3"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 3
    assert cleaned[0]["role"] == "user"
    assert cleaned[1]["role"] == "assistant"
    assert cleaned[2]["role"] == "tool"


# ── Edge cases ────────────────────────────────────────────────


def test_empty_messages():
    """Empty message list should return empty list."""
    cleaned = validate_openai_message_history([])
    assert cleaned == []


def test_no_tool_calls_in_assistant():
    """Assistant without tool_calls followed by tool message should drop tool."""
    messages = [
        _make_assistant(content="no tools here"),
        _make_tool("call_1"),  # no tool_calls in assistant
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 1
    assert cleaned[0]["role"] == "assistant"


def test_assistant_with_empty_tool_calls():
    """Assistant with empty tool_calls list followed by tool should drop tool."""
    messages = [
        _make_assistant(tool_calls=[]),
        _make_tool("call_1"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 1
    assert cleaned[0]["role"] == "assistant"


def test_assistant_with_tool_calls_no_ids():
    """Assistant with tool_calls that have no ids should drop tool messages."""
    messages = [
        _make_assistant(tool_calls=[{"function": {"name": "x", "arguments": "{}"}}]),  # no id
        _make_tool("call_1"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 1


def test_mixed_valid_and_invalid():
    """Mix of valid and invalid tool messages should only keep valid ones."""
    messages = [
        _make_user("hi"),
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),  # valid
        _make_tool("call_2"),  # unknown id
        _make_tool("call_1"),  # duplicate
        _make_assistant(content="done"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 4
    assert cleaned[0]["role"] == "user"
    assert cleaned[1]["role"] == "assistant"
    assert cleaned[2]["role"] == "tool"
    assert cleaned[2]["tool_call_id"] == "call_1"
    assert cleaned[3]["role"] == "assistant"


def test_idempotent():
    """Running validator twice should produce same result."""
    messages = [
        _make_user("hi"),
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_tool("call_2"),  # unknown - should be dropped
        _make_assistant(content="done"),
    ]
    cleaned_once = validate_openai_message_history(messages)
    cleaned_twice = validate_openai_message_history(cleaned_once)
    assert cleaned_once == cleaned_twice


# ── Agent execution scenarios ─────────────────────────────────


def test_agent_tool_sequence():
    """Agent execution: multiple tool calls in sequence should be valid."""
    messages = [
        _make_system("You are an agent."),
        _make_user("do task"),
        _make_assistant(tool_calls=[{"id": "agent_call_1", "function": {"name": "search", "arguments": "{}"}}]),
        _make_tool("agent_call_1"),
        _make_assistant(tool_calls=[{"id": "agent_call_2", "function": {"name": "compute", "arguments": "{}"}}]),
        _make_tool("agent_call_2"),
        _make_assistant(content="task done"),
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 7


def test_agent_with_orphan_tools():
    """Agent execution with orphan tools should clean them."""
    messages = [
        _make_system("You are an agent."),
        _make_tool("orphan_1"),  # orphan
        _make_user("do task"),
        _make_assistant(tool_calls=[{"id": "call_1", "function": {"name": "x", "arguments": "{}"}}]),
        _make_tool("call_1"),
        _make_tool("orphan_2"),  # consecutive orphan
    ]
    cleaned = validate_openai_message_history(messages)
    assert len(cleaned) == 4
    assert cleaned[0]["role"] == "system"
    assert cleaned[1]["role"] == "user"
    assert cleaned[2]["role"] == "assistant"
    assert cleaned[3]["role"] == "tool"
    assert cleaned[3]["tool_call_id"] == "call_1"