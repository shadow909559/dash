from __future__ import annotations

from dash_backend.tools.tool_registry import get_registry
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Import tool classes
from dash_backend.tools.desktop_windows_tools import (
    OpenApplicationTool,
    CloseApplicationTool,
    RestartApplicationTool,
    ListProcessesTool,
    BringWindowToFrontTool,
    OpenURLTool,
    SearchWebTool,
    OpenTabTool,
    CopyTextTool,
    ReadClipboardTool,
    ClearClipboardTool,
    ShowMessageTool,
    PlaySoundTool,
    SystemInfoTool,
    RunCommandTool,
)


def register_desktop_tools() -> None:
    registry = get_registry()
    tool_classes = [
        OpenApplicationTool,
        CloseApplicationTool,
        RestartApplicationTool,
        ListProcessesTool,
        BringWindowToFrontTool,
        OpenURLTool,
        SearchWebTool,
        OpenTabTool,
        CopyTextTool,
        ReadClipboardTool,
        ClearClipboardTool,
        ShowMessageTool,
        PlaySoundTool,
        SystemInfoTool,
        RunCommandTool,
    ]
    for cls in tool_classes:
        name = getattr(cls, "name", cls.__name__)
        try:
            if registry.get(name) is None:
                registry.register(cls())
        except Exception:
            logger.exception("Failed to register tool %s", name)


# Run on import
register_desktop_tools()
