"""Vision subsystem: OCR, screenshot, UI detection, image understanding.

Provides a VisionService with provider abstraction. Plug in Tesseract, OpenCV,
GPT-4V, or custom models without rewriting core logic.
"""
from .service import VisionService, VisionSkill, VisionProviderRegistry, get_vision_registry
from . import tesseract_provider

__all__ = [
    "VisionService", "VisionSkill", "VisionProviderRegistry",
    "get_vision_registry", "tesseract_provider",
]
