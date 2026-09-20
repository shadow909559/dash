"""DASH PresenceEngine — one authoritative, observable presence signal.

Phase 2 of the behavioral upgrade (decisions.md #116): the master prompt's
Layer 1. DASH already has states scattered across surfaces — the voice loop
(``WakeLoopStatus.state``), the task orchestrator (``TaskStatus``), the
approval engine (pending requests), and the meeting engine (live sessions) —
but nothing fuses them into ONE answer to "what is DASH doing right now?".

This module is that answer. Design rules:

- **Fusion, not ownership.** Surfaces *claim* presence (``claim()``); the
  engine resolves conflicts by fixed priority. A source never sets the
  whole state — so no component can fight another for the orb.
- **Real sources only.** Claims come with a source tag; every claim is
  auditable and the engine exposes exactly which source owns the current
  state. No synthetic "thinking" delays, no decorative states.
- **TTL honesty.** Transient claims (SPEAKING, EXECUTING…) auto-expire if
  their owner dies without releasing — a crashed speaker must not leave
  the orb stuck. Sticky claims (WAITING_FOR_APPROVAL, IN_MEETING) never
  expire on a timer; they end when the real thing ends.
- **Push + pull.** Every change pushes ``presence.update`` over the
  existing assistant websocket (same envelope/pattern as
  ``approval.created``) and publishes on the existing EventBus
  (``presence.changed``). The REST snapshot is the reconciliation
  fallback, per the push/pull convention already used by tasks (#95).

Single-owner local system: presence is global, not per-user.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# ── The presence enum ─────────────────────────────────────────────────────
# Master prompt §5. Priority order below is the fusion policy: when several
# sources claim at once, the highest-priority state wins. Rationale:
# a blocked approval or a live call outruns background monitoring; a crash
# (ERROR) outruns everything so the owner sees it.


class Presence:
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    PROCESSING = "processing"
    EXECUTING = "executing"
    OBSERVING = "observing"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    WAITING_FOR_USER = "waiting_for_user"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    MONITORING = "monitoring"
    CALLING = "calling"
    IN_CALL = "in_call"
    IN_MEETING = "in_meeting"
    PAUSED = "paused"
    ERROR = "error"


# Higher number wins when claims collide.
PRESENCE_PRIORITY: dict[str, int] = {
    Presence.ERROR: 100,
    Presence.WAITING_FOR_APPROVAL: 95,
    Presence.CALLING: 92,
    Presence.IN_CALL: 92,
    Presence.IN_MEETING: 90,
    Presence.RECOVERING: 85,
    Presence.VERIFYING: 80,
    Presence.EXECUTING: 75,
    Presence.SPEAKING: 70,
    Presence.INTERRUPTED: 68,
    Presence.LISTENING: 65,
    Presence.THINKING: 60,
    Presence.PROCESSING: 55,
    Presence.OBSERVING: 40,
    Presence.MONITORING: 30,
    Presence.WAITING_FOR_USER: 50,
    Presence.PAUSED: 45,
    Presence.IDLE: 0,
}

# States that must NOT expire on a timer — they end when the real
# underlying thing ends (approval resolved, meeting closed, call hung up).
STICKY_STATES = {
    Presence.WAITING_FOR_APPROVAL,
    Presence.CALLING,
    Presence.IN_CALL,
    Presence.IN_MEETING,
    Presence.PAUSED,
}

# Default TTLs for transient claims (seconds) — a safety net for owners
# that vanish (task coroutine cancelled, voice loop crashed) rather than a
# state machine clock.
DEFAULT_TTL: dict[str, float] = {
    Presence.SPEAKING: 300.0,
    Presence.LISTENING: 3600.0,
    Presence.THINKING: 300.0,
    Presence.PROCESSING: 600.0,
    Presence.EXECUTING: 3600.0,
    Presence.VERIFYING: 600.0,
    Presence.RECOVERING: 600.0,
    Presence.OBSERVING: 3600.0,
    Presence.MONITORING: 86400.0,
    Presence.WAITING_FOR_USER: 86400.0,
    Presence.INTERRUPTED: 60.0,
}


@dataclass
class Claim:
    """One source's claim on presence."""

    source: str          # "voice_loop" | "task_orchestrator" | "approvals" |
                         # "meetings" | "communication" | "chat" | ...
    state: str
    detail: str = ""
    since: float = 0.0
    expires_at: Optional[float] = None  # None = sticky
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "state": self.state,
            "detail": self.detail[:200],
            "since": self.since,
            "expires_at": self.expires_at,
        }


def _now() -> float:
    return time.time()


