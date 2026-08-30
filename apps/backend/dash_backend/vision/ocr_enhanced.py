"""OCR Enhanced - Advanced OCR with language support and preprocessing."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OCREnhanced:
    def __init__(self):
        self._languages = ["eng"]
    
    async def extract_text(self, image_bytes: bytes, languages: Optional[List[str]] = None) -> str:
        try:
            import pytesseract
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
            lang = "+".join(languages or self._languages)
            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip()
        except Exception as exc:
            logger.warning("OCR failed: %s", exc)
            return ""
    
    async def extract_text_with_positions(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        try:
            import pytesseract
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            results = []
            for i in range(len(data["text"])):
                if data["text"][i].strip():
                    results.append({
                        "text": data["text"][i],
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i],
                        "confidence": data["conf"][i],
                    })
            return results
        except Exception as exc:
            logger.warning("OCR with positions failed: %s", exc)
            return []
    
    def set_languages(self, languages: List[str]) -> None:
        self._languages = languages


_ocr_enhanced: Optional[OCREnhanced] = None


def get_ocr_enhanced() -> OCREnhanced:
    global _ocr_enhanced
    if _ocr_enhanced is None:
        _ocr_enhanced = OCREnhanced()
    return _ocr_enhanced
