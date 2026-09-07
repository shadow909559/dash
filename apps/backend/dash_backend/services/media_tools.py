"""Media control tools for volume, brightness, and media keys."""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus
from dash_backend.services.media import MediaService

logger = get_logger(__name__)


class GetVolumeTool(BaseTool):
    name = "get_volume"
    description = "Get current system volume level."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.get_volume()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SetVolumeTool(BaseTool):
    name = "set_volume"
    description = "Set system volume level (0-100)."
    parameters = [
        ToolParameter("level", "Volume level 0-100", type="integer", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            level = int(kwargs.get("level", 50))
            result = await svc.set_volume(max(0, min(100, level)))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MuteAudioTool(BaseTool):
    name = "mute_audio"
    description = "Mute or unmute system audio."
    parameters = [
        ToolParameter("muted", "True to mute, False to unmute", type="boolean", required=False, default=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.set_mute(muted=kwargs.get("muted", True))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ToggleMuteTool(BaseTool):
    name = "toggle_mute"
    description = "Toggle audio mute on/off."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.toggle_mute()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class VolumeUpTool(BaseTool):
    name = "volume_up"
    description = "Increase system volume."
    parameters = [
        ToolParameter("amount", "Steps to increase (1-100)", type="integer", required=False, default=5),
    ]
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.volume_up(amount=int(kwargs.get("amount", 5)))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class VolumeDownTool(BaseTool):
    name = "volume_down"
    description = "Decrease system volume."
    parameters = [
        ToolParameter("amount", "Steps to decrease (1-100)", type="integer", required=False, default=5),
    ]
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.volume_down(amount=int(kwargs.get("amount", 5)))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MediaPlayPauseTool(BaseTool):
    name = "media_play_pause"
    description = "Toggle media play/pause."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.media_play_pause()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MediaNextTool(BaseTool):
    name = "media_next"
    description = "Skip to next media track."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.media_next()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MediaPrevTool(BaseTool):
    name = "media_prev"
    description = "Go to previous media track."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.media_prev()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MediaStopTool(BaseTool):
    name = "media_stop"
    description = "Stop media playback."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.media_stop()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class GetBrightnessTool(BaseTool):
    name = "get_brightness"
    description = "Get current screen brightness level."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            result = await svc.get_brightness()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SetBrightnessTool(BaseTool):
    name = "set_brightness"
    description = "Set screen brightness level (0-100)."
    parameters = [
        ToolParameter("level", "Brightness 0-100", type="integer", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "media"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = MediaService()
        try:
            level = int(kwargs.get("level", 50))
            result = await svc.set_brightness(max(0, min(100, level)))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))

