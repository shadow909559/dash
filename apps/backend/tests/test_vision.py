"""Vision subsystem tests."""

from __future__ import annotations

import pytest
from dash_backend.vision.service import (
    VisionProviderRegistry,
    VisionService,
    NoopOCRProvider,
    OCRResult,
    UIDetectionResult,
    ImageUnderstandingResult,
)


class TestVisionRegistry:
    def test_registry_has_defaults(self):
        reg = VisionProviderRegistry()
        assert reg.get_ocr() is not None
        assert reg.get_screenshot() is not None
        assert reg.get_ui_detection() is not None
        assert reg.get_understanding() is not None

    def test_register_custom_ocr(self):
        reg = VisionProviderRegistry()
        provider = NoopOCRProvider()
        reg.register_ocr("custom", provider)
        assert reg.get_ocr("custom") is provider

    def test_get_nonexistent_falls_back_to_default(self):
        reg = VisionProviderRegistry()
        ocr = reg.get_ocr("nonexistent")
        assert ocr.name == "noop"


class TestVisionService:
    @pytest.mark.asyncio
    async def test_ocr_returns_noop_result(self):
        svc = VisionService()
        result = await svc.ocr(b"fake_image")
        assert isinstance(result, OCRResult)
        assert "not configured" in result.text

    @pytest.mark.asyncio
    async def test_detect_ui_elements_returns_empty(self):
        svc = VisionService()
        result = await svc.detect_ui_elements(b"fake_image")
        assert isinstance(result, UIDetectionResult)
        assert result.elements == []

    @pytest.mark.asyncio
    async def test_understand_image_returns_noop(self):
        svc = VisionService()
        result = await svc.understand_image(b"fake_image")
        assert isinstance(result, ImageUnderstandingResult)
        assert "not configured" in result.description

    @pytest.mark.asyncio
    async def test_capture_screenshot_raises_not_implemented(self):
        svc = VisionService()
        with pytest.raises(NotImplementedError):
            await svc.capture_screenshot()

