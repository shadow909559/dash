"""Vision skill package: screenshot, OCR, UI detection helpers.

This package provides a VisionSkill service that exposes high-level vision
operations. Implementations can plug in Tesseract/OpenCV/vision models as
needed. By default the service uses safe no-op behaviors so the system remains
functional without heavy dependencies.
"""
from .service import VisionSkill

__all__ = ["VisionSkill"]
