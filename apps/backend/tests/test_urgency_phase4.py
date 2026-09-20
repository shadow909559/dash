"""Phase 4 — owner-contact urgency policy tests (decisions.md #119).

Pins the ONE routing vocabulary (assistant/urgency.py) and its three
real consumers:
  - route_contact: channel selection by urgency, owner floor, quiet hours
  - the two bug fixes: desktop notify now includes `critical` (old code
    checked == "urgent" only), phone push respects a RAISED owner floor
  - quiet_hours preference: validation, defaults, critical break-through
  - proactive_tick stamps routing decisions on digest items
"""
from __future__ import annotations

import pytest

from dash_backend.assistant import mobile_bridge as amob
from dash_backend.assistant import proactive as aprobic
from dash_backend.assistant import urgency as aurg
from dash_backend.assistant.crm_store import CrmStore


# ── The shared scale ──────────────────────────────────────────────────


def test_rank_ordering_is_total():
    assert aurg.rank("low") < aurg.rank("normal") < aurg.rank("important") \
        < aurg.rank("urgent") < aurg.rank("critical")
    # Unknown strings rank as normal — never silently promoted to urgent.
    assert aurg.rank("hogwash") == aurg.rank("normal")
    assert aurg.at_least("urgent", "important") is True
    assert aurg.at_least("normal", "important") is False


def test_route_contact_default_channels():
    prefs = {}  # default floor: important
    # important → ws + digest + desktop (desktop fix: no longer ==urgent only)
    d = aurg.route_contact("important", prefs=prefs, local_hour=lambda: 12)
    assert set(d.channels) == {"ws", "digest", "desktop"}
    # urgent → adds phone, still no voice
    d = aurg.route_contact("urgent", prefs=prefs, local_hour=lambda: 12)
    assert set(d.channels) == {"ws", "digest", "desktop", "phone"}
    # critical → everything, including voice
    d = aurg.route_contact("critical", prefs=prefs, local_hour=lambda: 12)
    assert set(d.channels) == {"ws", "digest", "desktop", "phone", "voice"}
    # low/normal → ambient channels only (never cry wolf, spec #34)
    d = aurg.route_contact("low", prefs=prefs, local_hour=lambda: 12)
    assert set(d.channels) == {"ws", "digest"}


def test_owner_floor_lifts_intrusive_channels():
    prefs = {"notification_urgency_floor": "critical"}
    # urgent is below the raised floor → phone silenced
    d = aurg.route_contact("urgent", prefs=prefs, local_hour=lambda: 12)
    assert "phone" not in d.channels and "desktop" not in d.channels
    assert set(d.channels) == {"ws", "digest"}
    # floor cannot silence the ambient record
    assert "ws" in d.channels and "digest" in d.channels


def test_critical_bypasses_any_floor():
    """By the time something is critical, silence is the bigger risk."""
    prefs = {"notification_urgency_floor": "critical"}
    d = aurg.route_contact("critical", prefs=prefs, local_hour=lambda: 12)
    assert "phone" in d.channels and "voice" in d.channels and "desktop" in d.channels


# ── Quiet hours ───────────────────────────────────────────────────────


def test_quiet_hours_windows_and_wrap():
    # daytime window 13-15
    qh = aurg.QuietHours(13, 15)
    assert qh.is_quiet(13) and qh.is_quiet(14)
    assert not qh.is_quiet(12) and not qh.is_quiet(15) and not qh.is_quiet(3)
    # overnight window 22 → 7
    overnight = aurg.QuietHours(22, 7)
    assert overnight.is_quiet(23) and overnight.is_quiet(3) and overnight.is_quiet(6)
    assert not overnight.is_quiet(7) and not overnight.is_quiet(12) \
        and not overnight.is_quiet(21)
    # 0/0 = never quiet; invalid hours never quiet
    never = aurg.QuietHours(0, 0)
    assert not never.is_quiet(3) and not never.is_quiet(22)
    assert not aurg.QuietHours(8, 20).is_quiet(99)
    assert not aurg.QuietHours(8, 20).is_quiet(-1)


