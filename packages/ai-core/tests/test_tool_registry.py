"""Unit tests for ToolRegistry."""

from __future__ import annotations

from typing import Mapping

import pytest

from dash_ai_core.tool_registry import ToolRegistry


def test_tool_registry_register_get_list() -> None:
    reg = ToolRegistry()

    def t(payload: Mapping[str, object]) -> str:
        return f"ok:{payload.get('a')}"

    reg.register(name="tool_a", func=t, description="desc")

    assert reg.get("tool_a").name == "tool_a"
    assert reg.list_names() == ["tool_a"]


def test_tool_registry_unknown_tool() -> None:
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.get("missing")

