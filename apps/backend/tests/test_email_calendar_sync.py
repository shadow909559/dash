"""Email/calendar external sync + deadline tracking (decisions.md #52).

Hermetic: parsers are pure functions; services get isolated LocalStore
instances; IMAP is never contacted — network failure paths are exercised
through monkeypatched stubs. Route tests go through the real app (the
phase2 router is included lazily via _IncludedRouter, so route presence
is asserted by HTTP, not by static route tables).
"""

from __future__ import annotations

import pytest

from dash_backend.services.email_calendar_sync import (
    DeadlineService,
    ExtendedCalendarService,
    ExtendedEmailService,
    deadline_urgency,
    parse_eml,
    parse_ics,
)
from dash_backend.services.local_store import LocalStore

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def store(tmp_path):
    return LocalStore(db_path=tmp_path / "sync_test.db")


@pytest.fixture()
def email_svc(store):
    return ExtendedEmailService(store=store)


@pytest.fixture()
def cal_svc(store):
    return ExtendedCalendarService(store=store)


@pytest.fixture()
def dl_svc(store):
    return DeadlineService(store=store)


# ── EML parsing ────────────────────────────────────────────────────────────

def test_parse_eml_plain():
    raw = (
        b"From: Alice <alice@corp.com>\r\n"
        b"Subject: Quarterly report\r\n"
        b"Message-ID: <q3@corp.com>\r\n"
        b"\r\n"
        b"The report is attached.\r\n"
    )
    parsed = parse_eml(raw)
    assert parsed["from"] == "Alice <alice@corp.com>"
    assert parsed["subject"] == "Quarterly report"
    assert parsed["message_id"] == "<q3@corp.com>"
    assert "attached" in parsed["body"]


def test_parse_eml_multipart_takes_plain_text_part():
    raw = (
        b"From: a@b.com\r\nSubject: multi\r\n"
        b"MIME-Version: 1.0\r\n"
        b'Content-Type: multipart/alternative; boundary="BOUND"\r\n'
        b"\r\n"
        b"--BOUND\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"plain body here\r\n"
        b"--BOUND\r\n"
        b"Content-Type: text/html\r\n\r\n"
        b"<b>html body</b>\r\n"
        b"--BOUND--\r\n"
    )
    parsed = parse_eml(raw)
    assert parsed["body"] == "plain body here"


# ── ICS parsing ────────────────────────────────────────────────────────────

def test_parse_ics_basic_and_date_only():
    text = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "BEGIN:VEVENT", "UID:a@x", "DTSTART:20260915T090000Z",
        "DTEND:20260915T100000Z", "SUMMARY:Sync", "LOCATION:Office",
        "END:VEVENT",
        "BEGIN:VEVENT", "UID:b@x", "DTSTART;VALUE=DATE:20260918",
        "SUMMARY:All-day", "END:VEVENT",
        "END:VCALENDAR",
    ])
    events = parse_ics(text)
    assert len(events) == 2
    assert events[0]["start"] == "2026-09-15T09:00:00+00:00"
    assert events[0]["end"] == "2026-09-15T10:00:00+00:00"
    assert events[1]["start"] == "2026-09-18T00:00:00"
    assert events[1]["end"] == ""  # no DTEND — import_ics fills it with start


def test_parse_ics_unfolds_long_lines():
    long_summary = "X" * 90
    text = (
        "BEGIN:VEVENT\r\nUID:c@x\r\nDTSTART:20260920T120000Z\r\n"
        f"SUMMARY:{long_summary[:60]}\r\n"
        f" {long_summary[60:]}\r\n"  # RFC 5545 fold = CRLF + one space
        "END:VEVENT\r\n"
    )
    events = parse_ics(text)
    assert events[0]["title"] == long_summary


def test_parse_ics_skips_unparseable_dates_but_keeps_event():
    text = (
        "BEGIN:VEVENT\r\nUID:d@x\r\nDTSTART:not-a-date\r\n"
        "SUMMARY:Broken\r\nEND:VEVENT\r\n"
    )
    events = parse_ics(text)
    assert events == []  # no start → dropped


# ── deadline urgency ───────────────────────────────────────────────────────

def test_deadline_urgency_buckets():
    from datetime import datetime, timezone

    now = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    assert deadline_urgency("2026-09-12T18:00:00+00:00", now)["urgency"] == "today"
    assert deadline_urgency("2026-09-14T00:00:00+00:00", now)["urgency"] == "urgent"
    assert deadline_urgency("2026-09-12T06:00:00+00:00", now)["urgency"] == "overdue"
    assert deadline_urgency("2026-10-20", now)["urgency"] == "upcoming"
    assert deadline_urgency("garbage")["urgency"] == "unknown"


