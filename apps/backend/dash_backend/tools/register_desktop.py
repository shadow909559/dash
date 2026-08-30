"""Register all desktop tools with the tool registry."""

from __future__ import annotations

from dash_backend.tools.tool_registry import get_registry
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Import tool classes from desktop_windows_tools
from dash_backend.tools.desktop_windows_tools import (
    OpenApplicationTool,
    CloseApplicationTool,
    RestartApplicationTool,
    ListProcessesTool,
    BringWindowToFrontTool,
    OpenURLTool,
    SearchWebTool,
    OpenTabTool,
    CloseTabTool,
    RefreshTabTool,
    CopyTextTool,
    ReadClipboardTool,
    ClearClipboardTool,
    ShowMessageTool,
    PlaySoundTool,
    SystemInfoTool,
    RunCommandTool,
)

# Import power and media tools
from dash_backend.services.power_tools import (
    ShutdownTool,
    RestartTool,
    LockWorkstationTool,
    SleepTool,
    HibernateTool,
    LogoffTool,
)

from dash_backend.services.media_tools import (
    GetVolumeTool,
    SetVolumeTool,
    MuteAudioTool,
    ToggleMuteTool,
    VolumeUpTool,
    VolumeDownTool,
    MediaPlayPauseTool,
    MediaNextTool,
    MediaPrevTool,
    MediaStopTool,
    GetBrightnessTool,
    SetBrightnessTool,
)

from dash_backend.tools.system_management_tools import (
    StartupAppsTool,
    EnvironmentVariablesTool,
    InstalledFontsTool,
    WifiProfilesTool,
    WindowsUpdatesStatusTool,
    ServicesListTool,
    ServiceControlTool,
    DisplaySettingsTool,
    NetworkAdaptersTool,
    TaskSchedulerListTool,
)

from dash_backend.tools.explorer_tools import (
    BrowseFoldersTool,
    OpenFolderTool,
    OpenFileTool,
    RenameFileTool,
    DeleteFileTool,
    MoveFileTool,
    CopyFileTool,
    SearchExplorerTool,
    SpecialFoldersTool,
    EnumerateDrivesTool,
    RecentFilesTool,
)

# Import enhanced window management tools
from dash_backend.tools.window_management_tools import (
    RestoreWindowTool,
    MoveWindowTool,
    ResizeWindowTool,
    SnapWindowTool,
    DetectActiveWindowTool,
    ListMonitorsTool,
)

# Import advanced window control tools
from dash_backend.tools.window_advanced import (
    MaximizeWindowTool,
    MinimizeWindowTool,
    SendToBackWindowTool,
    TileWindowsTool,
    CascadeWindowsTool,
    ArrangeWindowsTool,
)

# Import enhanced mouse tools
from dash_backend.tools.mouse_tools import (
    MouseRelativeMoveTool,
    MouseRightClickTool,
    MouseMiddleClickTool,
    MouseDragTool,
    MouseSmoothMoveTool,
    MouseScrollHorizontalTool,
)

# Import enhanced keyboard tools
from dash_backend.tools.keyboard_tools import (
    ClipboardPasteTool,
    PressShortcutTool,
    TypeUnicodeTool,
)

# Import enhanced browser tools
from dash_backend.tools.browser_tools import (
    SearchYouTubeTool,
    CloseBrowserTabTool,
)

# Import registry tools
from dash_backend.tools.registry_tools import (
    ReadRegistryTool,
)

# Import device tools
from dash_backend.tools.device_tools import (
    ListAudioDevicesTool,
    ListUsbDevicesTool,
    ListPrintersTool,
    ListBluetoothDevicesTool,
    ListDisplaysTool,
)

# Import terminal tools
from dash_backend.tools.terminal_tools import (
    RunCmdTool,
    RunPowerShellTool,
    RunScriptTool,
    CancelTaskTool,
    ListTasksTool,
)

# Import file tools
from dash_backend.tools.file_tools import (
    ListFavoritesTool,
    PreviewFileTool,
    RecycleBinTool,
    EmptyRecycleBinTool,
)

# Import download manager tools
from dash_backend.tools.download_manager_tools import (
    ListDownloadsTool,
    OrganizeDownloadsTool,
    DownloadStatsTool,
)

