


def _is_valid_openai_tool_sequence(messages: list[dict]):
    """Local helper mirroring the OpenAI rule we enforce in server code."""
    for i, m in enumerate(messages):
        if m.get("role") == "tool":
            if i == 0:
                return False
            prev = messages[i - 1]
            if prev.get("role") != "assistant":
                return False
            prev_tool_calls = prev.get("tool_calls") or []
            tool_call_id = m.get("tool_call_id")
            if not tool_call_id:
                return False
            if not any((tc or {}).get("id") == tool_call_id for tc in prev_tool_calls):
                return False
    return True


def test_orphan_tool_message_is_invalid():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "tool", "tool_call_id": "abc", "content": "{}"},
    ]
    assert not _is_valid_openai_tool_sequence(messages)


def test_valid_tool_message_sequence():
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "abc", "function": {"name": "x", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "abc", "content": "{}"},
    ]
    assert _is_valid_openai_tool_sequence(messages)

