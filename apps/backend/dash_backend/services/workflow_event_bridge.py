"""Workflow event bridge (decisions.md #57).

Connects the DASH event bus to the workflow engine's event triggers, and
owns the REAL producers for the three topics the workflow templates ship
with — because a subscription with no publisher is a silent no-op, which
is exactly the fake wiring this project refuses:

- ``email.received`` — published by ExtendedEmailService._ingest when a
  genuinely new message is stored (IMAP fetch or .eml import).
- ``reminder.fired`` — published by ReminderService when a reminder's
  trigger time arrives.
- ``file.changed``  — published by the polling FileWatcher below. watchdog
  is not installed, so this is a stdlib mtime/size poll: honest about what
  it can miss (changes fully inside one poll window that restore the same
  mtime+size) in exchange for zero dependencies.

Delivery semantics: fire immediately on the bus delivery task (off the
event loop via a worker thread so delay nodes cannot stall it). No replay
after restart: events that happened while the backend was down are gone —
that is stated, not hidden.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# The topics the workflow engine can be triggered on. Producers elsewhere
# in the codebase publish these via schedule_event_publish() or the bridge.
EVENT_EMAIL_RECEIVED = "email.received"
EVENT_REMINDER_FIRED = "reminder.fired"
EVENT_FILE_CHANGED = "file.changed"
SUPPORTED_TOPICS = (EVENT_EMAIL_RECEIVED, EVENT_REMINDER_FIRED, EVENT_FILE_CHANGED)

# Wildcard topic groups. The bus supports single-level wildcards, so one
# subscription covers every sub-topic a producer group emits — e.g. the
# vision watcher publishes vision.person_seen / vision.unknown_person /
# vision.camera_unavailable / vision.watch_degraded / vision.watch_recovered
# (decisions.md #68), and any workflow may trigger on any of them.
# NOTE: only groups with NO exact-topic subscription here (reminder.fired is
# subscribed exactly below — the bus delivers to exact AND wildcard
# subscribers independently, so a reminder.* wildcard would double-fire it).
WILDCARD_TOPICS = (
    "vision.*",
    "guardian.*",
)

# File watcher: os.pathsep works on Windows (";") but people habitually type
# commas too — accept both.
_MAX_EVENTS_PER_SCAN = 32


def _watch_paths_from_env() -> list[Path]:
    raw = os.environ.get("DASH_WATCH_PATHS", "")
    paths: list[Path] = []
    for chunk in raw.replace(",", os.pathsep).split(os.pathsep):
        chunk = chunk.strip()
        if chunk:
            paths.append(Path(chunk).expanduser())
    return paths


def schedule_event_publish(topic: str, data: dict) -> None:
    """Publish a workflow event from sync code, best-effort.

    Producers (email ingest, reminder loop) may run with or without a
    running loop; when there is no loop the event is dropped with a debug
    log rather than silently queued forever. This helper never raises.
    """
    try:
        bridge = get_workflow_event_bridge()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("Event %s dropped: no running event loop", topic)
            return
        publisher = {
            EVENT_EMAIL_RECEIVED: bridge.notify_email_received,
            EVENT_REMINDER_FIRED: bridge.notify_reminder_fired,
            EVENT_FILE_CHANGED: bridge.notify_file_changed,
        }.get(topic)
        if publisher is None:
            return
        loop.create_task(publisher(dict(data)))
    except Exception:  # noqa: BLE001 — producers must never fail on notify
        logger.debug("Event %s publish failed", topic, exc_info=True)


class FileWatcher:
    """Stdlib polling watcher emitting file.changed events.

    Scans configured paths (files or directories, recursive) every
    poll_seconds, diffs mtime+size against the previous scan, and invokes
    the callback for each created/modified/deleted path. A single scan
    emits at most _MAX_EVENTS_PER_SCAN events so one bulk operation cannot
    stampede the workflow engine.
    """

    def __init__(self, callback: Callable[[dict], Any],
                 paths: Optional[list[Path]] = None,
                 poll_seconds: float = 2.0) -> None:
        self._callback = callback
        self._paths = list(paths or [])
        self._poll_seconds = max(0.5, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._snapshot: dict[str, tuple[float, int]] = {}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def paths(self) -> list[Path]:
        return list(self._paths)

    def start(self) -> None:
        if self.running:
            return
        if not self._paths:
            logger.info(
                "File watcher not started: no watch paths configured "
                "(set DASH_WATCH_PATHS to enable file.changed triggers)"
            )
            return
        existing = [p for p in self._paths if p.exists()]
        if not existing:
            logger.warning("File watcher paths do not exist: %s", self._paths)
        self._paths = existing or self._paths
        self._snapshot = self._scan()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="dash-file-watcher", daemon=True
        )
        self._thread.start()
        logger.info("File watcher started on %s (poll=%ss)", self._paths, self._poll_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._snapshot = {}

    def _scan(self) -> dict[str, tuple[float, int]]:
        snapshot: dict[str, tuple[float, int]] = {}
        for root in self._paths:
            try:
                candidates = [root] if root.is_file() else list(root.rglob("*"))
            except OSError:
                continue
            for f in candidates:
                if not f.is_file():
                    continue
                try:
                    st = f.stat()
                except OSError:
                    continue
                snapshot[str(f)] = (st.st_mtime, st.st_size)
        return snapshot

    def _loop(self) -> None:
        while not self._stop.wait(self._poll_seconds):
            try:
                current = self._scan()
            except Exception:  # noqa: BLE001 — keep watching regardless
                logger.debug("File watcher scan failed", exc_info=True)
                continue
            previous = self._snapshot
            self._snapshot = current
            events: list[dict] = []
            for path, stat in current.items():
                if path not in previous:
                    events.append({"path": path, "kind": "created"})
                elif previous[path] != stat:
                    events.append({"path": path, "kind": "modified"})
            for path in previous:
                if path not in current:
                    events.append({"path": path, "kind": "deleted"})
            for event in events[:_MAX_EVENTS_PER_SCAN]:
                try:
                    self._callback(event)
                except Exception:  # noqa: BLE001
                    logger.debug("File watcher callback failed", exc_info=True)


class WorkflowEventBridge:
    """Subscribes the workflow engine to the event bus and publishes the
    built-in trigger topics from real producers."""

    def __init__(self, engine: Any = None, bus: Any = None) -> None:
        if engine is None:
            from dash_backend.services.workflow_builder import workflow_engine

            engine = workflow_engine
        if bus is None:
            from dash_backend.events.event_bus import get_event_bus

            bus = get_event_bus()
        self._engine = engine
        self._bus = bus
        self._subscribed = False
        self._watcher = FileWatcher(self._on_file_event)

    # ── lifecycle ──────────────────────────────────────────────────

    @property
    def subscribed(self) -> bool:
        return self._subscribed

    @property
    def watching_files(self) -> bool:
        return self._watcher.running

    async def start(self) -> None:
        """Subscribe to the bus and start the file watcher (non-fatal).

        Async for lifespan symmetry with every other service main.py
        awaits; the work itself is synchronous and cheap."""
        if self._bus is not None and not self._subscribed:
            for topic in SUPPORTED_TOPICS:
                self._bus.subscribe(
                    topic, self._on_bus_event, name=f"workflow_event_bridge:{topic}"
                )
            for pattern in WILDCARD_TOPICS:
                self._bus.subscribe(
                    pattern, self._on_bus_event,
                    name=f"workflow_event_bridge:{pattern}",
                )
            self._subscribed = True
            logger.info(
                "Workflow event bridge subscribed: %s (wildcards: %s)",
                ", ".join(SUPPORTED_TOPICS), ", ".join(WILDCARD_TOPICS),
            )
        if not self._watcher.running:
            if not self._watcher.paths:
                self._watcher = FileWatcher(self._on_file_event,
                                            paths=_watch_paths_from_env())
            self._watcher.start()

    async def stop(self) -> None:
        if self._bus is not None and self._subscribed:
            self._bus.unsubscribe_all("workflow_event_bridge")
            self._subscribed = False
            logger.info("Workflow event bridge unsubscribed")
        self._watcher.stop()

    # ── bus delivery ───────────────────────────────────────────────

    async def _on_bus_event(self, event: Any) -> None:
        try:
            # Off-loop: a triggered workflow may contain a real delay node.
            await asyncio.to_thread(
                self._engine.fire_event, event.topic, dict(event.data or {})
            )
        except Exception:  # noqa: BLE001 — one bad workflow must not kill delivery
            logger.exception("Workflow event fire failed for %s", event.topic)

    def _on_file_event(self, payload: dict) -> None:
        self._fire_direct(EVENT_FILE_CHANGED, payload)

    def _fire_direct(self, topic: str, payload: dict) -> list[str]:
        try:
            return list(self._engine.fire_event(topic, dict(payload)))
        except Exception:  # noqa: BLE001
            logger.exception("Direct event fire failed for %s", topic)
            return []

    # ── producer entry points ──────────────────────────────────────

    async def notify_email_received(self, data: dict) -> list[str]:
        """A genuinely new email was stored. Publishes on the bus; when the
        bridge is subscribed the workflow fires via that subscription."""
        payload = dict(data or {})
        if self._bus is not None:
            try:
                await self._bus.publish_sync(
                    topic=EVENT_EMAIL_RECEIVED, data=payload,
                    source="email_calendar_sync",
                )
                if self._subscribed:
                    return []
            except Exception:  # noqa: BLE001
                logger.exception("Failed to publish %s", EVENT_EMAIL_RECEIVED)
        return self._fire_direct(EVENT_EMAIL_RECEIVED, payload)

    async def notify_reminder_fired(self, data: dict) -> list[str]:
        payload = dict(data or {})
        if self._bus is not None:
            try:
                await self._bus.publish_sync(
                    topic=EVENT_REMINDER_FIRED, data=payload,
                    source="reminder_service",
                )
                if self._subscribed:
                    return []
            except Exception:  # noqa: BLE001
                logger.exception("Failed to publish %s", EVENT_REMINDER_FIRED)
        return self._fire_direct(EVENT_REMINDER_FIRED, payload)

    async def notify_file_changed(self, data: dict) -> list[str]:
        payload = dict(data or {})
        if self._bus is not None:
            try:
                await self._bus.publish_sync(
                    topic=EVENT_FILE_CHANGED, data=payload,
                    source="file_watcher",
                )
                if self._subscribed:
                    return []
            except Exception:  # noqa: BLE001
                logger.exception("Failed to publish %s", EVENT_FILE_CHANGED)
        return self._fire_direct(EVENT_FILE_CHANGED, payload)


_bridge: Optional[WorkflowEventBridge] = None


def get_workflow_event_bridge() -> WorkflowEventBridge:
    """Singleton accessor; main.py starts it during lifespan startup."""
    global _bridge
    if _bridge is None:
        _bridge = WorkflowEventBridge()
    return _bridge
