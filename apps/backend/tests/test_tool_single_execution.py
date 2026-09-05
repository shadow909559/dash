"""Regression tests: one logical tool call must execute exactly once.

Previously the OpenAI-native chat path executed each tool via
execute_tool_stream() and then AGAIN via execute_tool() (plus a third time on
the timeout retry). Side-effecting tools (file delete, shell command, ...)
therefore ran multiple times.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from dash_backend.api.websocket.handlers import execute_tool_exactly_once
from dash_backend.tools.base_tool import BaseTool, ToolContext, ToolParameter
from dash_backend.tools.tool_manager import ToolCallRequest, ToolManager
from dash_backend.tools.tool_result import ToolResult, ToolStatus


class CountingTool(BaseTool):
    """Records every real execution; used to detect double-execution."""

    description = "Counts executions"
    parameters = [ToolParameter(name="n", description="unused", type="integer", required=False)]

    def __init__(self) -> None:
        from dash_backend.tools.base_tool import PermissionLevel

        self.permission_level = PermissionLevel.AUTO
        self.name = f"counting_tool_{uuid.uuid4().hex[:8]}"
        self.executions = 0
        super().__init__()

    async def execute(self, context: ToolContext, **kwargs):
        self.executions += 1
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            summary=f"ran {self.executions}",
            output={"n": self.executions},
        )


class SlowTool(CountingTool):
    def __init__(self) -> None:
        super().__init__()
        self.executions = 0  # completed executions only

    async def execute(self, context: ToolContext, **kwargs):
        await asyncio.sleep(3)
        self.executions += 1
        return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="done")


@pytest.mark.asyncio
async def test_tool_executes_exactly_once() -> None:
    tool = CountingTool()
    manager = ToolManager()
    manager._registry.register(tool)

    call = ToolCallRequest(tool_name=tool.name, arguments={})
    context = ToolContext(user_id="owner")

    lines, final_result, aborted = await execute_tool_exactly_once(
        manager, call, context, timeout_seconds=10.0
    )

    assert aborted is False
    assert tool.executions == 1, f"expected exactly one execution, got {tool.executions}"
    assert final_result is not None
    assert final_result.status == ToolStatus.SUCCESS
    assert final_result.summary == "ran 1"
    assert any("finished" in line for line in lines)


@pytest.mark.asyncio
async def test_timeout_does_not_re_execute() -> None:
    """A stream timeout must NOT trigger a second execution of a side-effecting tool."""
    tool = SlowTool()
    manager = ToolManager()
    manager._registry.register(tool)

    call = ToolCallRequest(tool_name=tool.name, arguments={})
    context = ToolContext(user_id="owner")

    lines, final_result, aborted = await execute_tool_exactly_once(
        manager, call, context, timeout_seconds=0.2
    )

    assert aborted is True
    assert final_result is None
    # The slow tool never completes within the timeout and is never re-run.
    assert tool.executions <= 1 and final_result is None
    assert any("timed out" in line for line in lines)


@pytest.mark.asyncio
async def test_unknown_tool_is_reported_not_executed() -> None:
    manager = ToolManager()
    call = ToolCallRequest(tool_name="does_not_exist_xyz", arguments={})
    context = ToolContext(user_id="owner")

    lines, final_result, aborted = await execute_tool_exactly_once(
        manager, call, context, timeout_seconds=5.0
    )

    assert aborted is True
    assert final_result is not None
    assert final_result.status == ToolStatus.ERROR
