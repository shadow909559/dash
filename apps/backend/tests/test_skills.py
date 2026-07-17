import asyncio

from dash_backend.skills.registry import SkillRegistry, SkillInterface
from dash_backend.skills.skill_router import SkillRouter, SkillContext
from dash_backend.desktop.service import DesktopSkill

from dash_backend.tools import tool_manager as tm_mod


def test_skill_registry_register_and_get():
    class DummySkill(SkillInterface):
        name = "dummy"

        async def handle(self, intent, args, context):
            return {"ok": True}

    # Register dummy skill
    SkillRegistry.register(DummySkill())
    s = SkillRegistry.get_skill("dummy")
    assert s is not None


def test_skill_router_routes_to_registered_skill():
    called = {}

    class TestSkill(SkillInterface):
        name = "desktop"

        async def handle(self, intent, args, context):
            called['intent'] = intent
            called['args'] = args
            return {"handled": True}

    # override desktop skill
    SkillRegistry.register(TestSkill())

    router = SkillRouter()

    async def run():
        ctx = SkillContext(user_id="u1", session_id="s1", extra={})
        res = await router.route("open something", {"target": "notepad"}, ctx)
        return res

    res = asyncio.run(run())
    assert res["status"] == "ok"
    assert called.get("intent") == "open something"


def test_desktop_skill_calls_tool_manager(monkeypatch):
    # Create a fake tool manager
    class FakeManager:
        def __init__(self):
            self.calls = []

        async def execute(self, tool_name, args):
            self.calls.append((tool_name, args))
            return {"status": "ok", "result": {"tool": tool_name}}

    fake = FakeManager()

    # Monkeypatch get_tool_manager
    original = tm_mod.get_tool_manager
    tm_mod.get_tool_manager = lambda: fake

    try:
        ds = DesktopSkill()

        async def run():
            return await ds.handle("open notepad", {"target": "notepad"}, None)

        res = asyncio.run(run())
        assert isinstance(res, dict)
        assert fake.calls, "ToolManager should have been called"
    finally:
        tm_mod.get_tool_manager = original
