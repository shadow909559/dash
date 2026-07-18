import uuid

import pytest

from dash_backend.agents import service as agent_service
from dash_backend.agents import models as agent_models


class DummySession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, 'id', None) is None:
            obj.id = uuid.uuid4()

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        return

    async def execute(self, stmt):
        if hasattr(stmt, 'whereclause'):
            where = stmt.whereclause
            if where is not None:
                target_id = None
                if hasattr(where, 'right'):
                    val = where.right
                    target_id = val.value if hasattr(val, 'value') else val
                if target_id is not None:
                    for obj in self.added:
                        if getattr(obj, 'id', None) == target_id:
                            values = getattr(stmt, '_values', {})
                            for col, param in values.items():
                                setattr(obj, col.name, param.value)
                            break
        return None

    async def get(self, model, pk):
        for obj in self.added:
            if getattr(obj, 'id', None) == pk:
                return obj
        return None


@pytest.mark.asyncio
async def test_create_and_update_agent():
    session = DummySession()
    agent = await agent_service.create_agent(session, "Test Agent", "desc", "You are a test agent.", ["read_file"])
    assert agent.id is not None
    assert agent.name == "Test Agent"

    updated = await agent_service.update_agent(session, agent.id, name="Renamed")
    assert updated is not None
    assert updated.name == "Renamed"
