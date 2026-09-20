"""Proactive event loop (spec #33/#34/#146).

A bounded background loop — NOT an uncontrolled infinite loop:

    tick → aggregate (reuse AttentionEngine) → meetings starting soon
    → deadlines approaching → deduplicate → notify/push → persist? (the
    underlying records are already persistent; the loop only reads)

Config-gated by ``DASH_ASSISTANT_PROACTIVE`` (default on) with a fixed,
configurable interval. Every notification is derived from real store
state; the dedupe cache is day-keyed and in-memory, so after a backend
restart a still-relevant alert may re-notify once — honest and bounded,
never a silent drop. Delivery order: WS push (every tick's digest) and
desktop notification (only urgent/critical items), both best-effort.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import time
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_INTERVAL_S = 300.0  # 5 minutes — meetings get >=1 warning tick
MEETING_LEAD_MIN = 15       # warn when a meeting starts within N minutes

_state_path: Path | None = None
_task: asyncio.Task | None = None
_seen: dict[str, str] = {}  # dedupe key -> YYYY-MM-DD it was last sent on


def _load_seen() -> None:
    """Dedupe keys persist across restarts so a restart does not re-spam."""
    global _seen
    if _state_path is not None:
        try:
            _seen = json.loads(_state_path.read_text(encoding="utf-8"))
        except Exception:
            _seen = {}


def _save_seen() -> None:
    if _state_path is not None:
        try:
            _state_path.write_text(
                json.dumps(_seen, default=str), encoding="utf-8")
        except Exception:
            logger.exception("proactive: failed to persist dedupe state")


def configure_state_dir(base_dir: Path | None) -> None:
    global _state_path
    _state_path = (base_dir / "proactive_state.json") if base_dir else None
    _load_seen()


def _today() -> str:
    return _dt.date.today().isoformat()


def _local_hour() -> int:
    """Local hour source for scheduled digests — a function so tests can
    inject the time deterministically (no immutable-type patching)."""
    return _dt.datetime.now().hour


def _fresh(key: str) -> bool:
    """True when this key has not been sent today."""
    if _seen.get(key) == _today():
        return False
    _seen[key] = _today()
    return True


def _already_sent(key: str) -> bool:
    """Read-only _fresh: has this key been sent today? (No mutation —
    lets the tick skip failures the immediate path already reported
    without consuming a key it might legitimately need later.)"""
    return _seen.get(key) == _today()

# ── Immediate task-event intake (decisions.md #124) ─────────────────


def _publish_task_topic(task: Any) -> None:
    """Mirror the task event onto the EventBus for observability.

    Copy of the presence engine's loop-tolerant publish (loop.create_task
    when running, run_coroutine_threadsafe on the captured loop, skip
    when neither — ws push already delivered to live clients).
    """
    try:
        import asyncio

        from dash_backend.events.event_bus import Event, EventPriority, get_event_bus
        topic = f"task.orchestrator.{task.get('status', 'updated')}"
        data = {"task_id": task.get("id"), "goal": task.get("goal"),
                "status": task.get("status")}
        bus = get_event_bus()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.create_task(bus.publish(Event(
                topic=topic, source="task_orchestrator",
                priority=EventPriority.HIGH, data=data)))
        else:
            captured = getattr(bus, "_loop", None)
            if captured is not None and not captured.is_closed():
                asyncio.run_coroutine_threadsafe(
                    bus.publish(Event(
                        topic=topic, source="task_orchestrator",
                        priority=EventPriority.HIGH, data=data)), captured)
    except Exception:
        logger.exception("proactive: task topic publish failed")


async def notify_task_event(
    task: dict[str, Any],
    event: str,
    store=None,
    audit=None,
    notifier=None,
) -> dict[str, Any] | None:
    """Route a task-orchestrator event to the owner immediately.

    The orchestrator's ``_push`` is ws-only and best-effort — with no ws
    client connected, a task failure previously vanished until the next
    5-minute digest tick (which groups only ≥2 failures). This path gives
    failure / recovery / waiting-confirmation events an immediate owner
    contact routed through the ONE shared urgency policy (#119): ws push
    always; desktop and phone per the urgency floor and quiet hours, with
    day-dedupe so the digest grouping cannot double-notify the same
    failure. Everything is best-effort: an owner-contact failure must
    never break task execution.
    """
    if event not in ("failed", "recovery", "waiting_confirmation"):
        return None
    status = str(task.get("status") or "")
    goal = str(task.get("goal") or "")[:80]
    task_id = str(task.get("id") or "")

    # Dedupe against the digest's grouped-failures item: if the immediate
    # path already reported this task's failure today, the 5-minute tick
    # (which keys on the failure COUNT, so it cannot key by task) skips
    # grouping it again — one honest notification per failure per day.
    if event == "failed":
        if not _fresh(f"task_failed_owner:{task_id}"):
            return None
    elif event == "recovery":
        # Retries are progress, not news — only the FIRST recovery push
        # per task per day reaches the owner.
        if not _fresh(f"task_recovery:{task_id}"):
            return None

    item: dict[str, Any] = {
        "kind": f"task_{event}",
        "task_id": task_id,
        "text": f"Task '{goal}' {event.replace('_', ' ')}.",
        "urgency": "urgent",
    }
    if event == "waiting_confirmation":
        item["urgency"] = "critical"
        item["text"] = (
            f"Task '{goal}' is waiting for your confirmation before a "
            f"high-risk step.")

    _publish_task_topic(task)

    try:
        from dash_backend.assistant.push import push_assistant_event
        push_assistant_event(None, {"type": "proactive.digest",
                                    "items": [item], "immediate": True})
    except Exception:
        logger.exception("proactive: task-event ws push failed")

    channels: list[str] = []
    try:
        if store is None:
            from dash_backend.assistant.crm_store import get_crm_store
            store = get_crm_store()
        from dash_backend.assistant.urgency import route_contact
        channels = list(route_contact(
            item["urgency"],
            prefs=store.get_preferences(),
            local_hour=_local_hour,
        ).channels)
        item["channels"] = channels
    except Exception:
        logger.exception("proactive: task-event routing failed")

    if "phone" in channels:
        try:
            from dash_backend.assistant.mobile_bridge import push_proactive_item
            push_proactive_item(item, store)
        except Exception:
            logger.exception("proactive: task-event mobile push failed")

    if "desktop" in channels and notifier is not None:
        try:
            await notifier.show(title="DASH needs you",
                                message=item["text"][:180])
        except Exception:
            logger.exception("proactive: task-event desktop notify failed")

    if "voice" in channels:
        # The last #119 channel with a real consumer (decisions.md #126):
        # speak the announcement through the always-listening loop's full
        # pipeline (streamed TTS, presence, barge-in). The loop honestly
        # refuses when not listening (disabled/mic down) — then the
        # desktop/phone/ws surfaces carry the item alone.
        try:
            from dash_backend.voice_system.always_listening import get_wake_loop
            item["voice_result"] = await get_wake_loop().announce(
                item["text"], source="proactive")
        except Exception:
            logger.exception("proactive: task-event voice announce failed")

    if audit is not None:
        try:
            audit.log(
                event_type="task_event_owner_contact",
                action=f"{event}:{task_id}",
                category="assistant",
                status="notified",
                details={"channels": channels, "urgency": item["urgency"]},
            )
        except Exception:
            logger.exception("proactive: task-event audit failed")

    return item


async def proactive_tick(store, audit=None, orchestrator=None,
                         notifier=None) -> dict[str, Any]:
    """One bounded pass. Returns the digest it decided to publish."""
    from dash_backend.assistant.push import push_assistant_event

    digest: dict[str, Any] = {"ts": time.time(), "items": []}
    if store is None:
        return digest
    # Owner preference gate (spec #107): proactive_enabled=False silences
    # the loop entirely — the owner's switch, checked every pass.
    try:
        if not store.get_preferences().get("proactive_enabled", True):
            return digest
    except Exception:
        logger.exception("proactive: preference read failed (continuing)")
    now = time.time()

    # 1. Meetings starting soon → PREPARE the briefing now (spec #21:
    # "DASH prepares" — prepare_briefing is deterministic and cheap, so it
    # runs here, not on request) and tell the owner it exists.
    for m in store.list_meetings():
        sched = m.get("scheduled_at")
        if not sched or m.get("status") in ("completed", "cancelled"):
            continue
        try:
            starts_in = (float(sched) - now) / 60.0
        except (TypeError, ValueError):
            continue
        if 0 < starts_in <= MEETING_LEAD_MIN:
            key = f"meeting:{m['id']}:{_today()}"
            if _fresh(key):
                briefing_ready = False
                try:
                    # prepare_briefing is a pure store read (no live-session
                    # state), so building the engine over THIS tick's store
                    # is correct even when the singleton binds elsewhere
                    # (tests, multi-state setups).
                    from dash_backend.assistant.meeting_engine import MeetingEngine
                    b = MeetingEngine(store=store).prepare_briefing(m["id"])
                    briefing_ready = b is not None
                except Exception:
                    logger.exception("proactive: pre-meeting briefing failed")
                item = {
                    "kind": "meeting_soon",
                    "text": (
                        f"Meeting '{m['title']}' starts in "
                        f"{max(1, round(starts_in))} min — "
                        + ("briefing prepared." if briefing_ready
                           else "briefing will be ready on request.")),
                    "meeting_id": m["id"],
                    "urgency": "important",
                }
                digest["items"].append(item)

    # 2. Action items due today / overdue → urgent (spec #36)
    for a in store.list_action_items(status="pending"):
        due = a.get("due")
        if not due:
            continue
        try:
            overdue = _dt.date.fromisoformat(str(due)[:10]) <= _dt.date.today()
        except ValueError:
            continue
        if overdue:
            key = f"action:{a['id']}:{_today()}"
            if _fresh(key):
                digest["items"].append({
                    "kind": "action_due",
                    "text": f"Action owed: {a['text'][:90]} (due {due})",
                    "urgency": "urgent",
                })

    # 3. Approvals pending too long (nudging the owner, not the client)
    for ap in store.list_approvals(status="pending"):
        age_h = (now - ap.get("requested_at", now)) / 3600.0
        if age_h >= 24:
            key = f"approval:{ap['id']}:{_today()}"
            if _fresh(key):
                digest["items"].append({
                    "kind": "approval_old",
                    "text": (f"Approval '{ap['description'][:70]}' pending "
                             f"{round(age_h)}h — approve or reject it."),
                    "urgency": "important",
                })

    # 4. Client follow-ups owed (spec #50): detect new ones, then surface
    # EVERY pending follow-up (day-deduped) until the owner resolves it.
    try:
        from dash_backend.assistant.followups import detect_follow_ups
        detect_follow_ups(store)
        for fu in store.list_follow_ups(status="pending"):
            key = f"followup:{fu['id']}:{_today()}"
            if not _fresh(key):
                continue
            client = store.get_client(fu["client_id"])
            digest["items"].append({
                "kind": "follow_up",
                "text": (f"{client['name'] if client else 'Client'}: "
                         f"{fu['reason'][:90]}"),
                "follow_up_id": fu["id"],
                "urgency": "important",
            })
    except Exception:
        logger.exception("proactive: follow-up detection failed")

    # 4b. Repeated failures grouped into ONE alert (spec #37): "failed
    # three times, stopped retrying" instead of a failure per attempt.
    # Failures the immediate path (#124) already reported individually are
    # excluded — one honest notification per failure per day, whichever
    # path fires first.
    try:
        if orchestrator is not None:
            failed = [t for t in orchestrator.list_tasks()
                      if t.get("status") == "failed"
                      and not _already_sent(f"task_failed_owner:{t.get('id')}")]
            if len(failed) >= 2:
                key = f"failures_grouped:{len(failed)}:{_today()}"
                if _fresh(key):
                    names = "; ".join(
                        (t.get("goal") or "")[:40] for t in failed[:3])
                    digest["items"].append({
                        "kind": "failures_grouped",
                        "text": (f"{len(failed)} task(s) failed and stopped "
                                 f"retrying: {names}"),
                        "count": len(failed),
                        "urgency": "urgent",
                    })
    except Exception:
        logger.exception("proactive: failure grouping failed")

    # 5. Scheduled owner digests (spec #145): morning briefing and
    # evening summary at the owner's configured working hours, day-deduped.
    try:
        prefs = store.get_preferences()
        wh = prefs.get("working_hours") or {}
        start_h = int(wh.get("start", 9))
        end_h = int(wh.get("end", 17))
        local_h = _local_hour()
        if local_h >= start_h and _fresh(f"briefing:{_today()}"):
            from dash_backend.assistant.control import daily_briefing
            brief = daily_briefing(store)
            digest["items"].append({
                "kind": "morning_briefing",
                "text": brief["text"][:400],
                "urgency": "normal",
            })
        if local_h >= end_h and _fresh(f"eod:{_today()}"):
            from dash_backend.assistant.control import end_of_day_summary
            eod = end_of_day_summary(store)
            digest["items"].append({
                "kind": "evening_summary",
                "text": eod["text"][:400],
                "urgency": "normal",
            })
    except Exception:
        logger.exception("proactive: scheduled digests failed")

    # 6. Retention auto-tick (spec #98/#99, decisions.md #103): once per
    # day when retention_days > 0 (0 = keep forever, never runs). Silent
    # when nothing expired — an informational item only when content was
    # actually pruned (never cry wolf, spec #34).
    try:
        rdays = int(store.get_preferences().get("retention_days", 0) or 0)
        if rdays > 0 and _fresh(f"retention:{_today()}"):
            ret = store.apply_retention(rdays)
            pruned = sorted(k for k, v in ret.get("pruned", {}).items() if v)
            if pruned:
                digest["items"].append({
                    "kind": "retention_pruned",
                    "text": (f"Retention ran ({rdays}d): pruned "
                             f"{', '.join(pruned)} beyond retention."),
                    "urgency": "low",
                })
    except Exception:
        logger.exception("proactive: retention tick failed")

    # Publish (Phase 4 routing, decisions.md #119): ws push always; each
    # item's channels come from ONE shared routing decision (urgency.py)
    # honoring the owner's urgency floor and quiet hours — critical
    # breaks through by design. This also fixes a real bug: the old
    # desktop check was ``urgency == "urgent"``, so a critical item
    # never produced a desktop notification.
    if digest["items"]:
        push_assistant_event(None, {"type": "proactive.digest", **digest})
        try:
            prefs = store.get_preferences()
        except Exception:
            prefs = {}
        try:
            from dash_backend.assistant.urgency import route_contact
            routes: dict[str, list[str]] = {}
            for item in digest["items"]:
                u = item["urgency"]
                if u not in routes:
                    routes[u] = route_contact(
                        u, prefs=prefs, local_hour=_local_hour).channels
                item["channels"] = list(routes[u])
        except Exception:
            logger.exception("proactive: channel routing failed")
        try:
            from dash_backend.assistant.mobile_bridge import push_proactive_item
            for item in digest["items"]:
                if "phone" in item.get("channels", ()):
                    push_proactive_item(item, store)
        except Exception:
            logger.exception("proactive: mobile push failed")
        desktop = [i for i in digest["items"]
                   if "desktop" in i.get("channels", ())]
        if desktop and notifier is not None:
            try:
                await notifier.show(
                    title="DASH needs you",
                    message=desktop[0]["text"][:180],
                )
            except Exception:
                logger.exception("proactive: desktop notification failed")
        if audit is not None:
            try:
                audit.log(
                    event_type="proactive_digest",
                    action=f"{len(digest['items'])} item(s)",
                    category="assistant",
                    status="notified",
                    details={"kinds": sorted({i['kind'] for i in digest['items']})},
                )
            except Exception:
                logger.exception("proactive: audit log failed")
        _save_seen()
    return digest


async def _loop(store, audit, orchestrator, notifier, interval_s: float) -> None:
    while True:
        try:
            await proactive_tick(store, audit=audit, orchestrator=orchestrator,
                                 notifier=notifier)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("proactive tick failed (continuing)")
        await asyncio.sleep(interval_s)


def start_proactive_loop(store, audit=None, orchestrator=None,
                         notifier=None) -> bool:
    """Start the background loop unless disabled by configuration.

    ``DASH_ASSISTANT_PROACTIVE=0`` disables. Returns whether it started.
    Non-critical by design: failures to start are logged, never raised.
    """
    global _task
    if os.getenv("DASH_ASSISTANT_PROACTIVE", "1").strip().lower() in (
            "0", "false", "no"):
        logger.info("proactive loop disabled by DASH_ASSISTANT_PROACTIVE")
        return False
    if _task is not None and not _task.done():
        return False
    interval = float(os.getenv("DASH_ASSISTANT_PROACTIVE_INTERVAL",
                               str(DEFAULT_INTERVAL_S)))
    _load_seen()
    _task = asyncio.create_task(
        _loop(store, audit, orchestrator, notifier, max(30.0, interval)))
    logger.info("proactive assistant loop started (interval %ss)", interval)
    return True


async def stop_proactive_loop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass
        _task = None