class PresenceEngine:
    """Fuses source claims into one observable presence state."""

    def __init__(self) -> None:
        self._claims: dict[str, Claim] = {}
        self._lock = threading.RLock()
        # Last resolved snapshot (also what REST returns when no claims).
        self._resolved_state: str = Presence.IDLE
        self._resolved_source: str = ""
        self._resolved_detail: str = ""
        self._resolved_at: float = _now()
        # Owner-observable transition history (decisions.md #123): bounded
        # ring of real state changes, newest last. Recorded at the two
        # transition points — claim-mutation resolution and read-path
        # expiry — never fabricated.
        self._history: deque[dict[str, Any]] = deque(maxlen=50)

    # ── Claims API ────────────────────────────────────────────────────

    def claim(
        self,
        source: str,
        state: str,
        detail: str = "",
        ttl: Optional[float] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Source claims presence. Returns the resolved snapshot."""
        if state not in PRESENCE_PRIORITY:
            raise ValueError(f"unknown presence state: {state}")
        now = _now()
        if state in STICKY_STATES:
            expires_at: Optional[float] = None
        else:
            expires_at = now + (DEFAULT_TTL.get(state, 600.0) if ttl is None else max(1.0, float(ttl)))
        with self._lock:
            self._claims[source] = Claim(
                source=source, state=state, detail=detail,
                since=now, expires_at=expires_at, meta=meta or {},
            )
            return self._resolve_locked()

    def release(self, source: str) -> dict[str, Any]:
        """Source releases its claim (loop stopped, task done, meeting ended)."""
        with self._lock:
            self._claims.pop(source, None)
            return self._resolve_locked()

    def release_state(self, source: str, state: str) -> dict[str, Any]:
        """Release only if the source still holds *state* (no clobbering)."""
        with self._lock:
            c = self._claims.get(source)
            if c is not None and c.state == state:
                self._claims.pop(source, None)
            return self._resolve_locked()

    # ── Resolution ────────────────────────────────────────────────────

    def _expire_locked(self, now: float) -> None:
        dead = [s for s, c in self._claims.items()
                if c.expires_at is not None and c.expires_at < now]
        for s in dead:
            logger.info("presence claim expired: source=%s state=%s",
                        s, self._claims[s].state)
            del self._claims[s]

    def _resolve_locked(self) -> dict[str, Any]:
        self._expire_locked(_now())
        if not self._claims:
            state, source, detail = Presence.IDLE, "", ""
        else:
            best = max(
                self._claims.values(),
                key=lambda c: (PRESENCE_PRIORITY.get(c.state, 0), c.since),
            )
            state, source, detail = best.state, best.source, best.detail
        changed = state != self._resolved_state
        self._resolved_state, self._resolved_source = state, source
        self._resolved_detail = detail
        self._resolved_at = _now()
        if changed:
            self._record_transition(state, source, detail)
        snapshot = self.snapshot()
        if changed:
            self._broadcast(snapshot)
        return snapshot

    def _record_transition(self, state: str, source: str, detail: str) -> None:
        """Append one real transition to the bounded history ring.
        Caller holds the lock."""
        self._history.append({
            "state": state,
            "source": source,
            "detail": detail[:200],
            "at": _now(),
        })

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Recent presence transitions, oldest first, newest last."""
        with self._lock:
            self._expire_locked(_now())
            items = list(self._history)
        try:
            limit = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            limit = 50
        return items[-limit:]

    # ── Observers ─────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        # Resolve on read: a caller may hold a claim whose TTL elapsed
        # between mutations — the snapshot must never serve a dead state.
        with self._lock:
            self._expire_locked(_now())
            if self._claims:
                best = max(
                    self._claims.values(),
                    key=lambda c: (PRESENCE_PRIORITY.get(c.state, 0), c.since),
                )
                if best.state != self._resolved_state:
                    self._resolved_state = best.state
                    self._resolved_source = best.source
                    self._resolved_detail = best.detail
                    self._resolved_at = _now()
                    self._record_transition(best.state, best.source, best.detail)
            elif self._resolved_state != Presence.IDLE and not self._claims:
                self._resolved_state = Presence.IDLE
                self._resolved_source = ""
                self._resolved_detail = ""
                self._resolved_at = _now()
                self._record_transition(Presence.IDLE, "", "")
            return {
                "state": self._resolved_state,
                "source": self._resolved_source,
                "detail": self._resolved_detail[:200],
                "since": self._resolved_at,
                "claims": [c.to_dict() for c in self._claims.values()],
            }

    @property
    def state(self) -> str:
        return self.snapshot()["state"]

    # ── Delivery (same conventions as assistant/push.py) ─────────────

    def _broadcast(self, snap: dict[str, Any]) -> None:
        payload = {"type": "presence.update", "presence": snap}
        try:
            from dash_backend.assistant.push import push_assistant_event
            push_assistant_event(None, payload)
        except Exception:
            logger.exception("presence ws push failed")
        try:
            import asyncio

            from dash_backend.events.event_bus import (
                Event,
                EventPriority,
                get_event_bus,
            )
            data = {"state": snap["state"], "source": snap["source"]}
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            bus = get_event_bus()
            if loop is not None:
                loop.create_task(bus.publish(Event(
                    topic="presence.changed", source="presence_engine",
                    priority=EventPriority.HIGH, data=data,
                )))
            else:
                # No running loop (sync tests / module import time): schedule
                # on the captured loop if one exists, else skip — the ws push
                # above already delivered to live clients.
                captured = getattr(bus, "_loop", None)
                if captured is not None and not captured.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        bus.publish(Event(
                            topic="presence.changed", source="presence_engine",
                            priority=EventPriority.HIGH, data=data,
                        )), captured)
        except Exception:
            logger.exception("presence event-bus publish failed")


_engine: Optional[PresenceEngine] | None = None
_engine_lock = threading.Lock()


def get_presence_engine() -> PresenceEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = PresenceEngine()
    return _engine


def reset_presence_engine() -> None:
    """Test helper."""
    global _engine
    with _engine_lock:
        _engine = None
