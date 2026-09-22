"""Composite desktop-command decomposition (backend-only fix).

Root cause being fixed (live-probed over the real WebSocket): the user's
message

    "set up a meeting reminder for 5 mins and after the time is up remind me
     and open brave then zoom and then start a meeting and then join the meeting"

was matched by the greedy clipboard-write regex in command_interceptor.py,
which consumed "set " as its verb and truncated the tail. The interceptor
then executed a clipboard copy of the mangled text — a wrong, silently-
succeeding fallback for a multi-step task.

The fix has two halves:

1.  command_interceptor's clipboard-write pattern is tightened so it only
    matches when the message is actually a clipboard command ("copy X to
    clipboard" / "clipboard: X" / a quoted payload). A bare "set up …"
    sentence no longer matches anything in the interceptor, so it falls
    through to this module instead of being eaten.

2.  This module decomposes the composite sentence into ordered steps and
    executes each step against the REAL backend capabilities that already
    exist:

    - "set up a reminder for N <unit> … remind me" → ReminderService.create
      (real store) + a fire task that shows the desktop toast and pushes to
      the live ws session when time is up.
    - "open X" / "launch X" → the real app launcher (registry discovery +
      common-exe table), and the launch is VERIFIED: the process must
      actually appear, otherwise the step reports failure honestly.
    - "start a meeting" / "join the meeting" → the meeting-tracking engine
      tracks meetings that already exist; it cannot drive Zoom's interactive
      login UI, so these steps report exactly what is (not) possible and
      what the user must do — never a fake success.

Every step's result is returned so the user sees a per-step honest report.
No step is ever routed to a clipboard write.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# ── Detection ──────────────────────────────────────────────────────

_ACTION_VERBS = (
    "open ", "launch ", "start ", "run ", "remind", "set a reminder",
    "set up a reminder", "create a reminder", "join ", "close ", "type ",
    "press ", "take a screenshot", "copy ", "paste", "mute", "unmute",
)

_SEQUENCERS = re.compile(
    r"\b(then|after that|after (?:the )?time is up|afterwards|and then|next)\b",
    re.I,
)

_DELAY_RE = re.compile(
    r"\b(?:in|for|after)\s+(?P<n>\d+)\s*"
    r"(?P<unit>seconds?|secs?|minutes?|mins?|hours?|hrs?)\b",
    re.I,
)


def is_composite_task(message: str) -> bool:
    """True when the message contains multiple actions / sequenced actions.

    Conservative on purpose: only claims a message when it really looks
    multi-step, so single desktop commands keep their fast path.
    """
    text = (message or "").strip().lower()
    if not text:
        return False
    verb_hits = sum(1 for v in _ACTION_VERBS if v in text)
    has_sequencer = bool(_SEQUENCERS.search(text))
    return (verb_hits >= 2 and has_sequencer) or (verb_hits >= 3)


# ── Step splitting (verb-carrying) ─────────────────────────────────

_STEP_SPLIT_RE = re.compile(
    r"\b(?:then|after that|afterwards|and then|next)\b|"
    r"\band after the time is up\b|"
    r"\bafter the time is up\b|"
    r"\band then\b|"
    r"\b,\s*and\b|"
    r"\band\s+(?=(?:open|launch|start|run|join|close|remind|set|create|take|press|type)\b)",
    re.I,
)

# Fragments that only contain the tail of a bigger action and must be
# merged back into the previous step ("… open brave" + "zoom").
_MERGE_INTO_PREVIOUS_RE = re.compile(
    r"^(?:the\s+)?(brave|zoom|chrome|edge|firefox|teams|notepad|calculator|"
    r"explorer|word|excel|outlook|spotify|vscode|code|terminal)\s*$",
    re.I,
)

_REMIND_TAIL_RE = re.compile(r"^remind me\b", re.I)


def _split_steps(message: str) -> list[str]:
    """Split a composite sentence into ordered steps.

    - "open brave then zoom" → ["open brave", "zoom"] with "open" carried
      into the verb-less fragment ("open zoom" — same verb, next object).
    - "remind me" after a reminder step is folded into that reminder step
      (it is the reminder's firing instruction, not a second action).
    """
    raw = [p.strip(" ,.") for p in _STEP_SPLIT_RE.split(message) if p and p.strip(" ,.")]
    steps: list[str] = []
    for frag in raw:
        # "remind me" right after the reminder step is that reminder's
        # firing instruction, not a second action — fold it in.
        if steps and _REMIND_TAIL_RE.match(frag) and "reminder" in steps[-1].lower():
            steps[-1] = f"{steps[-1]} — and {frag}"
            continue
        # A bare app name ("zoom" after "open brave") carries the previous
        # open-verb and starts its own step.
        if steps and _MERGE_INTO_PREVIOUS_RE.match(frag):
            m = re.match(r"^(open|launch|start|run)\s+", steps[-1], re.I)
            verb = m.group(1) if m else "open"
            steps.append(f"{verb} {frag}")
            continue
        steps.append(frag)
    return steps


# ── Executors (real backend capabilities) ──────────────────────────

_UNIT_SECONDS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
}


def _parse_delay_seconds(text: str) -> tuple[int, str] | None:
    m = _DELAY_RE.search(text)
    if not m:
        return None
    n = int(m.group("n"))
    unit = m.group("unit").lower()
    return n * _UNIT_SECONDS[unit], f"{n} {unit}"


def _verify_process_running(name: str, timeout_s: float = 6.0) -> tuple[bool, str]:
    """Poll tasklist until a process for `name` appears.

    Matching is precise: the exe basename must equal ``name`` (Zoom.exe) or
    be a dotted child of it — ``zoom`` must NOT match
    ``PowerToys.ZoomIt.exe``, which the naive substring check did (found
    live: zoom "already running" while only ZoomIt was up).
    """
    import subprocess
    import time

    needle = name.lower().strip()

    def _matches(img: str) -> bool:
        base = img.lower()
        if base.endswith(".exe"):
            base = base[:-4]
        return base == needle or base.endswith("." + needle)

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            out = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=8,
            ).stdout
            for line in out.splitlines():
                if not line.strip():
                    continue
                img = line.split('","')[0].strip('"')
                if _matches(img):
                    return True, img
        except Exception:
            logger.exception("process verification failed (assuming not running)")
            return False, ""
        time.sleep(0.5)
    return False, ""


# Apps whose launcher spawns a browser process under a different name.
_PROCESS_ALIASES = {
    "brave": ["brave"],
    "zoom": ["zoom"],
    "chrome": ["chrome"],
    "edge": ["msedge"],
    "firefox": ["firefox"],
}


async def _exec_open(step: str) -> dict[str, Any]:
    m = re.search(r"\b(?:open|launch|start|run)\s+(?:the\s+)?(?P<app>[a-z0-9 +\-]+)",
                  step, re.I)
    if not m:
        return {"step": step, "action": "open", "ok": False,
                "detail": f"no application name found in '{step}'"}
    app = m.group("app").strip()
    try:
        from dash_backend.services.command_interceptor import _execute_open
        result = await _execute_open(app)
        if "error" in result:
            return {"step": step, "action": "open", "app": app, "ok": False,
                    "detail": result.get("summary", "launch failed")}
        # Verify the process actually exists — "start zoom" via shell can
        # silently do nothing if the exe is gone.
        needles = _PROCESS_ALIASES.get(app.lower(), [app.lower()])
        ok, exe = False, ""
        for n in needles:
            ok, exe = await asyncio.get_running_loop().run_in_executor(
                None, lambda n=n: _verify_process_running(n, 4.0))
            if ok:
                break
        if ok:
            return {"step": step, "action": "open", "app": app, "ok": True,
                    "detail": f"{result.get('summary')} — {exe} is running"}
        return {"step": step, "action": "open", "app": app, "ok": False,
                "detail": (f"{result.get('summary')}, but no {app} process "
                           f"appeared — the app may not be installed")}
    except Exception as exc:
        logger.exception("composite open step failed")
        return {"step": step, "action": "open", "app": app, "ok": False,
                "detail": str(exc)}


def _wait_process(name: str) -> str:
    ok, exe = _verify_process_running(name, 4.0)
    return exe if ok else ""


_ZOOM_UNAVAILABLE = (
    "Zoom is not installed on this machine, so DASH cannot start or join the "
    "meeting from here. Install Zoom, then ask again — the open step will "
    "launch it. Starting/joining beyond launching also needs your Zoom "
    "login and a click on Join, which DASH must not simulate."
)


async def _exec_meeting(step: str) -> dict[str, Any]:
    """start/join a meeting: honest about what DASH can and cannot do.

    The only meeting platform DASH can launch today is Zoom; anything
    beyond launching (login, clicking Join) belongs to the user.
    """
    try:
        from dash_backend.services.command_interceptor import _execute_open
        result = await _execute_open("zoom")
        ok = "error" not in result
        if ok:
            ok, exe = await asyncio.get_running_loop().run_in_executor(
                None, lambda: _verify_process_running("zoom", 10.0))
        if ok:
            return {"step": step, "action": "meeting", "ok": True,
                    "detail": (f"Zoom is running ({exe}). DASH launched it — "
                               "sign in / join from Zoom's window, DASH "
                               "cannot click through Zoom's login UI.")}
        return {"step": step, "action": "meeting", "ok": False,
                "detail": _ZOOM_UNAVAILABLE}
    except Exception as exc:
        return {"step": step, "action": "meeting", "ok": False,
                "detail": f"{_ZOOM_UNAVAILABLE} ({exc})"}


async def _sleep(seconds: float) -> None:
    """Sleep seam — tests monkeypatch this instead of global asyncio."""
    await asyncio.sleep(seconds)


async def _exec_reminder(step: str, notify: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
    delay = _parse_delay_seconds(step)
    if delay is None:
        return {"step": step, "action": "reminder", "ok": False,
                "detail": "could not parse a delay like 'for 5 mins' — nothing scheduled"}
    seconds, human = delay
    try:
        from dash_backend.services.project_management import reminder_service
        from dash_backend.services.notifications import NotificationService

        remind_at = (datetime.now() + timedelta(seconds=seconds)).isoformat()
        created = reminder_service.create(title="Meeting reminder",
                                          remind_at=remind_at,
                                          context="composite task")
        rid = created["reminder"]["id"]
        notifier = NotificationService()

        async def _fire() -> None:
            await _sleep(seconds)
            reminder_service.fire(rid)
            text = f"Reminder: your {human} reminder is up — opening Brave next was part of the task."
            try:
                await notifier.show(title="DASH reminder", message=text[:180], duration=10)
            except Exception:
                logger.exception("composite reminder: desktop toast failed")
            try:
                await notify(text)
            except Exception:
                logger.exception("composite reminder: ws notify failed")

        asyncio.get_running_loop().create_task(_fire())
        return {"step": step, "action": "reminder", "ok": True, "reminder_id": rid,
                "detail": f"reminder scheduled {human} from now (fires at {remind_at})"}
    except Exception as exc:
        logger.exception("composite reminder step failed")
        return {"step": step, "action": "reminder", "ok": False, "detail": str(exc)}


# ── Public entry point ─────────────────────────────────────────────

async def run_composite_task(
    message: str,
    notify: Callable[[str], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Decompose and execute a composite task; return an honest per-step report."""
    steps = _split_steps(message)
    if not steps:
        steps = [message.strip()]

    results: list[dict[str, Any]] = []

    async def _notify(text: str) -> None:
        if notify is not None:
            await notify(text)

    for step in steps:
        s = step.strip()
        sl = s.lower()
        if "reminder" in sl or sl.startswith("remind"):
            results.append(await _exec_reminder(s, _notify))
        elif re.match(r"^(?:open|launch|start|run|join)\b", sl):
            if "meeting" in sl:
                results.append(await _exec_meeting(s))
            else:
                results.append(await _exec_open(s))
        else:
            results.append(await _exec_open(s))

    fired = sum(1 for r in results if r.get("ok"))
    summary_lines = [f"{'OK' if r.get('ok') else 'FAILED'}: {r.get('detail', '')}"
                     for r in results]
    return {
        "action": "composite_task",
        "steps": results,
        "ok": any(r.get("ok") for r in results),
        "summary": (f"Composite task — {fired}/{len(results)} steps succeeded. "
                    + " | ".join(summary_lines)),
    }
