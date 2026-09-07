"""OCR tools for Dash - extract text from images, screenshots, and clipboard.

Uses TesseractOCRProvider via VisionService.
All tools auto-register with ToolRegistry via BaseTool subclass discovery.
"""

from __future__ import annotations

import base64
import os
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus
from dash_backend.vision.service import VisionService, get_vision_registry
from dash_backend.vision.tesseract_provider import TesseractOCRProvider

logger = get_logger(__name__)

# Register the Tesseract provider in the vision registry at import time
_registry = get_vision_registry()
_registry.register_ocr("tesseract", TesseractOCRProvider())

# Shared vision service
_vision_service = VisionService()


def _get_service() -> VisionService:
    return _vision_service


# ── ocr_image ───────────────────────────────────────

class OCRImageTool(BaseTool):
    name = "ocr_image"
    description = "Extract text from an image file using Tesseract OCR."
    parameters = [
        ToolParameter("path", "Path to the image file", required=True),
        ToolParameter("lang", "Tesseract language code (e.g. 'eng')", required=False, default="eng"),
    ]
    permission_level = PermissionLevel.AUTO
    category = "ocr"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        lang = kwargs.get("lang", "eng")
        if not path:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        if not os.path.isfile(path):
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"File not found: {path}")
        try:
            with open(path, "rb") as f:
                image_bytes = f.read()
            service = _get_service()
            result = await service.ocr(image_bytes, provider_name="tesseract")
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"text": result.text, "confidence": result.confidence, "path": path, "lang": lang, "char_count": len(result.text)},
                summary=f"OCR: {len(result.text)} chars (confidence: {result.confidence:.1%})",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── ocr_screenshot ──────────────────────────────────

class OCRScreenshotTool(BaseTool):
    name = "ocr_screenshot"
    description = "Take a screenshot of the primary monitor and extract text."
    parameters = [
        ToolParameter("lang", "Tesseract language code", required=False, default="eng"),
    ]
    permission_level = PermissionLevel.AUTO
    category = "ocr"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        lang = kwargs.get("lang", "eng")
        try:
            from dash_backend.desktop.screen_stream import get_screen_streamer
            streamer = get_screen_streamer()
            frame = await streamer.capture_frame()
            if not frame or not frame.get("data"):
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Failed to capture screenshot")
            image_bytes = base64.b64decode(frame["data"])
            service = _get_service()
            result = await service.ocr(image_bytes, provider_name="tesseract")
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={
                    "text": result.text, "confidence": result.confidence,
                    "monitor": frame.get("monitor", 0),
                    "resolution": f"{frame.get('width', 0)}x{frame.get('height', 0)}",
                    "char_count": len(result.text),
                },
                summary=f"Screenshot OCR: {len(result.text)} chars (confidence: {result.confidence:.1%})",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── ocr_monitor ─────────────────────────────────────

class OCRMonitorTool(BaseTool):
    name = "ocr_monitor"
    description = "Capture a specific monitor and extract text from it."
    parameters = [
        ToolParameter("monitor_id", "Monitor index (1-based). 0 = all monitors.", type="integer", required=False, default=0),
        ToolParameter("lang", "Tesseract language code", required=False, default="eng"),
    ]
    permission_level = PermissionLevel.AUTO
    category = "ocr"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        monitor_id = int(kwargs.get("monitor_id", 0))
        lang = kwargs.get("lang", "eng")
        try:
            from dash_backend.desktop.screen_stream import get_screen_streamer
            streamer = get_screen_streamer()
            streamer.set_monitor(monitor_id)
            frame = await streamer.capture_frame()
            if not frame or not frame.get("data"):
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Failed to capture monitor {monitor_id}")
            image_bytes = base64.b64decode(frame["data"])
            service = _get_service()
            result = await service.ocr(image_bytes, provider_name="tesseract")
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={
                    "text": result.text, "confidence": result.confidence,
                    "monitor_id": monitor_id,
                    "resolution": f"{frame.get('width', 0)}x{frame.get('height', 0)}",
                    "char_count": len(result.text),
                },
                summary=f"Monitor {monitor_id} OCR: {len(result.text)} chars (confidence: {result.confidence:.1%})",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── ocr_clipboard_image ─────────────────────────────

class OCRClipboardImageTool(BaseTool):
    name = "ocr_clipboard_image"
    description = "Extract text from an image stored in the system clipboard."
    parameters = [
        ToolParameter("lang", "Tesseract language code", required=False, default="eng"),
    ]
    permission_level = PermissionLevel.AUTO
    category = "ocr"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        lang = kwargs.get("lang", "eng")
        try:
            import sys as _sys
            if not _sys.platform.startswith("win"):
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.OpenClipboard(None)
            handle = user32.GetClipboardData(2)  # CF_BITMAP
            if not handle:
                user32.CloseClipboard()
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS,
                                  output={"text": "", "note": "No image in clipboard"},
                                  summary="No image found in clipboard")
            # Use Pillow to read from clipboard directly
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            user32.CloseClipboard()
            if img is None:
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS,
                                  output={"text": "", "note": "No image in clipboard"},
                                  summary="No image found in clipboard")
            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()
            service = _get_service()
            result = await service.ocr(image_bytes, provider_name="tesseract")
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"text": result.text, "confidence": result.confidence, "char_count": len(result.text)},
                summary=f"Clipboard image OCR: {len(result.text)} chars (confidence: {result.confidence:.1%})",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))

