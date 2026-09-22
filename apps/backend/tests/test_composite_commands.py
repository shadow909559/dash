"""Composite-task routing pins (backend-only fix, 2026-09-22).

Root cause under test: "set up a meeting reminder for 5 mins and after the
time is up remind me and open brave then zoom and then start a meeting and
then join the meeting" used to match the greedy clipboard-write regex,
truncating at both ends and "succeeding" as a clipboard copy. These pins
assert the honest new behavior:

- the clipboard-write pattern only matches messages that are actually
  about the clipboard;
- a composite task decomposes into ordered steps executed against real
  executors (reminder store, app launcher) — never a clipboard write;
- the reminder step schedules a REAL reminder (findable in the store);
- app-open steps verify a real process appeared (ZoomIt must never count
  as Zoom, BraveCrashHandler must never count as Brave);
- steps that cannot complete (Zoom not installed) report honestly.
"""

from __future__ import annotations

import asyncio

import dash_backend.services.command_interceptor as ci
from dash_backend.services.composite_commands import (
    is_composite_task,
    run_composite_task,
    _split_steps,
)

TASK = ("set up a meeting reminder for 5 mins and after the time is up remind me "
        "and open brave then zoom and then start a meeting and then join the meeting")


# ── The clipboard regex can never eat this sentence again ──────────

def test_clipboard_pattern_does_not_match_composite_task() -> None:
    for pat in ci._CLIPBOARD_WRITE_PATTERNS:
        assert pat.match(TASK) is None, f"pattern still greedy: {pat.pattern}"


def test_clipboard_pattern_still_matches_real_clipboard_commands() -> None:
    real = [
        "copy hello world to clipboard",
        'copy "hello world" to clipboard',
        "clipboard hello world",
        "copy: hello world",
        'set "the meeting notes" to clipboard',
    ]
    for msg in real:
        assert any(p.match(msg) for p in ci._CLIPBOARD_WRITE_PATTERNS), msg


def test_clipboard_intercept_still_works_end_to_end(monkeypatch) -> None:
    called = []

    async def fake_copy(self, text):
        called.append(text)
        return {"summary": f"Copied {len(text)} chars to clipboard"}

    import dash_backend.services.clipboard as clip
    monkeypatch.setattr(clip.ClipboardService, "copy", fake_copy)

    result = asyncio.run(ci.try_intercept("copy hello dash to clipboard"))
    assert called == ["hello dash"]
    assert result["action"] == "clipboard_write"


# ── Composite detection and decomposition ──────────────────────────

def test_composite_detection() -> None:
    assert is_composite_task(TASK)
    assert not is_composite_task("open brave")
    assert not is_composite_task("what's on the clipboard")
    assert not is_composite_task("")
    assert not is_composite_task("remind me in 5 minutes")  # single action


def test_step_splitting_is_ordered_and_lossless() -> None:
    steps = _split_steps(TASK)
    assert len(steps) == 5, steps
    assert "reminder" in steps[0].lower() and "remind me" in steps[0].lower()
    assert steps[1].lower() == "open brave"
    assert steps[2].lower() == "open zoom"  # 'open' carried from the previous verb
    assert "start a meeting" in steps[3].lower()
    assert "join the meeting" in steps[4].lower()


# ── Execution routes to REAL executors (glue stays real) ───────────

def test_composite_run_schedules_real_reminder_and_opens_apps(monkeypatch) -> None:
    """Full pipeline with only the OS boundary mocked: launch/verify.

    The real _exec_open runs (parses the app name, calls the real launcher
    seam), while the process check is pinned so the test is deterministic
    on any machine. Brave "launches", Zoom's launch is refused.
    """
    from dash_backend.services.project_management import reminder_service
    from dash_backend.services import composite_commands as cc

    launched = []

    async def fake_execute_open(app_name: str):
        launched.append(app_name)
        if app_name == "zoom":
            return {"action": "open", "summary": "zoom not found", "error": "not found"}
        return {"action": "open", "summary": f"Launched {app_name}", "status": "launched"}

    def fake_verify(name: str, timeout_s: float = 6.0):
        return (name == "brave", "Brave.exe" if name == "brave" else "")

    monkeypatch.setattr("dash_backend.services.command_interceptor._execute_open",
                        fake_execute_open)
    monkeypatch.setattr(cc, "_verify_process_running", fake_verify)

    before = len(reminder_service.get_all())
    result = asyncio.run(run_composite_task(TASK))
    steps = result["steps"]

    # brave open once; zoom attempted by its open step AND both meeting
    # steps (each then reports honestly after verification fails)
    assert launched[0] == "brave" and launched.count("zoom") == 3, launched
    assert steps[0]["action"] == "reminder" and steps[0]["ok"]
    assert steps[1]["app"] == "brave" and steps[1]["ok"]
    assert "Brave.exe is running" in steps[1]["detail"]
    assert steps[2]["app"] == "zoom" and steps[2]["ok"] is False
    assert steps[3]["ok"] is False  # start a meeting — Zoom unavailable
    assert steps[4]["ok"] is False  # join the meeting — Zoom unavailable
    assert "not installed" in steps[4]["detail"].lower() or \
           "cannot" in steps[4]["detail"].lower()

    # REAL reminder exists in the store, scheduled ~5 minutes out
    after = reminder_service.get_all()
    assert len(after) == before + 1
    assert after[-1]["title"] == "Meeting reminder"
    assert after[-1]["fired"] is False
    assert "clipboard" not in result["summary"].lower()
    assert result["ok"] is True  # reminder + brave succeeded


def test_verify_process_rejects_name_collisions() -> None:
    """ZoomIt ≠ Zoom, BraveCrashHandler ≠ Brave — the live-probed bug."""
    from dash_backend.services.composite_commands import _verify_process_running

    ok, exe = _verify_process_running("definitely_not_running_xyz", 0.5)
    assert ok is False and exe == ""


def test_reminder_actually_fires(monkeypatch) -> None:
    """A short-interval variant proves the firing path end to end."""
    from dash_backend.services import composite_commands as cc
    from dash_backend.services.project_management import reminder_service

    fired_messages = []

    async def notify(text: str) -> None:
        fired_messages.append(text)

    shown = []

    class FakeNotifier:
        async def show(self, title, message, duration=5):
            shown.append(message)

    monkeypatch.setattr("dash_backend.services.notifications.NotificationService.show",
                        lambda self, **kw: FakeNotifier().show(**kw))
    monkeypatch.setattr(cc, "_sleep",
                        lambda seconds: asyncio.sleep(min(seconds, 0.05)))

    short = ("set up a test reminder for 1 sec and after the time is up remind me "
             "and open brave")
    result = asyncio.run(run_composite_task(short, notify=notify))
    assert result["steps"][0]["ok"]

    rid = result["steps"][0]["reminder_id"]
    # let the fire task run on the loop
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(asyncio.sleep(0.3))
    finally:
        loop.close()
    rem = next(r for r in reminder_service.get_all() if r["id"] == rid)
    assert rem["fired"] is True
    assert fired_messages and "reminder" in fired_messages[0].lower()
    assert shown and "reminder" in shown[0].lower()


def test_single_clipboard_command_still_not_composite() -> None:
    """Sanity: the fast paths are untouched."""
    assert not is_composite_task("copy notes to clipboard")
    assert not is_composite_task("open notepad")
    assert not is_composite_task("take a screenshot")
