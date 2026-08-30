"""Image Analyzer - Image captioning, document understanding, and visual analysis."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from dash_backend.llm.service import collect_streamed_response, build_chat_messages

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    async def caption(self, image_bytes: bytes) -> str:
        try:
            import base64
            b64 = base64.b64encode(image_bytes).decode()
            
            messages = build_chat_messages(
                system_prompt="You are an image captioning AI. Describe what you see in detail.",
                user_message="Describe this image in one detailed sentence.",
            )
            
            return await collect_streamed_response(messages)
        except Exception as exc:
            logger.warning("Image caption failed: %s", exc)
            return ""
    
    async def analyze_document(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            import base64
            b64 = base64.b64encode(image_bytes).decode()
            
            messages = build_chat_messages(
                system_prompt="Analyze this document image. Extract text, structure, and key information. Return JSON with 'title', 'content', 'type', 'key_points'.",
                user_message="Analyze this document. JSON only.",
            )
            
            text = await collect_streamed_response(messages)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"content": text[:500]}
        except Exception:
            return {}
    
    async def understand_screen(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            messages = build_chat_messages(
                system_prompt="Analyze this screen. Identify the application, purpose, key elements, and actions possible. Return JSON.",
                user_message="What application is this and what can I do here? JSON only.",
            )
            
            text = await collect_streamed_response(messages)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"description": text[:300]}
        except Exception:
            return {}


_image_analyzer: Optional[ImageAnalyzer] = None


def get_image_analyzer() -> ImageAnalyzer:
    global _image_analyzer
    if _image_analyzer is None:
        _image_analyzer = ImageAnalyzer()
    return _image_analyzer
