"""DASH monitoring & diagnostics REST API.

Exposes the health summary and developer-only detailed diagnostics, plus
automatic repair actions. Additive — the existing /health endpoint is untouched.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.logging_config import get_logger
from dash_backend.monitoring import get_diagnostics_service, get_repair_routine

logger = get_logger(__name__)

# Every monitor route requires the local device token. These endpoints expose
# internals (diagnostics) and can trigger actions (repairs, research).
router = APIRouter(
    prefix="/monitor", tags=["monitor"], dependencies=[Depends(get_current_user_id)]
)


class RepairRequest(BaseModel):
    action: str = Field(..., description="Repair action name (see /monitor/repairs)")
    run_all: bool = Field(False, description="Run all repair actions")


@router.post("/research")
async def monitor_research(
    query: str = Query(..., min_length=1),
    max_results: int = Query(8, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Run the existing web_search tool and return structured results."""
    try:
        from dash_backend.tools.base_tool import ToolContext
        from dash_backend.tools.web_tools import WebSearchTool

        tool = WebSearchTool()
        context = ToolContext(user_id=user_id)
        result = await tool.execute(context, query=query, max_results=max_results)
        output = result.output if isinstance(result.output, dict) else {"raw": result.output}
        return {
            "ok": result.status.value == "success" if hasattr(result.status, "value") else True,
            "query": query,
            "summary": result.summary,
            "error": result.error_message,
            "results": output.get("results") or [],
            "abstract": output.get("abstract") or "",
            "total_results": output.get("total_results") or 0,
        }
    except Exception as exc:
        logger.exception("Research failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health")
async def monitor_health() -> Dict[str, Any]:
    """Aggregated health summary across all DASH components."""
    service = get_diagnostics_service()
    return await service.summary()


@router.get("/diagnostics")
async def monitor_diagnostics(
    include_sensitive: bool = Query(False, description="Include sensitive details (developer only)"),
) -> Dict[str, Any]:
    """Detailed diagnostics. Developer-gated."""
    service = get_diagnostics_service()
    return await service.diagnostics(include_sensitive=include_sensitive)


@router.get("/repairs")
async def list_repairs() -> Dict[str, Any]:
    """List available automatic repair actions."""
    return get_repair_routine().list()


@router.post("/repairs/run")
async def run_repair(req: RepairRequest) -> Dict[str, Any]:
    """Run a repair action (or all)."""
    routine = get_repair_routine()
    if req.run_all:
        return await routine.run_all()
    return await routine.run(req.action)
