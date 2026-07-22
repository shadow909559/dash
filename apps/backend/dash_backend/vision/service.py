"""Vision subsystem with provider abstraction.

Provides OCR, screenshot analysis, UI element detection, image understanding,
and document reading capabilities. All providers are abstract so Tesseract,
OpenCV, GPT-4V, or custom models can be plugged in without rewriting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# =========================================================================
# Data types
# =========================================================================


@dataclass
class OCRResult:
    text: str
    confidence: float = 1.0
    bounding_boxes: Optional[list[dict[str, float]]] = None


@dataclass
class UIDetectionResult:
    elements: list[dict[str, Any]]
    raw: Optional[dict[str, Any]] = None


@dataclass
class ImageUnderstandingResult:
    description: str
    objects: list[str] = None
    text_detected: bool = False
    raw: Optional[dict[str, Any]] = None


# =========================================================================
# Provider interfaces
# =========================================================================


@runtime_checkable
class OCRProvider(Protocol):
    name: str

    async def ocr(self, image_bytes: bytes) -> OCRResult:
        ...


@runtime_checkable
class ScreenshotProvider(Protocol):
    name: str

    async def capture(self) -> bytes:
        ...


@runtime_checkable
class UIElementDetectionProvider(Protocol):
    name: str

    async def detect_elements(self, image_bytes: bytes) -> UIDetectionResult:
        ...


@runtime_checkable
class ImageUnderstandingProvider(Protocol):
    name: str

    async def understand(self, image_bytes: bytes, prompt: Optional[str] = None) -> ImageUnderstandingResult:
        ...


# =========================================================================
# Default noop providers (safe fallbacks)
# =========================================================================


class NoopOCRProvider:
    name = "noop"

    async def ocr(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(text="[OCR not configured]")


class NoopScreenshotProvider:
    name = "noop"

    async def capture(self) -> bytes:
        raise NotImplementedError("Screenshot capture not configured")


class NoopUIDetectionProvider:
    name = "noop"

    async def detect_elements(self, image_bytes: bytes) -> UIDetectionResult:
        return UIDetectionResult(elements=[])


class NoopImageUnderstandingProvider:
    name = "noop"

    async def understand(self, image_bytes: bytes, prompt: Optional[str] = None) -> ImageUnderstandingResult:
        return ImageUnderstandingResult(
            description="[Image understanding not configured]",
            objects=[],
            text_detected=False,
        )


# =========================================================================
# Provider registry
# =========================================================================


class VisionProviderRegistry:
    """Registry for vision providers that allows plugging in different backends."""

    def __init__(self):
        self._ocr_providers: dict[str, OCRProvider] = {}
        self._screenshot_providers: dict[str, ScreenshotProvider] = {}
        self._ui_detection_providers: dict[str, UIElementDetectionProvider] = {}
        self._understanding_providers: dict[str, ImageUnderstandingProvider] = {}

        # Register noop defaults
        self.register_ocr("default", NoopOCRProvider())
        self.register_screenshot("default", NoopScreenshotProvider())
        self.register_ui_detection("default", NoopUIDetectionProvider())
        self.register_understanding("default", NoopImageUnderstandingProvider())

    def register_ocr(self, name: str, provider: OCRProvider):
        self._ocr_providers[name] = provider

    def register_screenshot(self, name: str, provider: ScreenshotProvider):
        self._screenshot_providers[name] = provider

    def register_ui_detection(self, name: str, provider: UIElementDetectionProvider):
        self._ui_detection_providers[name] = provider

    def register_understanding(self, name: str, provider: ImageUnderstandingProvider):
        self._understanding_providers[name] = provider

    def get_ocr(self, name: Optional[str] = None) -> OCRProvider:
        if name:
            return self._ocr_providers.get(name, self._ocr_providers.get("default"))
        return self._ocr_providers.get("default")

    def get_screenshot(self, name: Optional[str] = None) -> ScreenshotProvider:
        if name:
            return self._screenshot_providers.get(name, self._screenshot_providers.get("default"))
        return self._screenshot_providers.get("default")

    def get_ui_detection(self, name: Optional[str] = None) -> UIElementDetectionProvider:
        if name:
            return self._ui_detection_providers.get(name, self._ui_detection_providers.get("default"))
        return self._ui_detection_providers.get("default")

    def get_understanding(self, name: Optional[str] = None) -> ImageUnderstandingProvider:
        if name:
            return self._understanding_providers.get(name, self._understanding_providers.get("default"))
        return self._understanding_providers.get("default")


# Global registry singleton
_registry: Optional[VisionProviderRegistry] = None


def get_vision_registry() -> VisionProviderRegistry:
    global _registry
    if _registry is None:
        _registry = VisionProviderRegistry()
    return _registry


# =========================================================================
# Skill interface for registry
# =========================================================================


class VisionSkill:
    """Skill wrapper for Computer Vision that conforms to SkillInterface.

    Integrates with SkillRegistry and routes OCR, screenshot, UI detection,
    and image understanding intents through the VisionService.
    """

    name = "vision"

    def __init__(self, tool_manager: Any = None):
        self.service = VisionService()
        self.tool_manager = tool_manager

    async def handle(self, intent: str, args: dict, context: Any) -> dict:
        logger.info("VisionSkill handling %s %s", intent, args)
        image_bytes: bytes | None = args.get("image") or args.get("image_bytes")
        intent_lower = intent.lower()

        if "ocr" in intent_lower or "read" in intent_lower:
            if not image_bytes:
                return {"error": "no image provided"}
            result = await self.service.ocr(image_bytes)
            return {"text": result.text, "confidence": result.confidence}

        if "screenshot" in intent_lower:
            try:
                img = await self.service.capture_screenshot()
                ocr = await self.service.ocr(img)
                return {"screenshot_captured": True, "ocr_text": ocr.text}
            except NotImplementedError:
                return {"error": "Screenshot not configured"}

        if "ui" in intent_lower or "element" in intent_lower:
            if not image_bytes:
                return {"error": "no image provided"}
            result = await self.service.detect_ui_elements(image_bytes)
            return {"elements": result.elements}

        if "understand" in intent_lower or "describe" in intent_lower:
            if not image_bytes:
                return {"error": "no image provided"}
            result = await self.service.understand_image(image_bytes, prompt=args.get("prompt"))
            return {"description": result.description, "objects": result.objects or []}

        return {"error": "unknown_vision_intent"}


# =========================================================================
# High-level VisionService
# =========================================================================


class VisionService:
    """High-level vision service exposing OCR, screenshot, UI detection,
    image understanding, and document reading.

    Integrates with memory and planner for context-aware vision operations.
    """

    def __init__(self, registry: Optional[VisionProviderRegistry] = None):
        self.registry = registry or get_vision_registry()

    async def ocr(self, image_bytes: bytes, provider_name: Optional[str] = None) -> OCRResult:
        """Perform OCR on an image."""
        provider = self.registry.get_ocr(provider_name)
        return await provider.ocr(image_bytes)

    async def capture_screenshot(self, provider_name: Optional[str] = None) -> bytes:
        """Capture a screenshot."""
        provider = self.registry.get_screenshot(provider_name)
        return await provider.capture()

    async def detect_ui_elements(self, image_bytes: bytes, provider_name: Optional[str] = None) -> UIDetectionResult:
        """Detect UI elements in an image."""
        provider = self.registry.get_ui_detection(provider_name)
        return await provider.detect_elements(image_bytes)

    async def understand_image(self, image_bytes: bytes, prompt: Optional[str] = None, provider_name: Optional[str] = None) -> ImageUnderstandingResult:
        """Understand image content with optional prompt."""
        provider = self.registry.get_understanding(provider_name)
        return await provider.understand(image_bytes, prompt=prompt)

    async def read_document(self, image_bytes: bytes, provider_name: Optional[str] = None) -> OCRResult:
        """Read text from a document image (alias for OCR)."""
        return await self.ocr(image_bytes, provider_name=provider_name)

    async def analyze_screenshot(self, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """Capture and analyze a screenshot, returning combined results."""
        image_bytes = await self.capture_screenshot(provider_name=provider_name)
        ocr_result = await self.ocr(image_bytes, provider_name=provider_name)
        ui_result = await self.detect_ui_elements(image_bytes, provider_name=provider_name)
        understanding = await self.understand_image(image_bytes, provider_name=provider_name)
        return {
            "ocr_text": ocr_result.text,
            "ui_elements": ui_result.elements,
            "description": understanding.description,
            "objects_detected": understanding.objects,
        }
