from __future__ import annotations

from typing import Dict, Any, Optional
from dataclasses import dataclass

from dash_backend.logging_config import get_logger
from dash_backend.tools.tool_manager import get_tool_manager

logger = get_logger(__name__)


class VisionSkill:
    name = "vision"

    def __init__(self, tool_manager: Optional[Any] = None):
        self.tool_manager = tool_manager or get_tool_manager()

    async def handle(self, intent: str, args: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Handle vision tasks: screenshot, OCR, detect UI elements.

        Default implementation uses available tools where possible (screenshot)
        or returns placeholders.
        """
        logger.info("VisionSkill handling %s %s", intent, args)
        if "screenshot" in intent or intent.startswith("screenshot"):
            # If a screenshot tool exists, call it; otherwise return an error
            return await self.tool_manager.execute("take_screenshot", {})
        if "ocr" in intent or "read" in intent:
            # expect image bytes in args['image'] or call screenshot first
            image = args.get("image")
            if not image:
                res = await self.tool_manager.execute("take_screenshot", {})
                # tool_manager.execute returns dict/result depending on implementation
                if isinstance(res, dict) and res.get("status") == "ok":
                    image = res.get("result")
                else:
                    # allow raw bytes returned by some tools
                    image = res
            # Try to use pytesseract if available
            try:
                from PIL import Image
                import io
                import pytesseract

                if isinstance(image, dict) and "image_bytes" in image:
                    img_bytes = image["image_bytes"]
                elif isinstance(image, (bytes, bytearray)):
                    img_bytes = bytes(image)
                else:
                    img_bytes = None

                if img_bytes:
                    img = Image.open(io.BytesIO(img_bytes))
                    text = pytesseract.image_to_string(img)
                    return {"text": text, "image_present": True}
            except Exception:
                # OCR libs not present or failed — fall through to placeholder
                pass

            # fallback placeholder
            return {"text": "[ocr result placeholder]", "image_present": bool(image)}
        return {"error": "unknown_vision_intent"}
