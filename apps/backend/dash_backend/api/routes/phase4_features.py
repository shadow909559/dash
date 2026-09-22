"""API routes for Phase 4 features: advanced learning, project management, desktop advanced."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from dash_backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/phase4", tags=["Features V4"])


# ── Mutation models (#144): the desktop app mutates these resources ────


class ActionItemCreate(BaseModel):
    title: str
    description: str = ""
    assignee: str = ""
    priority: str = "medium"
    due_date: str = ""
    source: str = "manual"
    tags: list[str] = []


class ActionItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None


class ReminderCreate(BaseModel):
    title: str
    remind_at: str
    context: str = ""
    recurring: str = ""


class ReminderComplete(BaseModel):
    note: str = ""


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


# Mutations (#144): the ActionItemsPage creates, completes, edits and
# deletes items — the router previously exposed GET only, so every one of
# those buttons could never succeed.


@router.post("/action-items", status_code=201)
async def create_action_item(payload: ActionItemCreate, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import action_items

    result = action_items.create(
        title=payload.title,
        assignee=payload.assignee,
        due_date=payload.due_date,
        source=payload.source,
        priority=payload.priority,
        description=payload.description,
        tags=payload.tags,
    )
    return result.get("item", {})


@router.get("/action-items/{item_id}")
async def get_action_item(item_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import action_items

    for item in action_items.get_all():
        if item["id"] == item_id:
            return item
    raise HTTPException(status_code=404, detail="action item not found")


@router.put("/action-items/{item_id}")
async def update_action_item(
    item_id: str, payload: ActionItemUpdate, _user=Depends(get_current_user)
):
    from dash_backend.services.project_management import action_items

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    result = action_items.update(item_id, **updates)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="action item not found")
    return {"ok": True}


@router.post("/action-items/{item_id}/complete")
async def complete_action_item(item_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import action_items

    result = action_items.complete(item_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="action item not found")
    return {"ok": True}


@router.delete("/action-items/{item_id}", status_code=204)
async def delete_action_item(item_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import action_items

    before = len(action_items.get_all())
    action_items.delete(item_id)
    if len(action_items.get_all()) == before:
        raise HTTPException(status_code=404, detail="action item not found")


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


# Mutations (#144): the RemindersPage fires, dismisses, edits and deletes.


@router.post("/reminders", status_code=201)
async def create_reminder(payload: ReminderCreate, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import reminder_service

    result = reminder_service.create(
        title=payload.title,
        remind_at=payload.remind_at,
        context=payload.context,
        recurring=payload.recurring,
    )
    return result.get("reminder", {})


@router.post("/reminders/{reminder_id}/complete")
async def complete_reminder(reminder_id: str, _user=Depends(get_current_user)):
    """The UI's 'complete' button — mapped to the service's fire/dismiss."""
    from dash_backend.services.project_management import reminder_service

    result = reminder_service.dismiss(reminder_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="reminder not found")
    return {"ok": True}


@router.post("/reminders/{reminder_id}/fire")
async def fire_reminder(reminder_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import reminder_service

    result = reminder_service.fire(reminder_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="reminder not found")
    return {"ok": True}


@router.delete("/reminders/{reminder_id}", status_code=204)
async def delete_reminder(reminder_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import reminder_service

    before = len(reminder_service.get_all())
    reminder_service.delete(reminder_id)
    if len(reminder_service.get_all()) == before:
        raise HTTPException(status_code=404, detail="reminder not found")


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
    # One real store for the page: tab screenshots from the browser service
    # (populated by POST /screenshots/capture), not the separate desktop
    # capture registry — split stores made page captures vanish on reload.
    from dash_backend.services.browser_automation import get_browser_service

    return {"captures": get_browser_service().get_screenshots()}


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


# ── Sprint mutations (#144): SprintBoardPage creates sprints and mutates
#    sprint items; the router previously exposed GET only.


class SprintCreate(BaseModel):
    name: str
    start_date: str
    end_date: str
    goal: str = ""


class SprintItemCreate(BaseModel):
    title: str
    description: str = ""
    story_points: int = 1
    assignee: str = ""
    sprint_id: str = ""


class SprintItemUpdate(BaseModel):
    status: str


@router.post("/sprints", status_code=201)
async def create_sprint(payload: SprintCreate, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import sprint_service

    result = sprint_service.create_sprint(payload.name, payload.start_date, payload.end_date, payload.goal)
    return result.get("sprint", {})


@router.get("/sprint-items")
async def get_sprint_items(sprint_id: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import sprint_service

    tasks = sprint_service.get_tasks(sprint_id) if sprint_id else sprint_service.get_all_tasks()
    return {"items": tasks}


@router.post("/sprint-items", status_code=201)
async def create_sprint_item(payload: SprintItemCreate, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import sprint_service

    if not payload.sprint_id:
        raise HTTPException(status_code=422, detail="sprint_id is required")
    result = sprint_service.add_task(
        payload.sprint_id, payload.title,
        points=payload.story_points, description=payload.description,
        assignee=payload.assignee,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="sprint not found")
    return result.get("task", {})


@router.patch("/sprint-items/{item_id}")
async def update_sprint_item(item_id: str, payload: SprintItemUpdate, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import sprint_service

    # The item id is unique inside its sprint; find the owning sprint.
    for sprint in sprint_service.get_sprints():
        result = sprint_service.update_task(sprint["id"], item_id, payload.status)
        if result.get("ok"):
            return {"ok": True}
    raise HTTPException(status_code=404, detail="sprint item not found")


@router.delete("/sprint-items/{item_id}", status_code=204)
async def delete_sprint_item(item_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import sprint_service

    for sprint in sprint_service.get_sprints():
        result = sprint_service.delete_task(sprint["id"], item_id)
        if result.get("ok"):
            return
    raise HTTPException(status_code=404, detail="sprint item not found")


# ── Clipboard history mutations (#144): ClipboardHistoryPage pins and
#    deletes individual clips.


@router.post("/clipboard/{clip_id}/pin")
async def pin_clipboard_clip(clip_id: str, payload: dict | None = None, _user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import clipboard_history

    pinned = bool(payload.get("pinned", True)) if isinstance(payload, dict) else True
    result = clipboard_history.set_pin(clip_id, pinned) if not pinned else clipboard_history.pin(clip_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="clip not found")
    return {"ok": True}


@router.delete("/clipboard/{clip_id}", status_code=204)
async def delete_clipboard_clip(clip_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import clipboard_history

    clipboard_history.delete(clip_id)



# ── Web-page screenshot capture (#144): ScreenshotCapturePage captures a
#    URL and deletes captures. The browser service records real tab state;
#    the visual PNG itself is rendered by the desktop shell.

# capture uses the body so the page can send {"url", "full_page"}


@router.post("/screenshots/capture", status_code=201)
async def capture_screenshot(payload: dict, _user=Depends(get_current_user)):
    from dash_backend.services.browser_automation import get_browser_service

    url = str(payload.get("url", "")).strip()
    if not url:
        raise HTTPException(status_code=422, detail="url is required")
    # Record a real tab visit, then a real screenshot entry bound to it.
    tab = get_browser_service().open_tab(url, title=url, active=True)
    entry = get_browser_service().take_screenshot(tab_id=tab.get("id"), full_page=bool(payload.get("full_page")))
    return {
        "id": entry["id"],
        "url": url,
        "title": url,
        "width": 1280,
        "height": 720,
        "created_at": entry["timestamp"],
        "full_page": entry["full_page"],
        "tab_id": tab.get("id"),
    }


@router.delete("/screenshots/{screenshot_id}", status_code=204)
async def delete_screenshot(screenshot_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.browser_automation import get_browser_service

    result = get_browser_service().delete_screenshot(screenshot_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="screenshot not found")


# ── Debug console clear (#144): DebugConsolePage has a Clear button.


@router.delete("/debug/logs", status_code=204)
async def clear_debug_logs(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_advanced import debug_console

    debug_console.clear()


# ── Updates (#144): UpdateCheckerPage checks version, installs and reads
#    the changelog. The backend reports its real version; installing
#    downloads are owned by the desktop shell's auto-updater, so the route
#    reports honestly that no packaged update is managed server-side.


class UpdateCheck(BaseModel):
    version: str
    release_date: str = ""
    release_notes: str = ""
    download_url: str = ""
    size: str = ""


_DASH_VERSION = "1.0.0"


@router.get("/updates/check", response_model=UpdateCheck)
async def updates_check(_user=Depends(get_current_user)):
    return UpdateCheck(version=_DASH_VERSION, release_date="2026-09-12")


@router.post("/updates/install")
async def updates_install(_user=Depends(get_current_user)):
    return {
        "ok": False,
        "reason": "server_side_install_unavailable",
        "detail": "Updates are installed by the desktop shell's auto-updater, not the backend.",
    }


@router.get("/updates/changelog")
async def updates_changelog(_user=Depends(get_current_user)):
    return [
        {
            "version": _DASH_VERSION,
            "date": "2026-09-12",
            "changes": [
                "Assistant vertical: clients, meetings, approvals, requirements",
                "Voice loop with wake word, streaming TTS and live amplitude",
                "Route parity between desktop app and backend enforced in CI",
            ],
        }
    ]


# ── Manual time entry (#144): TimeTrackingPage logs manual durations.


class TimeManualEntry(BaseModel):
    task: str
    project: str = ""
    duration_seconds: int = 0


@router.post("/time/manual", status_code=201)
async def add_manual_time(payload: TimeManualEntry, _user=Depends(get_current_user)):
    from dash_backend.services.project_management import time_tracking

    result = time_tracking.add_manual(
        payload.task, project=payload.project, duration_seconds=payload.duration_seconds
    )
    return result.get("entry", result)


# ── Terminal exec (#144): TerminalPage runs shell commands. Real exec with
#    the same rails as the code-execution tool: hard timeout, output caps,
#    and a deny list for catastrophically destructive commands. Auth is
#    enforced by the router dependency (device-token bearer).


import asyncio

EXEC_TIMEOUT = 30
MAX_OUTPUT_CHARS = 100_000

_DENY_PATTERNS = (
    r"rm\s+-rf\s+/(?:\s|$)", r"format\b.*:", r"del\s+/[fsq].*C:\\",
    r"rd\s+/s", r"shutdown\b", r"diskpart\b", r"mkfs\b", r":(){.*};:",
)


class TerminalExec(BaseModel):
    command: str
    shell: str = "cmd"


@router.post("/terminal/exec")
async def terminal_exec(payload: TerminalExec, _user=Depends(get_current_user)):
    import re as _re

    command = payload.command.strip()
    if not command:
        raise HTTPException(status_code=422, detail="command is required")
    for pattern in _DENY_PATTERNS:
        if _re.search(pattern, command, _re.IGNORECASE):
            raise HTTPException(status_code=403, detail=f"command denied by safety policy: {pattern}")

    shell = "powershell" if payload.shell.lower().startswith("power") else "cmd"
    if shell == "powershell":
        argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        argv = ["cmd", "/c", command]

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=EXEC_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504, detail=f"command timed out after {EXEC_TIMEOUT}s")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"shell unavailable: {exc}") from exc

    return {
        "stdout": stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS],
        "stderr": stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS],
        "exit_code": proc.returncode or 0,
    }
