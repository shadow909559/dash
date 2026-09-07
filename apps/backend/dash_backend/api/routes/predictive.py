"""DASH Predictive Problem Detection API (DASH Ultimate spec, Part 8).

- GET /predictive/risks  -> forward-looking risks with evidence + likelihood

Every risk is a prediction with evidence, an honest likelihood and a
suggested action — never a guaranteed fact. Requires the local device token,
like every other internal API.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger
from dash_backend.predictive.engine import get_predictive_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/predictive", tags=["predictive"])


@router.get("/risks")
async def get_risks(
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    engine = get_predictive_engine()
    return await engine.analyze(session=session, user_id=user_id)
