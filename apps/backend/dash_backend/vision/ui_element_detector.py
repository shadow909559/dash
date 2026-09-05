"""UI Element Detector - Detect windows, buttons, errors in screenshots."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UIElementDetector:
    async def detect_buttons(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        return []
    
    async def detect_errors(self, image_bytes: bytes) -> List[Dict[str, str]]:
        try:
            from dash_backend.llm.service import collect_streamed_response, build_chat_messages
            import base64
            b64 = base64.b64encode(image_bytes).decode()
            
            messages = build_chat_messages(
                system_prompt="Analyze this screenshot for any error messages, warnings, or dialogs. Return JSON array with 'type', 'message', 'severity'.",
                user_message="Detect any errors or warnings in this screenshot. JSON only.",
            )
            
            text = await collect_streamed_response(messages)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return []
        except Exception:
            return []
    
    async def detect_windows(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        return []


_ui_element_detector: Optional[UIElementDetector] = None


def get_ui_element_detector() -> UIElementDetector:
    global _ui_element_detector
    if _ui_element_detector is None:
        _ui_element_detector = UIElementDetector()
    return _ui_element_detector
