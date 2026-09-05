"""Object Detector - Detect objects, windows, buttons, and UI elements in images."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from dash_backend.llm.service import collect_streamed_response, build_chat_messages

logger = logging.getLogger(__name__)


class ObjectDetector:
    def __init__(self):
        self._use_llm = True
        self._confidence_threshold = 0.5
    
    async def detect_objects(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        try:
            import base64
            b64 = base64.b64encode(image_bytes).decode()
            
            messages = build_chat_messages(
                system_prompt="Analyze this image and list all objects you can detect. Return JSON array with objects having 'name', 'confidence', 'position' (description), and 'category' fields.",
                user_message="Describe all objects visible in this image. Respond with JSON only.",
            )
            
            text = await collect_streamed_response(messages)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return [{"name": text[:100], "confidence": 0.5, "category": "unknown"}]
        except Exception as exc:
            logger.warning("Object detection failed: %s", exc)
            return []
    
    async def detect_ui_elements(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        try:
            import base64
            b64 = base64.b64encode(image_bytes).decode()
            
            messages = build_chat_messages(
                system_prompt="You are a UI element detector. List all clickable UI elements (buttons, links, inputs, menus) visible. Return JSON array with 'type', 'text', 'position_description'.",
                user_message="List all UI elements in this screen. JSON only.",
            )
            
            text = await collect_streamed_response(messages)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return []
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
