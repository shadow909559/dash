"""External email/calendar sync and deadline tracking.

Extends EmailService/CalendarService (email_calendar.py) with the pieces
that touch the outside world (decisions.md #52):

- IMAP fetch: real mailbox polling via stdlib imaplib, credentials stored
  encrypted (integration_connectors.SecretBox, AES-256-GCM) — never plaintext.
- EML ingest: parse a raw RFC-822 message (webhook/manual paste) with
  stdlib email parsing; no external dependencies.
- ICS import: minimal RFC-5545 parser (unfold + VEVENT blocks) for
  calendar subscriptions/exports; dedup on UID.
- Deadlines: a unified, persisted deadline list fed from emails ("due
  2026-09-20" patterns), calendar events, and manual entries, with
  urgency buckets so the UI and briefing can sort by what's closest.

The extended classes are singletons that REBIND the base module's
email_service/calendar_service attributes, so every later
``from dash_backend.services.email_calendar import email_service`` (all
existing routes import lazily inside handlers) transparently gets the
extended behavior.
"""
from __future__ import annotations

import hashlib
import imaplib
import logging
import re
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from typing import Optional

from dash_backend.services.email_calendar import (
    CalendarService,
    EmailService,
)
from dash_backend.services.integration_connectors import SecretBox
from dash_backend.services.local_store import LocalStore, new_id

logger = logging.getLogger(__name__)

# Well-known provider → IMAP host. Unknown domains must pass host explicitly.
PROVIDER_HOSTS = {
    "gmail.com": "imap.gmail.com",
    "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com",
    "hotmail.com": "outlook.office365.com",
    "live.com": "outlook.office365.com",
    "yahoo.com": "imap.mail.yahoo.com",
    "icloud.com": "imap.mail.me.com",
}