def test_quiet_hours_route_silence_with_critical_breakthrough():
    prefs = {"quiet_hours": {"start": 22, "end": 7}}
    # 23h: urgent silenced to ambient channels
    d = aurg.route_contact("urgent", prefs=prefs, local_hour=lambda: 23)
    assert set(d.channels) == {"ws", "digest"} and d.quiet is True
    # 3am: critical breaks through — a 3am fire must reach someone
    d = aurg.route_contact("critical", prefs=prefs, local_hour=lambda: 3)
    assert "phone" in d.channels and "desktop" in d.channels and "voice" in d.channels
    # 12h: not quiet — urgent routes normally
    d = aurg.route_contact("urgent", prefs=prefs, local_hour=lambda: 12)
    assert "phone" in d.channels and "desktop" in d.channels


def test_quiet_hours_preference_validation_and_persistence(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    # defaults: never quiet
    assert store.get_preferences()["quiet_hours"] == {"start": 0, "end": 0}
    # invalid values rejected
    with pytest.raises(ValueError):
        store.update_preferences({"quiet_hours": {"start": 24, "end": 0}})
    with pytest.raises(ValueError):
        store.update_preferences({"quiet_hours": "overnight"})
    # valid window persists
    store.update_preferences({"quiet_hours": {"start": 22, "end": 7}})
    store2 = CrmStore(base_dir=tmp_path)
    assert store2.get_preferences()["quiet_hours"] == {"start": 22, "end": 7}


# ── Consumers: proactive tick + mobile bridge ─────────────────────────


class _FakeNotifier:
    def __init__(self):
        self.calls = []

    async def show(self, title, message):
        self.calls.append({"title": title, "message": message})


@pytest.fixture(autouse=True)
def _reset_dedupe():
    aprobic._seen.clear()
    amob.reset_seen()
    yield
    aprobic._seen.clear()
    amob.reset_seen()


@pytest.mark.asyncio
async def test_proactive_tick_stamps_channels_and_notifies(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    store.add_action_item("Overdue thing", owner="Shadow", due="2020-01-01")
    notifier = _FakeNotifier()
    d = await aprobic.proactive_tick(store, notifier=notifier)
    urgent_items = [i for i in d["items"] if i["urgency"] == "urgent"]
    assert urgent_items, "overdue action must produce an urgent item"
    item = urgent_items[0]
    # Routing decision stamped on the item, decided by ONE policy module
    assert "phone" in item["channels"] and "desktop" in item["channels"] \
        and "ws" in item["channels"]
    # Desktop notifier fired for the urgent item (spec #34)
    assert notifier.calls, "urgent item must trigger the desktop notifier"
    # Second pass same day → deduped to silence
    d2 = await aprobic.proactive_tick(store, notifier=notifier)
    assert d2["items"] == []


def test_desktop_critical_bug_is_fixed():
    """The old delivery code checked ``urgency == 'urgent'`` only, so a
    CRITICAL item never produced a desktop notification. Routing now
    includes desktop for critical — pinned here."""
    d = aurg.route_contact("critical", prefs={}, local_hour=lambda: 12)
    assert "desktop" in d.channels


def test_mobile_bridge_respects_raised_floor(tmp_path):
    store = CrmStore(base_dir=tmp_path)
    item = {"kind": "action_due", "text": "Overdue: send docs",
            "urgency": "urgent"}
    # Default floor: urgent reaches the phone (record queued, maybe 0
    # devices — honest queue/delivered split, #117)
    r = amob.push_proactive_item(dict(item), store)
    assert r is not None
    # Floor raised to critical: urgent silenced on the phone
    store.update_preferences({"notification_urgency_floor": "critical"})
    amob.reset_seen()
    assert amob.push_proactive_item(dict(item), store) is None
    # ...but critical still pushes under the raised floor
    amob.reset_seen()
    crit = {"kind": "action_due", "text": "Production down",
            "urgency": "critical"}
    assert amob.push_proactive_item(crit, store) is not None


def test_mobile_bridge_urgent_floor_default_without_store():
    """Legacy callers (no store) keep the pinned urgent-only behavior."""
    item = {"kind": "x", "text": "t", "urgency": "important"}
    assert amob.push_proactive_item(item) is None
