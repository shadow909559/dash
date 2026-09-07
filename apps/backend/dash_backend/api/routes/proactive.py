"""DASH Proactive Intelligence REST API (DASH 2.0, sections 5-7).

- GET  /proactive/suggestions  -> ranked suggestions (threshold/cooldown gated)
- POST /proactive/ack          -> client confirms a suggestion was shown
- GET  /proactive/config       -> current gating config
- POST /proactive/config       -> update enabled/quiet hours/cooldown/threshold
- GET  /proactive/history      -> recently shown suggestions
- GET  /proactive/briefing     -> daily briefing (section 6)
- GET  /proactive/summary      -> end-of-day summary (section 7)

All routes require the local device token, like every other internal API.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger
from dash_backend.proactive.briefing import build_briefing, build_end_of_day
from dash_backend.proactive.engine import DEFAULT_CONFIG, get_proactive_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/proactive", tags=["proactive"])


class AckRequest(BaseModel):
    signal_id: str = Field(..., description="Stable signal id from a suggestion (e.g. uncommitted_work)")
    title: Optional[str] = None


class ConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    quiet_hours_start: Optional[int] = Field(None, ge=0, le=23)
    quiet_hours_end: Optional[int] = Field(None, ge=0, le=23)
    cooldown_minutes: Optional[int] = Field(None, ge=1, le=24 * 60)
    importance_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)


@router.get("/suggestions")
async def get_suggestions(
    limit: int = Query(5, ge=1, le=20),
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    engine = get_proactive_engine()
    suggestions = await engine.evaluate(session=session, user_id=user_id, limit=limit)
    return {"count": len(suggestions), "suggestions": suggestions}


@router.post("/ack")
async def acknowledge_suggestion(
    payload: AckRequest,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    engine = get_proactive_engine()
    engine.record_shown(payload.signal_id, payload.title or "")
    return {"ok": True, "signal_id": payload.signal_id}


@router.get("/config")
async def get_config(
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    engine = get_proactive_engine()
    cfg = await engine.load_config(session, user_id)
    return {"config": cfg}


@router.post("/config")
async def update_config(
    payload: ConfigUpdate,
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    engine = get_proactive_engine()
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    cfg = await engine.save_config(session, user_id, updates)
    return {"ok": True, "config": cfg}


@router.get("/history")
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    return {"history": get_proactive_engine().history(limit=limit)}


@router.get("/briefing")
async def daily_briefing(
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    return await build_briefing(session=session, user_id=user_id)


@router.get("/summary")
async def end_of_day_summary(
    store: bool = Query(True, description="Store the summary to long-term memory"),
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    return await build_end_of_day(session=session, user_id=user_id, store_memory=store)