# Subject/body phrases that precede an explicit ISO due date.
_DUE_PATTERNS = re.compile(
    r"(?:due|deadline|expires?|submit by|submit before|by)\s*[: ]*\s*"
    r"(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?)",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_eml(raw: bytes) -> dict:
    """Parse an RFC-822 message into DASH's email dict shape (no persistence)."""
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                body = part.get_content()
                break
    else:
        try:
            body = msg.get_content()
        except Exception:  # noqa: BLE001 — non-text bodies
            body = ""
    return {
        "from": str(msg.get("From", "")),
        "subject": str(msg.get("Subject", "")),
        "body": body,
        "message_id": str(msg.get("Message-ID", "")),
        "received_at": _now_iso(),
    }


def _parse_ics_dt(value: str, params: str) -> str:
    """Map an ICS DTSTART/DTEND value to an ISO-8601 string."""
    if "VALUE=DATE" in params or (len(value) == 8 and "T" not in value):
        d = datetime.strptime(value, "%Y%m%d")
        return d.isoformat()
    if value.endswith("Z"):
        d = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return d.isoformat()
    d = datetime.strptime(value, "%Y%m%dT%H%M%S")
    return d.isoformat()


def parse_ics(text: str) -> list[dict]:
    """Extract VEVENT blocks from ICS text. Returns event dicts with uid."""
    # Unfold: RFC 5545 folds long lines with CRLF + space/tab.
    unfolded: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    events: list[dict] = []
    current: Optional[dict] = None
    for line in unfolded:
        stripped = line.strip()
        if stripped.upper() == "BEGIN:VEVENT":
            current = {"uid": "", "title": "", "start": "", "end": "",
                       "description": "", "location": "", "status": "confirmed"}
            continue
        if stripped.upper() == "END:VEVENT":
            if current and current.get("start"):
                events.append(current)
            current = None
            continue
        if current is None or ":" not in stripped:
            continue
        head, _, value = stripped.partition(":")
        name, _, params = head.partition(";")
        name = name.upper()
        value = value.strip()
        try:
            if name == "UID":
                current["uid"] = value
            elif name == "SUMMARY":
                current["title"] = value
            elif name == "DTSTART":
                current["start"] = _parse_ics_dt(value, params)
            elif name == "DTEND":
                current["end"] = _parse_ics_dt(value, params)
            elif name == "DESCRIPTION":
                current["description"] = value
            elif name == "LOCATION":
                current["location"] = value
            elif name == "STATUS" and value.upper() == "CANCELLED":
                current["status"] = "cancelled"
        except ValueError:
            logger.warning("ICS: unparseable date in field %s: %r", name, value)
    return events


def deadline_urgency(due_iso: str, now: Optional[datetime] = None) -> dict:
    """Classify a due date into an urgency bucket for sorting/UX."""
    now = now or datetime.now(timezone.utc)
    try:
        due = datetime.fromisoformat(due_iso)
    except (ValueError, TypeError):
        return {"days_remaining": None, "urgency": "unknown"}
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    delta = (due - now).total_seconds()
    days = round(delta / 86400, 2)
    if delta < 0:
        urgency = "overdue"
    elif delta < 86400:
        urgency = "today"
    elif delta <= 2 * 86400:
        urgency = "urgent"
    elif delta <= 7 * 86400:
        urgency = "soon"
    else:
        urgency = "upcoming"
    return {"days_remaining": days, "urgency": urgency}


_URGENCY_ORDER = {"overdue": 0, "today": 1, "urgent": 2, "soon": 3,
                  "upcoming": 4, "unknown": 5}


class ExtendedEmailService(EmailService):
    """EmailService + IMAP fetch, EML ingest, rules engine, deadline extraction."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        super().__init__(store)
        try:
            self._secrets = SecretBox(self._store)
        except RuntimeError:  # pragma: no cover — cryptography missing
            self._secrets = None

    # ── credentials ────────────────────────────────────────────────────

    def list_accounts(self) -> list[dict]:
        """Public account list: never expose the encrypted credential blob."""
        safe: list[dict] = []
        for a in self._accounts:
            item = {k: v for k, v in a.items() if k != "password_enc"}
            item["has_credentials"] = bool(a.get("password_enc"))
            safe.append(item)
        return safe

    def set_credentials(self, account_id: str, password: str,
                        host: str = "") -> dict:
        """Store IMAP credentials encrypted at rest (never returned)."""
        if self._secrets is None:
            return {"ok": False, "reason": "cryptography package required"}
        account = self._find_account(account_id)
        if not account:
            return {"ok": False, "reason": "Account not found"}
        account["password_enc"] = self._secrets.encrypt(password)
        if host:
            account["host"] = host
        self._store.put_doc("email_accounts", account["id"], account)
        return {"ok": True}

    def _find_account(self, account_id: str) -> Optional[dict]:
        for a in self._accounts:
            if a["id"] == account_id:
                return a
        return None

    # ── ingest (IMAP + EML share this) ─────────────────────────────────

    def _ingest(self, parsed: dict, source: str) -> tuple[bool, dict]:
        """Persist a parsed message; dedup on Message-ID when present."""
        mid = parsed.get("message_id", "")
        if mid:
            for e in self._inbox:
                if e.get("message_id") == mid:
                    return False, e
        email = {
            "id": new_id("email"),
            "from": parsed.get("from", ""),
            "subject": parsed.get("subject", ""),
            "body": parsed.get("body", ""),
            "importance": parsed.get("importance", 0.5),
            "labels": parsed.get("labels", []),
            "read": False,
            "received_at": parsed.get("received_at") or _now_iso(),
            "message_id": mid,
            "source": source,
        }
        self._inbox.append(email)
        self._store.put_doc("emails", email["id"], email,
                            seq=self._store.next_seq("emails"))
        return True, email

    def ingest_eml(self, raw: bytes) -> dict:
        created, email = self._ingest(parse_eml(raw), source="eml")
        return {"ok": True, "created": created, "email": email}

    # ── IMAP ───────────────────────────────────────────────────────────

    def fetch_imap(self, account_id: str, folder: str = "INBOX",
                   limit: int = 20, host: str = "", port: int = 993) -> dict:
        """Poll a real IMAP mailbox. Credentials must be stored first."""
        account = self._find_account(account_id)
        if not account:
            return {"ok": False, "reason": "Account not found"}
        if self._secrets is None:
            return {"ok": False, "reason": "cryptography package required"}
        password_enc = account.get("password_enc", "")
        if not password_enc:
            return {"ok": False,
                    "reason": "No credentials stored — set them first via "
                              "POST /features/email/{id}/credentials"}
        password = self._secrets.decrypt(password_enc)
        if not password:
            return {"ok": False, "reason": "Stored credentials unreadable "
                                           "(wrong key or corrupt row)"}
        imap_host = host or account.get("host") or PROVIDER_HOSTS.get(
            account["email"].split("@")[-1].lower(), "")
        if not imap_host:
            return {"ok": False,
                    "reason": "Unknown provider — pass host explicitly"}

        created, skipped = 0, 0
        try:
            conn = imaplib.IMAP4_SSL(imap_host, port)
            try:
                conn.login(account["email"], password)
                conn.select(folder)
                status, data = conn.search(None, "ALL")
                if status != "OK":
                    return {"ok": False, "reason": f"IMAP search failed: {status}"}
                ids = (data[0] or b"").split()[-limit:]
                for num in ids:
                    fstatus, fdata = conn.fetch(num, "(RFC822)")
                    if fstatus != "OK" or not fdata or fdata[0] is None:
                        skipped += 1
                        continue
                    raw = fdata[0][1]
                    if isinstance(raw, tuple):
                        raw = raw[1]
                    was_new, _ = self._ingest(parse_eml(raw), source="imap")
                    created += 1 if was_new else 0
                    skipped += 0 if was_new else 1
            finally:
                try:
                    conn.logout()
                except Exception:  # noqa: BLE001
                    pass
        except imaplib.IMAP4.error as exc:
            return {"ok": False, "reason": f"IMAP error: {exc}"}
        except OSError as exc:
            return {"ok": False, "reason": f"Connection failed: {exc}"}

        account["last_fetch"] = _now_iso()
        account["last_fetch_new"] = created
        self._store.put_doc("email_accounts", account["id"], account)
        return {"ok": True, "fetched": len(ids), "created": created,
                "skipped": skipped}

    # ── rules engine (apply stored rules to a message) ─────────────────

    def apply_rules(self, email: dict) -> list[str]:
        """Run enabled rules against a message; returns applied rule names."""
        applied: list[str] = []
        for rule in self._rules:
            if not rule.get("enabled", True):
                continue
            cond = rule.get("condition", {})
            field = str(cond.get("field", "subject")).lower()
            operator = str(cond.get("op", "contains")).lower()
            value = str(cond.get("value", ""))
            text = str(email.get(field, "")).lower()
            if operator == "contains" and value.lower() not in text:
                continue
            if operator == "equals" and text != value.lower():
                continue
            if operator == "starts_with" and not text.startswith(value.lower()):
                continue
            action = rule.get("action", "")
            if action == "label":
                labels = email.setdefault("labels", [])
                tag = rule.get("action_config", {}).get("label", "rule")
                if tag not in labels:
                    labels.append(tag)
                self._store.put_doc("emails", email["id"], email)
            elif action == "mark_read":
                email["read"] = True
                self._store.put_doc("emails", email["id"], email)
            applied.append(rule.get("name", rule["id"]))
        return applied

    def delete_rule(self, rule_id: str) -> dict:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r["id"] != rule_id]
        self._store.delete_doc("email_rules", rule_id)
        return {"ok": True, "deleted": before - len(self._rules)}

    # ── deadline extraction from mail ──────────────────────────────────

    def extract_deadlines(self, deadline_svc: Optional["DeadlineService"] = None) -> dict:
        """Scan the inbox for explicit 'due YYYY-MM-DD' style dates.

        ``deadline_svc`` defaults to the module singleton; injectable so
        tests (or a multi-user setup) can use an isolated store.
        """
        if deadline_svc is None:
            from dash_backend.services.email_calendar_sync import deadline_service as svc  # noqa: PLC0415 — avoids import cycle at module load
            deadline_svc = svc

        created, scanned = 0, 0
        for e in self._inbox:
            scanned += 1
            text = f"{e.get('subject', '')}\n{e.get('body', '')}"
            match = _DUE_PATTERNS.search(text)
            if not match:
                continue
            was_new = deadline_svc.add_deadline(
                title=e.get("subject", "Deadline from email")[:120],
                due=match.group(1),
                source="email",
                source_id=e["id"],
                notes=e.get("from", ""),
            )
            created += 1 if was_new else 0
        return {"ok": True, "scanned": scanned, "created": created}


class ExtendedCalendarService(CalendarService):
    """CalendarService + ICS import + deadline views."""

    def import_ics(self, text: str, calendar_id: str = "0") -> dict:
        """Import VEVENTs; dedup on UID so re-importing a subscription is safe."""
        created, skipped = 0, 0
        known_uids = {e.get("external_id") for e in self._events
                      if e.get("external_id")}
        for ev in parse_ics(text):
            uid = ev["uid"] or hashlib.sha1(  # noqa: S324 — dedup key, not security
                f"{ev['title']}|{ev['start']}".encode()).hexdigest()
            if uid in known_uids:
                skipped += 1
                continue
            result = self.create_event(
                title=ev["title"] or "(untitled)",
                start=ev["start"],
                end=ev["end"] or ev["start"],
                calendar_id=calendar_id,
                description=ev["description"],
                location=ev["location"],
            )
            event = result.get("event", {})
            event["external_id"] = uid
            if ev["status"] == "cancelled":
                event["status"] = "cancelled"
            self._store.put_doc("calendar_events", event["id"], event)
            known_uids.add(uid)
            created += 1
        return {"ok": True, "created": created, "skipped": skipped}

    # ── deadlines ──────────────────────────────────────────────────────

    def get_deadlines(self, window_days: int = 30,
                      deadline_svc: Optional["DeadlineService"] = None) -> list[dict]:
        """Unified deadline view: deadline docs + deadline-ish calendar events."""
        if deadline_svc is None:
            from dash_backend.services.email_calendar_sync import deadline_service as svc  # noqa: PLC0415
            deadline_svc = svc

        items: list[dict] = []
        for dl in deadline_svc.list_deadlines():
            entry = dict(dl)
            entry.update(deadline_urgency(dl.get("due", "")))
            items.append(entry)

        now_iso = _now_iso()
        cutoff = (datetime.now(timezone.utc)
                  + timedelta(days=window_days)).isoformat()
        keywords = ("deadline", "due", "submit", "expires", "expiry",
                    "cutoff", "hand-in", "handin")
        for e in self._events:
            start = e.get("start", "")
            if not start or not (now_iso <= start <= cutoff):
                continue
            title = e.get("title", "").lower()
            if e.get("kind") == "deadline" or any(k in title for k in keywords):
                items.append({
                    "id": e["id"], "title": e.get("title", ""),
                    "due": start, "source": "calendar",
                    "source_id": e["id"], "notes": e.get("location", ""),
                    **deadline_urgency(start),
                })
        items.sort(key=lambda x: (_URGENCY_ORDER.get(x.get("urgency"), 9),
                                  x.get("due", "")))
        return items


class DeadlineService:
    """Persisted unified deadline list (docs: deadlines)."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        self._store = store if store is not None else LocalStore.instance()
        self._deadlines = self._store.list_docs("deadlines", newest_first=True)

    def add_deadline(self, title: str, due: str, source: str = "manual",
                     source_id: str = "", notes: str = "") -> bool:
        """Create a deadline; returns False (no-op) if source+source_id exists."""
        if source_id:
            for d in self._deadlines:
                if d.get("source") == source and d.get("source_id") == source_id:
                    return False
        deadline = {
            "id": new_id("dl"),
            "title": title,
            "due": due,
            "source": source,
            "source_id": source_id,
            "notes": notes,
            "created_at": _now_iso(),
        }
        self._deadlines.append(deadline)
        self._store.put_doc("deadlines", deadline["id"], deadline,
                            seq=self._store.next_seq("deadlines"))
        return True

    def list_deadlines(self) -> list[dict]:
        return list(self._deadlines)

    def delete_deadline(self, deadline_id: str) -> dict:
        before = len(self._deadlines)
        self._deadlines = [d for d in self._deadlines
                           if d["id"] != deadline_id]
        self._store.delete_doc("deadlines", deadline_id)
        return {"ok": True, "deleted": before - len(self._deadlines)}


# Extended singletons — rebind the base module's attributes so every lazy
# ``from dash_backend.services.email_calendar import email_service`` (all
# existing route handlers) picks up the extended behavior automatically.
email_service = ExtendedEmailService()  # noqa: F811 — intentional rebinding
calendar_service = ExtendedCalendarService()  # noqa: F811
deadline_service = DeadlineService()

import dash_backend.services.email_calendar as _base  # noqa: E402

_base.email_service = email_service
_base.calendar_service = calendar_service