# Import enhanced detection tools
from dash_backend.services.enhanced_tools import (
    BrowserDetectionTool,
    ApplicationSearchTool,
    SmoothMouseMoveTool,
    KeyboardHoldReleaseTool,
    TypeUnicodeTool as EnhancedTypeUnicodeTool,
    ClipboardHistoryTool,
    ClearClipboardHistoryTool,
)


def register_desktop_tools() -> None:
    registry = get_registry()
    tool_classes = [
        # Desktop window and app tools (17 tools)
        OpenApplicationTool,
        CloseApplicationTool,
        RestartApplicationTool,
        ListProcessesTool,
        BringWindowToFrontTool,
        OpenURLTool,
        SearchWebTool,
        OpenTabTool,
        CloseTabTool,
        RefreshTabTool,
        CopyTextTool,
        ReadClipboardTool,
        ClearClipboardTool,
        ShowMessageTool,
        PlaySoundTool,
        SystemInfoTool,
        RunCommandTool,
        # Power tools (6 tools)
        ShutdownTool,
        RestartTool,
        LockWorkstationTool,
        SleepTool,
        HibernateTool,
        LogoffTool,
        # Media tools (12 tools)
        GetVolumeTool,
        SetVolumeTool,
        MuteAudioTool,
        ToggleMuteTool,
        VolumeUpTool,
        VolumeDownTool,
        MediaPlayPauseTool,
        MediaNextTool,
        MediaPrevTool,
        MediaStopTool,
        GetBrightnessTool,
        SetBrightnessTool,
        # System management tools (10 tools)
        StartupAppsTool,
        EnvironmentVariablesTool,
        InstalledFontsTool,
        WifiProfilesTool,
        WindowsUpdatesStatusTool,
        ServicesListTool,
        ServiceControlTool,
        DisplaySettingsTool,
        NetworkAdaptersTool,
        TaskSchedulerListTool,
        # Explorer/file tools (11 tools)
        BrowseFoldersTool,
        OpenFolderTool,
        OpenFileTool,
        RenameFileTool,
        DeleteFileTool,
        MoveFileTool,
        CopyFileTool,
        SearchExplorerTool,
        SpecialFoldersTool,
        EnumerateDrivesTool,
        RecentFilesTool,
        # Enhanced window management tools (6 tools)
        RestoreWindowTool,
        MoveWindowTool,
        ResizeWindowTool,
        SnapWindowTool,
        DetectActiveWindowTool,
        ListMonitorsTool,
        # Advanced window control tools (6 tools)
        MaximizeWindowTool,
        MinimizeWindowTool,
        SendToBackWindowTool,
        TileWindowsTool,
        CascadeWindowsTool,
        ArrangeWindowsTool,
        # Enhanced mouse tools (6 tools)
        MouseRelativeMoveTool,
        MouseRightClickTool,
        MouseMiddleClickTool,
        MouseDragTool,
        MouseSmoothMoveTool,
        MouseScrollHorizontalTool,
        # Enhanced keyboard tools (3 tools)
        ClipboardPasteTool,
        PressShortcutTool,
        TypeUnicodeTool,
        # Enhanced browser tools (2 tools)
        SearchYouTubeTool,
        CloseBrowserTabTool,
        # System tools (1 tool)
        ReadRegistryTool,
        # Device tools (5 tools)
        ListAudioDevicesTool,
        ListUsbDevicesTool,
        ListPrintersTool,
        ListBluetoothDevicesTool,
        ListDisplaysTool,
        # Terminal tools (5 tools)
        RunCmdTool,
        RunPowerShellTool,
        RunScriptTool,
        CancelTaskTool,
        ListTasksTool,
        # File tools (4 tools)
        ListFavoritesTool,
        PreviewFileTool,
        RecycleBinTool,
        EmptyRecycleBinTool,
        # Download manager tools (3 tools)
        ListDownloadsTool,
        OrganizeDownloadsTool,
        DownloadStatsTool,
        # Enhanced detection/input tools (7 tools)
        BrowserDetectionTool,
        ApplicationSearchTool,
        SmoothMouseMoveTool,
        KeyboardHoldReleaseTool,
        EnhancedTypeUnicodeTool,
        ClipboardHistoryTool,
        ClearClipboardHistoryTool,
    ]
    logger.info("Registering %d desktop tools", len(tool_classes))
    for cls in tool_classes:
        name = getattr(cls, "name", cls.__name__)
        try:
            if registry.get(name) is None:
                registry.register(cls())
        except Exception:
            logger.exception("Failed to register tool %s", name)


# Run on import
register_desktop_tools()

