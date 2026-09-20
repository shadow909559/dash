"""§25 authority consistency for input tools (decisions.md #129).

Before #129 the LLM could route around the gated desktop-automation family
(mouse_click/keyboard_type = CONFIRM, mouse_drag = RESTRICTED) by picking the
"enhanced" families, where everything — including type_unicode (types
arbitrary text), press_shortcut (arbitrary hotkeys), clipboard_paste,
right/middle click, and hold_release_key — registered as AUTO.

These tests pin the repaired invariant on the REAL registration set:

1. No tool in the mouse/keyboard categories executes input effects below
   CONFIRM, except an explicit allowlist of pure cursor positioning /
   scrolling (no text entry, no button activation).
2. The first-registration-wins name collisions resolve to the gated
   family's levels — the model cannot pick a friendlier duplicate.
3. The executor (tool_executor.py) enforces the gate at runtime: a real
   input tool returns CONFIRMATION_REQUIRED before any execution, and a
   rejection never runs the tool.
"""

from __future__ import annotations

import pytest

from dash_backend.tools import tool_registry as tr_mod
from dash_backend.tools.base_tool import BaseTool, PermissionLevel, ToolContext, ToolParameter
from dash_backend.tools.register_desktop import register_desktop_tools
from dash_backend.tools.tool_executor import ToolExecutor
from dash_backend.tools.tool_result import ToolResult, ToolStatus

# Pure cursor positioning / viewport scrolling. These never enter text and
# never activate UI, so they stay AUTO in every family (deliberate, audited).
POSITIONING_ONLY_ALLOWLIST = frozenset({
    "mouse_move",
    "mouse_relative_move",
    "mouse_smooth_move",
    "smooth_mouse_move",
    "mouse_scroll_horizontal",
    # Read-only observability: returns the automation event log; injects
    # nothing into the OS, so AUTO is correct.
    "get_automation_history",
})

INPUT_TOOL_NAMES = (
    "mouse_click",
    "keyboard_type",
    "keyboard_hotkey",
    "mouse_drag",
    "press_shortcut",
    "type_unicode",
    "clipboard_paste",
    "mouse_right_click",
    "mouse_middle_click",
    "hold_release_key",
)


@pytest.fixture()
def fresh_desktop_registry(monkeypatch):
    """Register the real desktop tool set into a throwaway registry.

    register_desktop.py registers on import into get_registry(), so the
    module global is swapped for a fresh ToolRegistry for the duration of
    the test and restored afterwards (hermetic — no global pollution).
    """
    fresh = tr_mod.ToolRegistry()
    monkeypatch.setattr(tr_mod, "_registry", fresh)
    register_desktop_tools()
    yield fresh


def test_no_input_injection_tool_below_confirm(fresh_desktop_registry):
    # "automation" is the gated desktop_automation family's category — it must
    # be scanned too, or the very family the gates exist for escapes the pin.
    input_categories = ("mouse", "keyboard", "automation")
    auto_input = {
        tool.name
        for tool in fresh_desktop_registry.get_all().values()
        if getattr(tool, "category", "") in input_categories
        and tool.permission_level < PermissionLevel.CONFIRM
    }
    unexpected = auto_input - POSITIONING_ONLY_ALLOWLIST
    assert unexpected == set(), (
        "input-injecting tools must gate at CONFIRM; unexpected AUTO tools: "
        f"{sorted(unexpected)}"
    )


def test_collision_winners_use_gated_family_levels(fresh_desktop_registry):
    # Duplicate names across families resolve first-registration-wins to the
    # gated desktop_automation levels — the friendlier duplicates are shadowed.
    assert fresh_desktop_registry.get("mouse_drag").permission_level == PermissionLevel.RESTRICTED
    assert fresh_desktop_registry.get("mouse_click").permission_level == PermissionLevel.CONFIRM
    assert fresh_desktop_registry.get("keyboard_type").permission_level == PermissionLevel.CONFIRM
    for name in INPUT_TOOL_NAMES:
        tool = fresh_desktop_registry.get(name)
        assert tool is not None, f"{name} not registered"
        assert tool.permission_level >= PermissionLevel.CONFIRM, f"{name} is not gated"


@pytest.mark.asyncio
async def test_executor_gates_real_input_tool_before_execution(fresh_desktop_registry):
    """The runtime gate fires on a REAL input tool: no hotkey is pressed
    while pending, and a rejection never executes the tool."""
    tool = fresh_desktop_registry.get("press_shortcut")
    executor = ToolExecutor(timeout=5.0)

    events = []
    async for event, result in executor.execute(
        tool, ToolContext(user_id="owner"), shortcut="save"
    ):
        events.append((event, result))

    assert [event.name for event, _ in events] == ["CONFIRMATION_REQUIRED"]
    token = events[0][1].confirmation_token
    assert token, "gate must mint a confirmation token"

    rejection = await executor.reject_confirmation(token)
    assert rejection.status == ToolStatus.REJECTED
    # Unknown tokens are rejected honestly, never silently accepted.
    unknown = await executor.reject_confirmation("not-a-real-token")
    assert unknown.status == ToolStatus.ERROR


class _CountingConfirmTool(BaseTool):
    """CONFIRM-level tool that records executions — proves the confirmed
    path runs exactly once without touching real system input."""

    name = "counting_confirm_tool"
    description = "counts confirmed executions"
    parameters = []
    category = "keyboard"

    def __init__(self) -> None:
        self.executions = 0
        super().__init__()

    @property
    def permission_level(self) -> PermissionLevel:  # type: ignore[override]
        return PermissionLevel.CONFIRM

    async def execute(self, context: ToolContext, **kwargs) -> ToolResult:
        self.executions += 1
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            summary=f"ran {self.executions}",
        )


@pytest.mark.asyncio
async def test_confirmed_input_tool_executes_exactly_once(fresh_desktop_registry):
    tool = _CountingConfirmTool()
    fresh_desktop_registry.register(tool)
    executor = ToolExecutor(timeout=5.0)

    events = []
    async for event, result in executor.execute(tool, ToolContext(user_id="owner")):
        events.append((event, result))

    assert [event.name for event, _ in events] == ["CONFIRMATION_REQUIRED"]
    token = events[0][1].confirmation_token

    finished = []
    async for event, result in executor.execute_confirmed(token):
        finished.append((event, result))

    assert [event.name for event, _ in finished] == ["STARTED", "FINISHED"]
    assert tool.executions == 1
