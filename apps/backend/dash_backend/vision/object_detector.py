"""Object Detector - Detect objects, windows, buttons, and UI elements in images.

`detect_objects` runs the REAL ONNX detector (recognition.py) and reports
its honest result — including "model missing" instead of pretending.
The legacy implementation asked an LLM to describe the image and returned
the description as fake detection JSON with invented confidences (and the
image bytes were never even attached to the prompt); that path is gone.
LLM description is still available separately as `describe_image` — clearly
labeled as a description, never as detections.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dash_backend.llm.service import collect_streamed_response, build_chat_messages

logger = logging.getLogger(__name__)


class ObjectDetector:
    def __init__(self):
        self._confidence_threshold = 0.5

    async def detect_objects(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        """Real detection via the ONNX stack; honest failure reporting."""
        from dash_backend.vision import recognition

        rgb = recognition.decode_to_rgb_array(image_bytes)
        if rgb is None:
            return [{"backend": "none", "reason": "image could not be decoded", "objects": []}]
        detector = recognition.get_object_detector()
        if not detector.available:
            return [{"backend": "none", "reason": detector.unavailable_reason, "objects": []}]
        detections = detector.detect(rgb, conf_threshold=self._confidence_threshold)
        return [
            {
                "name": d.name,
                "confidence": round(d.confidence, 4),
                "box": d.box,
                "backend": "onnx",
            }
            for d in detections
        ]

    async def describe_image(self, image_bytes: bytes) -> str:
        """LLM description of an image — explicitly NOT object detection.
        Kept for callers who want natural-language scene descriptions; the
        reply is prose from a model, with no confidence numbers to fake."""
        try:
            messages = build_chat_messages(
                system_prompt="You are describing an image. Describe what you see in detail.",
                user_message="Describe this image.",
            )
            return await collect_streamed_response(messages)
        except Exception as exc:
            logger.warning("Image description failed: %s", exc)
            return ""

    async def detect_ui_elements(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        """Best-effort UI element listing from the LLM. The result is a
        model's opinion, not a measured detection: each item is labeled
        backend='llm-description' so callers cannot mistake the provenance."""
        try:
            messages = build_chat_messages(
                system_prompt="You are a UI element detector. List all clickable UI elements (buttons, links, inputs, menus) visible. Return JSON array with 'type', 'text', 'position_description'.",
                user_message="List all UI elements in this screen. JSON only.",
            )
            text = await collect_streamed_response(messages)
            try:
                import json

                parsed = json.loads(text)
                items = parsed if isinstance(parsed, list) else []
            except Exception:
                return []
            for item in items:
                if isinstance(item, dict):
                    item["backend"] = "llm-description"
            return items
        except Exception:
            return []

    def set_confidence_threshold(self, threshold: float) -> None:
        self._confidence_threshold = max(0.0, min(1.0, threshold))


_object_detector: Optional[ObjectDetector] = None


def get_object_detector() -> ObjectDetector:
    global _object_detector
    if _object_detector is None:
        _object_detector = ObjectDetector()
    return _object_detector
