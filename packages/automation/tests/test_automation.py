from dash_automation.types import AutomationKind


def test_automation_kind() -> None:
    assert AutomationKind.BROWSER.value == "browser"
