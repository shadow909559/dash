"""Owner-contact urgency policy (master plan Phase 4, spec #9/#10).

One shared vocabulary for every channel that reaches the owner — the
proactive tick, the Android companion bridge, and the desktop notifier —
so "how urgent is this" and "which channels may fire" are decided in
exactly one place instead of ad-hoc string comparisons per module.

The five-level scale is the one the owner preference
``notification_urgency_floor`` already validates (crm_store):

    low → normal → important → urgent → critical

Channels, ordered by intrusiveness (master plan §10):

    ws        — in-app push over the assistant websocket. Always fires;
                it is how the UI stays live, not an interruption.
    digest    — the proactive digest record (persisted, surfaced on
                demand). Always fires; costs the owner nothing.
    desktop   — OS desktop notification (toasts). Fires from `important`
                up. This also fixes a real bug: the old check was
                ``urgency == "urgent"``, so a `critical` item never
                produced a desktop notification.
    phone     — Android companion push. Fires from `urgent` up by
                default (the phone is for urgent things — spec #34) but
                now RESPECTS the owner's notification_urgency_floor when
                it is raised above that; previously the floor was only
                consulted for approvals, not proactive items.
    voice     — DASH speaking proactively. Fires from `critical` up
                (never interrupt the owner's day by voice without
                something truly critical; quiet hours apply).

Quiet hours (master plan §10 "should DASH wait"): the owner's
notification_urgency_floor stays in force all day, but during the quiet
window every channel except ws/digest is silenced — EXCEPT `critical`,
which breaks through by definition (a fire at 3am must wake someone).

All functions are pure/policy-only: no I/O, no clock reads except
through the injected `local_hour` callable, fully injectable for tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ── The shared five-level scale (order IS the semantics) ─────────────

URGENCY_LEVELS = ("low", "normal", "important", "urgent", "critical")

CHANNELS = ("ws", "digest", "desktop", "phone", "voice")

# Minimum urgency each channel requires. Order = intrusiveness.
CHANNEL_MIN_URGENCY: dict[str, str] = {
    "ws": "low",
    "digest": "low",
    "desktop": "important",
    "phone": "urgent",
    "voice": "critical",
}


def rank(urgency: str) -> int:
    """Index of an urgency on the shared scale; unknown → `normal` (0-ranked
    mid) — callers validate at the edges; this never raises."""
    try:
        return URGENCY_LEVELS.index((urgency or "").lower())
    except ValueError:
        return URGENCY_LEVELS.index("normal")


def at_least(urgency: str, floor: str) -> bool:
    """True when `urgency` is greater than or equal to `floor`."""
    return rank(urgency) >= rank(floor)


def floor_from_preferences(prefs: Optional[dict[str, Any]]) -> str:
    """Owner's urgency floor from preferences, defaulting like crm_store.

    The floor LIFTS channels: a channel fires only when its own minimum
    urgency AND the owner's floor are both met (i.e. the effective floor
    is the max of the two). `critical` items ignore the floor — by the
    time something is critical, silence is the bigger risk.
    """
    try:
        value = (prefs or {}).get("notification_urgency_floor")
    except Exception:
        value = None
    return value if value in URGENCY_LEVELS else "important"


def effective_floor(channel: str, owner_floor: str) -> str:
    """The floor a channel actually enforces: max(channel min, owner floor).

    `critical` is never floored away — an emergency contact channel that
    can be disabled by a preference would not be an emergency channel.
    """
    channel_min = CHANNEL_MIN_URGENCY.get(channel, "critical")
    if channel_min == "critical":
        return "critical"
    return channel_min if rank(channel_min) >= rank(owner_floor) else owner_floor


# ── Quiet hours ──────────────────────────────────────────────────────


@dataclass
class QuietHours:
    """Owner's do-not-disturb window in LOCAL hours.

    ``start`` == ``end`` means "never quiet" (an always-quiet window of
    zero length). A wrap-around window (e.g. 22 → 7) means overnight:
    quiet when hour >= start OR hour < end.
    """

    start: int = 0
    end: int = 0

    def is_quiet(self, local_hour: int) -> bool:
        try:
            h = int(local_hour)
        except (TypeError, ValueError):
            return False
        if not (0 <= h <= 23):
            return False
        s, e = self.start, self.end
        if s == e:
            return False
        if s < e:
            return s <= h < e
        return h >= s or h < e  # overnight wrap (22 → 7)

    @classmethod
    def from_preferences(cls, prefs: Optional[dict[str, Any]]) -> "QuietHours":
        raw = (prefs or {}).get("quiet_hours")
        if not isinstance(raw, dict):
            return cls(0, 0)  # default: no quiet hours configured

        def _hour(key: str) -> int:
            try:
                v = int(raw.get(key, 0))
            except (TypeError, ValueError):
                return 0
            return v if 0 <= v <= 23 else 0

        return cls(_hour("start"), _hour("end"))


# ── Routing decision ─────────────────────────────────────────────────


@dataclass
class RouteDecision:
    urgency: str
    channels: list[str] = field(default_factory=list)
    quiet: bool = False
    floor: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "urgency": self.urgency,
            "channels": list(self.channels),
            "quiet": self.quiet,
            "floor": self.floor,
        }


def route_contact(
    urgency: str,
    *,
    prefs: Optional[dict[str, Any]] = None,
    local_hour: Optional[Callable[[], int]] = None,
) -> RouteDecision:
    """Which channels may carry this item to the owner, decided once.

    Rules, in order:
      1. Unknown urgency strings rank as `normal` (never silently
         promoted to urgent).
      2. ws + digest always fire — they are the ambient record, not an
         interruption.
      3. Intrusive channels (desktop/phone/voice) require BOTH their own
         minimum urgency and the owner's floor (effective_floor).
      4. During quiet hours, intrusive channels are silenced — EXCEPT
         `critical`, which breaks through (a critical fire at 3am must
         reach someone).
    """
    u = (urgency or "").lower()
    if u not in URGENCY_LEVELS:
        u = "normal"
    owner_floor = floor_from_preferences(prefs)
    qh = QuietHours.from_preferences(prefs)
    hour = local_hour() if local_hour is not None else 0
    quiet = qh.is_quiet(hour)

    channels = ["ws", "digest"]
    if not quiet or u == "critical":
        for channel in ("desktop", "phone", "voice"):
            if at_least(u, effective_floor(channel, owner_floor)):
                channels.append(channel)
    return RouteDecision(urgency=u, channels=channels, quiet=quiet,
                         floor=owner_floor)