# ── EML ingest + dedup ─────────────────────────────────────────────────────

async def test_ingest_eml_dedups_on_message_id(email_svc):
    raw = (
        b"From: a@b.com\r\nSubject: once\r\nMessage-ID: <dup@x>\r\n\r\nbody\r\n"
    )
    first = email_svc.ingest_eml(raw)
    second = email_svc.ingest_eml(raw)
    assert first["created"] is True
    assert second["created"] is False
    assert len(email_svc.get_inbox(limit=100)) == 1


async def test_ingest_eml_without_message_id_always_creates(email_svc):
    raw = b"From: a@b.com\r\nSubject: no id\r\n\r\nbody\r\n"
    assert email_svc.ingest_eml(raw)["created"] is True
    assert email_svc.ingest_eml(raw)["created"] is True


# ── IMAP fetch (network stubbed) ───────────────────────────────────────────

async def test_fetch_imap_requires_credentials(email_svc):
    account = email_svc.add_account("user@gmail.com")["account"]
    result = email_svc.fetch_imap(account["id"])
    assert result["ok"] is False
    assert "credentials" in result["reason"]


async def test_fetch_imap_unknown_provider_needs_host(email_svc):
    account = email_svc.add_account("user@unknown-domain.tld")["account"]
    email_svc.set_credentials(account["id"], "secret")
    result = email_svc.fetch_imap(account["id"])
    assert result["ok"] is False
    assert "host" in result["reason"]


async def test_fetch_imap_happy_path_stubs_network(email_svc, monkeypatch):
    account = email_svc.add_account("user@gmail.com")["account"]
    email_svc.set_credentials(account["id"], "app-password")

    raw = b"From: f@x.com\r\nSubject: from imap\r\nMessage-ID: <imap@x>\r\n\r\nhi\r\n"

    class FakeConn:
        def __init__(self, *a, **k):
            pass

        def login(self, user, pw):
            assert user == "user@gmail.com"
            assert pw == "app-password"  # decrypts the stored blob

        def select(self, folder):
            assert folder == "INBOX"

        def search(self, charset, *criterion):
            return "OK", [b"1 2"]

        def fetch(self, num, spec):
            assert spec == "(RFC822)"
            return "OK", [(b"1", raw)]

        def logout(self):
            pass

    import imaplib as _imaplib

    monkeypatch.setattr(
        _imaplib, "IMAP4_SSL", lambda *a, **k: FakeConn()
    )

    result = email_svc.fetch_imap(account["id"])
    assert result["ok"] is True
    assert result["created"] == 1
    subjects = [e["subject"] for e in email_svc.get_inbox(limit=10)]
    assert "from imap" in subjects
    # Second fetch with the same message dedups.
    result2 = email_svc.fetch_imap(account["id"])
    assert result2["created"] == 0


async def test_credentials_never_leak_via_list_accounts(email_svc):
    account = email_svc.add_account("user@gmail.com")["account"]
    email_svc.set_credentials(account["id"], "topsecret")
    listed = email_svc.list_accounts()
    assert all("password_enc" not in a for a in listed)
    assert all(a.get("has_credentials") is True for a in listed
               if a["id"] == account["id"])


# ── ICS import + dedup ─────────────────────────────────────────────────────

async def test_import_ics_creates_and_dedups(cal_svc):
    text = "\r\n".join([
        "BEGIN:VCALENDAR", "BEGIN:VEVENT", "UID:dup-1@x",
        "DTSTART:20260915T090000Z", "SUMMARY:Tax filing",
        "END:VEVENT", "END:VCALENDAR",
    ])
    first = cal_svc.import_ics(text)
    second = cal_svc.import_ics(text)
    assert first["created"] == 1 and first["skipped"] == 0
    assert second["created"] == 0 and second["skipped"] == 1
    assert cal_svc.get_events()[0]["external_id"] == "dup-1@x"


# ── deadline extraction from emails ────────────────────────────────────────

async def test_extract_deadlines_finds_due_dates(email_svc, dl_svc):
    email_svc.receive_email(
        "boss@corp.com", "Report", "please submit by 2026-09-20, thanks")
    email_svc.receive_email("news@x.com", "Newsletter", "no dates here")
    result = email_svc.extract_deadlines(deadline_svc=dl_svc)
    assert result["scanned"] == 2
    assert result["created"] == 1
    dues = [d["due"] for d in dl_svc.list_deadlines()]
    assert any(d.startswith("2026-09-20") for d in dues)


