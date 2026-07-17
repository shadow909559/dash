import asyncio
from datetime import datetime

import pytest

from dash_backend.automation import service as automation_service
from dash_backend.automation import models as automation_models
from dash_backend.tools.tool_result import ToolResult, ToolStatus


class DummySession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        # noop
        return


class FakeManager:
    def __init__(self, result: ToolResult):
        self._result = result

    async def execute_tool(self, call, ctx):
        return self._result


@pytest.mark.asyncio
async def test_execute_automation_persists_execution(monkeypatch):
    # Create a fake automation ORM instance
    auto = automation_models.Automation(
        user_id="00000000-0000-0000-0000-000000000001",
        name="Test Auto",
        trigger_type="interval",
        schedule="1",
        tool_name="read_file",
        tool_arguments={"path": "test.txt"},
        enabled=True,
    )

    # Prepare dummy session to capture adds
    session = DummySession()

    # Prepare a fake tool result
    tr = ToolResult(tool_name="read_file", status=ToolStatus.SUCCESS, output={"ok": True}, summary="ok")

    # Patch get_tool_manager in the automation_service module
    monkeypatch.setattr(automation_service, "get_tool_manager", lambda: FakeManager(tr))

    res = await automation_service.execute_automation(session, auto)

    assert res["status"] == "SUCCESS"
    # Ensure commit was called
    assert session.committed is True
    # Ensure an AutomationExecution record was added
    found = any(type(obj).__name__ == "AutomationExecution" for obj in session.added)
    assert found, f"AutomationExecution not recorded, added: {session.added}"
