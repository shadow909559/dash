"""API routes for Phase 4 features: advanced learning, project management, desktop advanced."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from dash_backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/phase4", tags=["Features V4"])


# ── Code Understanding ─────────────────────────────────────────────────────

@router.get("/code/analyses")
async def get_code_analyses(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import code_understanding
    return {"analyses": code_understanding.get_analyses()}


# ── NL to SQL ──────────────────────────────────────────────────────────────

@router.get("/nl-sql/schemas")
async def get_nl_sql_schemas(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import nl_to_sql
    return nl_to_sql.get_schemas()

@router.get("/nl-sql/queries")
async def get_nl_sql_queries(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import nl_to_sql
    return {"queries": nl_to_sql.get_queries()}


# ── Federated Learning ─────────────────────────────────────────────────────

@router.get("/federated/insights")
async def get_federated_insights(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import federated_learning
    return federated_learning.get_insights()

@router.get("/federated/patterns")
async def get_federated_patterns(type: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import federated_learning
    return {"patterns": federated_learning.get_patterns(type)}


# ── Curriculum Learning ────────────────────────────────────────────────────

@router.get("/curriculum")
async def get_curricula(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import curriculum_learning
    return {"curricula": curriculum_learning.get_curricula()}


# ── Multi-Modal ────────────────────────────────────────────────────────────

@router.get("/multi-modal/processed")
async def get_multi_modal(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import multi_modal
    return {"processed": multi_modal.get_processed()}


# ── Reasoning Engine ───────────────────────────────────────────────────────

@router.get("/reasoning/chains")
async def get_reasoning_chains(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import reasoning_engine
    return {"chains": reasoning_engine.get_chains()}


# ── Causal Inference ───────────────────────────────────────────────────────

@router.get("/causal/relationships")
async def get_causal_relationships(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_learning import causal_inference
    return {"relationships": causal_inference.get_all()}


# ── Meeting Notes ──────────────────────────────────────────────────────────

@router.get("/meetings/notes")
async def get_meeting_notes(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import meeting_notes
    return {"notes": meeting_notes.get_all()}

@router.get("/meetings/search")
async def search_meetings(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.project_management import meeting_notes
    return {"results": meeting_notes.search(q)}


# ── Action Items ───────────────────────────────────────────────────────────

@router.get("/action-items")
async def get_action_items(status: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import action_items
    return {"items": action_items.get_all(status)}

@router.get("/action-items/pending")
async def get_pending_actions(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import action_items
    return {"items": action_items.get_pending()}

@router.get("/action-items/overdue")
async def get_overdue_actions(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import action_items
    return {"items": action_items.get_overdue()}


# ── Time Tracking ──────────────────────────────────────────────────────────

@router.get("/time/active")
async def get_active_timer(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import time_tracking
    return {"active": time_tracking.get_active()}

@router.get("/time/entries")
async def get_time_entries(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import time_tracking
    return {"entries": time_tracking.get_entries()}

@router.get("/time/summary")
async def get_time_summary(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import time_tracking
    return time_tracking.get_summary()


# ── Sprints ────────────────────────────────────────────────────────────────

@router.get("/sprints")
async def get_sprints(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import sprint_service
    return {"sprints": sprint_service.get_sprints()}

@router.get("/sprints/velocity")
async def get_velocity(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import sprint_service
    return {"velocity": sprint_service.get_velocity()}


# ── Reminders ──────────────────────────────────────────────────────────────

@router.get("/reminders")
async def get_reminders(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import reminder_service
    return {"reminders": reminder_service.get_all()}

@router.get("/reminders/pending")
async def get_pending_reminders(_user=Depends(get_current_user)):
    from dash_backend.services.project_management import reminder_service
    return {"reminders": reminder_service.get_pending()}


# ── Clipboard History ──────────────────────────────────────────────────────

@router.get("/clipboard/history")
async def get_clipboard_history(limit: int = 50, _user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import clipboard_history
    return {"history": clipboard_history.get_history(limit)}

@router.get("/clipboard/search")
async def search_clipboard(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import clipboard_history
    return {"results": clipboard_history.search(q)}


# ── Screenshot Capture ─────────────────────────────────────────────────────

@router.get("/screenshots")
async def get_screenshots(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import screenshot_capture
    return {"captures": screenshot_capture.get_captures()}


# ── File Browser ───────────────────────────────────────────────────────────

@router.get("/files/bookmarks")
async def get_file_bookmarks(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import file_browser
    return {"bookmarks": file_browser.get_bookmarks()}

@router.get("/files/recent")
async def get_recent_files(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import file_browser
    return {"recent": file_browser.get_recent()}


# ── Session Replay ─────────────────────────────────────────────────────────

@router.get("/sessions/recordings")
async def get_session_recordings(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import session_replay
    return {"recordings": session_replay.get_recordings()}


# ── Backup/Restore ─────────────────────────────────────────────────────────

@router.get("/backups")
async def get_backups(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import backup_restore
    return {"backups": backup_restore.get_backups()}

@router.get("/backups/stats")
async def get_backup_stats(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import backup_restore
    return backup_restore.get_stats()


# ── Debug Console ──────────────────────────────────────────────────────────

@router.get("/debug/logs")
async def get_debug_logs(level: Optional[str] = None, source: Optional[str] = None, limit: int = 100, _user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import debug_console
    return {"logs": debug_console.get_logs(level, source, limit=limit)}

@router.get("/debug/stats")
async def get_debug_stats(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import debug_console
    return debug_console.get_stats()
