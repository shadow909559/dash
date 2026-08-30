"""Health check endpoint."""

from datetime import UTC, datetime
import time
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from dash_backend import __version__
from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.config import get_settings
from dash_backend.services.ai.provider_health_monitor import get_ai_provider_health_monitor
from dash_backend.services.supabase import get_supabase_service

router = APIRouter()

# Server start time for uptime calculation
_start_time = time.time()


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str = Field(examples=["ok"])
    service: str
    version: str
    environment: str
    uptime: float
    timestamp: datetime


class AIProviderHealthResponse(BaseModel):
    """AI Provider health status response."""
    healthy: bool
    last_check: float
    provider: str
    configured_model: Optional[str]
    model_available: bool
    installed_models: List[str]
    error: Optional[str]
    latency_ms: Optional[float]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status - lightweight check that doesn't depend on external services."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.env,
        uptime=time.time() - _start_time,
        timestamp=datetime.now(UTC),
    )


@router.get("/api/v1/health", response_model=HealthResponse)
async def health_check_v1() -> HealthResponse:
    """Return service health status - lightweight check that doesn't depend on external services."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.env,
        uptime=time.time() - _start_time,
        timestamp=datetime.now(UTC),
    )


@router.get("/health/ai-provider", response_model=AIProviderHealthResponse)
async def ai_provider_health_check(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Return current AI provider health status."""
    monitor = get_ai_provider_health_monitor()
    return monitor.current_status.to_dict()


@router.post("/health/ai-provider/force-check", response_model=AIProviderHealthResponse)
async def force_ai_provider_check(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Force an immediate health check and return the result."""
    monitor = get_ai_provider_health_monitor()
    return await monitor.force_check()


@router.get("/health/supabase")
async def supabase_health_check(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Return optional Supabase connectivity; never exposes configuration secrets."""
    return await get_supabase_service().check_connectivity()


@router.get("/health/diagnostic")
async def diagnostic_check(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Complete diagnostic of the DASH chat pipeline.
    
    Tests each component in the request path:
    - Backend health
    - Ollama connectivity
    - Configured model availability
    - Test chat generation
    """
    diagnostic = {
        "backend": {"status": "unknown"},
        "ollama": {"status": "unknown"},
        "model": {"status": "unknown"},
        "chat": {"status": "unknown"},
        "overall": "unknown"
    }
    
    # 1. Backend health
    try:
        settings = get_settings()
        diagnostic["backend"] = {
            "status": "ok",
            "service": settings.app_name,
            "version": __version__,
        }
    except Exception as exc:
        diagnostic["backend"] = {
            "status": "error",
            "error": str(exc)
        }
    
    # 2. Ollama connectivity
    try:
        from dash_backend.llm.service import check_provider_health
        ollama_health = await check_provider_health()
        diagnostic["ollama"] = {
            "status": "ok" if ollama_health["healthy"] else "error",
            "healthy": ollama_health["healthy"],
            "configured_model": ollama_health["configured_model"],
            "model_available": ollama_health["model_available"],
            "installed_models": ollama_health["installed_models"],
            "error": ollama_health["error"],
            "latency_ms": ollama_health["latency_ms"],
        }
    except Exception as exc:
        diagnostic["ollama"] = {
            "status": "error",
            "error": str(exc)
        }
    
    # 3. Model verification
    try:
        if diagnostic["ollama"].get("model_available"):
            diagnostic["model"] = {
                "status": "ok",
                "configured": diagnostic["ollama"]["configured_model"],
                "available": True
            }
        else:
            diagnostic["model"] = {
                "status": "error",
                "configured": diagnostic["ollama"]["configured_model"],
                "available": False,
                "error": "Configured model not available"
            }
    except Exception as exc:
        diagnostic["model"] = {
            "status": "error",
            "error": str(exc)
        }
    
    # 4. Test chat generation
    try:
        from dash_backend.llm.service import collect_streamed_response
        test_messages = [
            {"role": "system", "content": "You are a test assistant. Respond with exactly: DASH_TEST_OK"},
            {"role": "user", "content": "Test"}
        ]
        model_to_use = diagnostic["ollama"].get("configured_model")
        test_response = await collect_streamed_response(test_messages, model=model_to_use)
        
        if "DASH_TEST_OK" in test_response:
            diagnostic["chat"] = {
                "status": "ok",
                "response_received": True,
                "test_response": test_response
            }
        else:
            diagnostic["chat"] = {
                "status": "error",
                "response_received": True,
                "test_response": test_response,
                "error": "Response did not contain expected test string"
            }
    except Exception as exc:
        diagnostic["chat"] = {
            "status": "error",
            "error": str(exc)
        }
    
    # Overall status
    all_ok = all(
        d.get("status") == "ok" 
        for d in [diagnostic["backend"], diagnostic["ollama"], diagnostic["model"], diagnostic["chat"]]
    )
    diagnostic["overall"] = "ok" if all_ok else "error"
    
    return diagnostic
