import pytest

from dash_backend.agents import service as agent_service
from dash_backend.agents import models as agent_models


class DummySession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        return


@pytest.mark.asyncio
async def test_create_and_update_agent():
    session = DummySession()
    agent = await agent_service.create_agent(session, "Test Agent", "desc", "You are a test agent.", ["read_file"])
    assert agent.id is not None
    assert agent.name == "Test Agent"

    updated = await agent_service.update_agent(session, agent.id, name="Renamed")
    assert updated is not None
    assert updated.name == "Renamed"
