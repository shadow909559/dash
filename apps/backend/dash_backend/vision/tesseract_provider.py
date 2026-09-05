"""Tesseract OCR provider for the Dash vision system.

Configures pytesseract with the correct tesseract_cmd path
and implements the OCRProvider protocol from vision/service.py.
"""

from __future__ import annotations

import io
from typing import Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class TesseractOCRProvider:
    """OCR provider using Tesseract via pytesseract.

    Implements the OCRProvider protocol (duck-typing compatible with
    the VisionProviderRegistry). Sets tesseract_cmd to the user's
    Tesseract-OCR installation path automatically.

    Usage:
        provider = TesseractOCRProvider()
        result = await provider.ocr(image_bytes)
    """

    name = "tesseract"

    def __init__(self) -> None:
        self._imported = False
        self._pytesseract = None

    def _lazy_import(self) -> None:
        """Lazy-import pytesseract on first use.

        We do this so importing this module never raises ImportError;
        the error is deferred until the first ocr() call, which makes
        the provider safe to register even when pytesseract is absent.
        """
        if self._imported:
            return
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            self._pytesseract = pytesseract
            self._imported = True
            logger.info(
                "TesseractOCRProvider initialized. tesseract_cmd=%s",
                TESSERACT_CMD,
            )
        except ImportError as exc:
            logger.warning(
                "pytesseract not installed. OCR will raise ImportError. %s",
                exc,
            )
            self._pytesseract = None
            self._imported = True  # don't retry

    async def ocr(
        self,
        image_bytes: bytes,
        lang: Optional[str] = None,
        config: Optional[str] = None,
    ) -> "OCRResult":
        """Perform OCR on an image and return extracted text.

        Args:
            image_bytes: Raw image file bytes (PNG, JPEG, etc.).
            lang: Tesseract language code (e.g. 'eng', 'eng+fra').
                  Defaults to None (pytesseract default = 'eng').
            config: Additional Tesseract config string.

        Returns:
            OCRResult with extracted text and confidence.

        Raises:
            ImportError: If pytesseract is not installed.
            FileNotFoundError: If Tesseract executable is not found.
            RuntimeError: If OCR processing fails.
        """
        self._lazy_import()
        if self._pytesseract is None:
            from dash_backend.vision.service import OCRResult
            return OCRResult(
                text="[ERROR] pytesseract is not installed. Install with: pip install pytesseract",
                confidence=0.0,
            )

        try:
            from PIL import Image
            image = Image.open(io.BytesIO(image_bytes))

            ocr_kwargs = {}
            if lang:
                ocr_kwargs["lang"] = lang
            if config:
                ocr_kwargs["config"] = config

            if ocr_kwargs:
                text: str = self._pytesseract.image_to_string(image, **ocr_kwargs)
            else:
                text = self._pytesseract.image_to_string(image)

            # Get confidence data if possible
            try:
                if ocr_kwargs:
                    data = self._pytesseract.image_to_data(image, output_type=self._pytesseract.Output.DICT, **ocr_kwargs)
                else:
                    data = self._pytesseract.image_to_data(image, output_type=self._pytesseract.Output.DICT)
                confidences = [c for c in data.get("conf", []) if c != -1]
                avg_confidence = (
                    sum(confidences) / len(confidences) / 100.0
                    if confidences
                    else 0.5
                )
            except Exception:
                avg_confidence = 0.5

            from dash_backend.vision.service import OCRResult
            return OCRResult(
                text=text.strip(),
                confidence=round(avg_confidence, 4),
            )

        except FileNotFoundError as exc:
            logger.error("Tesseract binary not found at %s: %s", TESSERACT_CMD, exc)
            from dash_backend.vision.service import OCRResult
            return OCRResult(
                text=f"[ERROR] Tesseract binary not found: {exc}",
                confidence=0.0,
            )
        except Exception as exc:
            logger.exception("OCR processing failed")
            from dash_backend.vision.service import OCRResult
            return OCRResult(
                text=f"[OCR Error] {exc}",
                confidence=0.0,
            )


# Convenience alias matching the protocol name expected by VisionProviderRegistry
TesseractProvider = TesseractOCRProvider