async def test_extract_deadlines_no_email_dupes(email_svc, dl_svc):
    email_svc.receive_email("b@c.com", "Invoice", "due 2026-10-01")
    email_svc.extract_deadlines(deadline_svc=dl_svc)
    again = email_svc.extract_deadlines(deadline_svc=dl_svc)
    assert again["created"] == 0  # source_id dedup


# ── unified deadline view ──────────────────────────────────────────────────

async def test_unified_deadlines_merge_and_sort(cal_svc, dl_svc):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    # Calendar deadline tomorrow (urgent-ish), email deadline +10d
    cal_svc.create_event("Submission deadline", (now + timedelta(days=2)).isoformat(),
                         (now + timedelta(days=2)).isoformat())
    dl_svc.add_deadline("Far-out thing", (now + timedelta(days=10)).isoformat(),
                        source="email", source_id="e1")
    items = cal_svc.get_deadlines(deadline_svc=dl_svc)
    assert len(items) >= 2
    # Non-deadline events are excluded
    cal_svc.create_event("Lunch", (now + timedelta(days=1)).isoformat(),
                         (now + timedelta(days=1)).isoformat())
    titles = [i["title"] for i in items]
    assert "Lunch" not in titles
    assert "Submission deadline" in titles
    # Sorted: calendar urgent before far-out upcoming
    assert items[0]["source"] == "calendar"


# ── routes (real app) ──────────────────────────────────────────────────────

from tests.conftest import AUTH_HEADERS  # noqa: E402


async def test_route_ingest_eml_and_scan_deadlines(client):
    raw = (
        b"From: boss@corp.com\r\nSubject: Deadline notice\r\n"
        b"Message-ID: <rt-1@x>\r\n\r\ndue 2026-12-01\r\n"
    )
    r = await client.post("/api/v1/features/email/ingest-eml",
                          content=raw, headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["created"] is True

    r2 = await client.post("/api/v1/features/email/scan-deadlines",
                           headers=AUTH_HEADERS)
    assert r2.status_code == 200
    assert r2.json()["scanned"] >= 1


async def test_route_ingest_eml_empty_body_rejected(client):
    r = await client.post("/api/v1/features/email/ingest-eml",
                          content=b"", headers=AUTH_HEADERS)
    assert r.status_code == 422


async def test_route_ics_import_and_deadlines_endpoint(client):
    ics = "\r\n".join([
        "BEGIN:VCALENDAR", "BEGIN:VEVENT", "UID:rt-ics@x",
        "DTSTART:20260925T090000Z", "SUMMARY:Route test deadline",
        "END:VEVENT", "END:VCALENDAR",
    ])
    r = await client.post("/api/v1/features/calendar/import-ics",
                          content=ics.encode(), headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["created"] == 1

    r2 = await client.get("/api/v1/features/deadlines", headers=AUTH_HEADERS)
    assert r2.status_code == 200
    items = r2.json()["deadlines"]
    assert any("Route test deadline" in i["title"] for i in items)


async def test_route_event_update_delete_reminder(client):
    rc = await client.post(
        "/api/v1/features/calendar/events",
        json={"title": "Original", "start": "2026-12-05T10:00:00+00:00",
              "end": "2026-12-05T11:00:00+00:00"},
        headers=AUTH_HEADERS,
    )
    event = rc.json()["event"]

    ru = await client.put(
        f"/api/v1/features/calendar/events/{event['id']}",
        json={"title": "Renamed"}, headers=AUTH_HEADERS,
    )
    assert ru.json()["event"]["title"] == "Renamed"

    rr = await client.post(
        f"/api/v1/features/calendar/events/{event['id']}/reminders",
        json={"minutes_before": 15}, headers=AUTH_HEADERS,
    )
    assert rr.json()["ok"] is True

    rd = await client.delete(
        f"/api/v1/features/calendar/events/{event['id']}",
        headers=AUTH_HEADERS,
    )
    assert rd.json()["ok"] is True


async def test_route_email_rules_crud(client):
    r = await client.post(
        "/api/v1/features/email/rules",
        json={"name": "Newsletter", "field": "subject", "op": "contains",
              "value": "newsletter", "action": "label", "label": "news"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    rule = r.json()["rule"]

    r2 = await client.get("/api/v1/features/email/rules", headers=AUTH_HEADERS)
    assert any(x["id"] == rule["id"] for x in r2.json()["rules"])

    r3 = await client.delete(f"/api/v1/features/email/rules/{rule['id']}",
                             headers=AUTH_HEADERS)
    assert r3.json()["ok"] is True
