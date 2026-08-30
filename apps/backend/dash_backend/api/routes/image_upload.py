"""REST API routes for image upload with OCR and LLM analysis."""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/images", tags=["images"])


# ── Request / Response Models ────────────────────────────────


class ImageAnalysisResponse(BaseModel):
    status: str = "ok"
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ImageUploadResponse(BaseModel):
    status: str = "ok"
    image_id: str = ""
    filename: str = ""
    size_bytes: int = 0
    analysis: ImageAnalysisResponse | None = None


# ── Endpoints ────────────────────────────────────────────────


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    analyze: bool = True,
    ocr: bool = True,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImageUploadResponse:
    """Upload an image and optionally perform OCR and LLM analysis."""
    try:
        # Read image data
        image_bytes = await file.read()
        size_bytes = len(image_bytes)
        
        # Generate image ID
        import uuid
        image_id = str(uuid.uuid4())
        
        response = ImageUploadResponse(
            status="ok",
            image_id=image_id,
            filename=file.filename or "unknown",
            size_bytes=size_bytes,
        )
        
        if analyze and ocr:
            # Perform OCR using existing OCR tools
            try:
                from dash_backend.vision.service import VisionService, get_vision_registry
                from dash_backend.vision.tesseract_provider import TesseractOCRProvider
                
                # Register Tesseract provider
                registry = get_vision_registry()
                registry.register_ocr("tesseract", TesseractOCRProvider())
                
                vision_service = VisionService()
                ocr_result = await vision_service.ocr(image_bytes, provider_name="tesseract")
                
                analysis = ImageAnalysisResponse(
                    status="ok",
                    ocr_text=ocr_result.text,
                    ocr_confidence=ocr_result.confidence,
                    summary=f"OCR extracted {len(ocr_result.text)} characters with {ocr_result.confidence:.1%} confidence",
                    details={"char_count": len(ocr_result.text)},
                )
                response.analysis = analysis
                
                logger.info("Image OCR completed: %s chars, %.1f%% confidence", 
                           len(ocr_result.text), ocr_result.confidence * 100)
                
            except Exception as exc:
                logger.exception("OCR failed for uploaded image")
                response.analysis = ImageAnalysisResponse(
                    status="error",
                    summary="OCR analysis failed",
                    details={"error": str(exc)},
                )
        
        return response
        
    except Exception as exc:
        logger.exception("Image upload failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze", response_model=ImageAnalysisResponse)
async def analyze_image(
    image_base64: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImageAnalysisResponse:
    """Analyze a base64-encoded image with OCR."""
    try:
        # Decode base64
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image data")
        
        # Perform OCR
        from dash_backend.vision.service import VisionService, get_vision_registry
        from dash_backend.vision.tesseract_provider import TesseractOCRProvider
        
        registry = get_vision_registry()
        registry.register_ocr("tesseract", TesseractOCRProvider())
        
        vision_service = VisionService()
        ocr_result = await vision_service.ocr(image_bytes, provider_name="tesseract")
        
        return ImageAnalysisResponse(
            status="ok",
            ocr_text=ocr_result.text,
            ocr_confidence=ocr_result.confidence,
            summary=f"OCR extracted {len(ocr_result.text)} characters with {ocr_result.confidence:.1%} confidence",
            details={"char_count": len(ocr_result.text)},
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Image analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/screenshot", response_model=ImageAnalysisResponse)
async def capture_and_analyze_screenshot(
    monitor_id: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImageAnalysisResponse:
    """Capture a screenshot and perform OCR analysis."""
    try:
        from dash_backend.desktop.screen_stream import get_screen_streamer
        
        streamer = get_screen_streamer()
        if monitor_id > 0:
            streamer.set_monitor(monitor_id)
        
        frame = await streamer.capture_frame()
        if not frame or not frame.get("data"):
            raise HTTPException(status_code=500, detail="Failed to capture screenshot")
        
        image_bytes = base64.b64decode(frame["data"])
        
        # Perform OCR
        from dash_backend.vision.service import VisionService, get_vision_registry
        from dash_backend.vision.tesseract_provider import TesseractOCRProvider
        
        registry = get_vision_registry()
        registry.register_ocr("tesseract", TesseractOCRProvider())
        
        vision_service = VisionService()
        ocr_result = await vision_service.ocr(image_bytes, provider_name="tesseract")
        
        return ImageAnalysisResponse(
            status="ok",
            ocr_text=ocr_result.text,
            ocr_confidence=ocr_result.confidence,
            summary=f"Screenshot OCR: {len(ocr_result.text)} characters with {ocr_result.confidence:.1%} confidence",
            details={
                "char_count": len(ocr_result.text),
                "monitor": frame.get("monitor", 0),
                "resolution": f"{frame.get('width', 0)}x{frame.get('height', 0)}",
            },
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Screenshot capture and analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
