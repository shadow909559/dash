"""Meeting intelligence (spec #25-#32/#79-#80/#141).

Meeting lifecycle: scheduled → live (transcript ingested turn by turn,
extraction runs incrementally) → completed (summary + action items +
requirement updates, all linked back to client/project). Two modes:
LISTEN_ONLY / ASSISTED (private help to the owner, never visible to
participants) and AUTHORIZED_PARTICIPANT (DASH may speak, still gated
by the authority engine). Private alerts to the owner go through the
existing NotificationService — never to the meeting.

Transcript ingestion is REALTIME-SAFE: extraction is deterministic and
fast (no LLM on the hot path); LLM summarization happens only at
meeting close.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import time
from typing import Any

from dash_backend.assistant.crm_store import CrmStore, get_crm_store
from dash_backend.assistant.requirement_intel import (
    ExtractedItem,
    detect_requirement_change,
    extract_items,
    summarize_extraction,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

MODES = ("listen_only", "assisted", "authorized_participant")


class MeetingEngine:
    """Stateful meeting session bound to a persistent meeting record."""

    def __init__(self, store: CrmStore | None = None,
                 notifier=None, audit=None,
                 local_hour_fn=None):
        self._store = store or get_crm_store()
        self._notifier = notifier
        self._audit = audit
        self._local_hour_fn = local_hour_fn  # injectable for tests
        self._live: dict[str, dict[str, Any]] = {}
        self._pending: list[asyncio.Task] = []

    # ── Preparation (spec #26) ─────────────────────────────────────────

    def prepare_briefing(self, meeting_id: str) -> dict[str, Any] | None:
        meeting = self._store.get_meeting(meeting_id)
        if meeting is None:
            return None
        client = (self._store.get_client(meeting["client_id"])
                  if meeting.get("client_id") else None)
        project = (self._store.get_project(meeting["project_id"])
                   if meeting.get("project_id") else None)
        client_id = client["id"] if client else None
        requirements = self._store.list_requirements(client_id=client_id)
        open_reqs = [r for r in requirements
                     if r["status"] in ("detected", "clarification_needed",
                                        "confirmed", "planned", "approved",
                                        "in_progress")]
        comms = self._store.list_communications(client_id=client_id)
        last_comm = comms[-1] if comms else None
        briefing = {
            "meeting": meeting["title"],
            "client": client["name"] if client else None,
            "project": project["name"] if project else None,
            "project_status": project.get("status") if project else None,
            "open_requirements": [
                {"text": r["text"], "status": r["status"],
                 "confidence": r["confidence"]}
                for r in open_reqs[-10:]
            ],
            "pending_decisions": [
                r["text"] for r in requirements if r["category"] == "decision"
                and r["status"] in ("detected", "clarification_needed")
            ],
            "last_communication": (
                {"direction": last_comm["direction"],
                 "summary": last_comm["summary"][:200],
                 "when": last_comm["created_at"]}
                if last_comm else None
            ),
            "questions_to_ask": self._suggest_questions(open_reqs),
            "prepared_at": time.time(),
        }
        self._store.update_meeting(meeting_id, {"briefing": briefing})
        return briefing

    @staticmethod
    def _suggest_questions(open_reqs: list[dict[str, Any]]) -> list[str]:
        questions: list[str] = []
        for r in open_reqs:
            if r["status"] == "clarification_needed" or r.get("history", [{}])[-1].get("status") == "clarification_needed":
                questions.append(f"Clarify: {r['text'][:100]}")
        if not questions:
            questions.append("Confirm current priorities and the next deadline")
        return questions[:5]

    # ── Live meeting (spec #27-#30) ────────────────────────────────────

    def start_live(self, meeting_id: str, mode: str = "listen_only") -> dict[str, Any] | None:
        if mode not in MODES:
            raise ValueError(f"invalid meeting mode: {mode}")
        meeting = self._store.get_meeting(meeting_id)
        if meeting is None:
            return None
        self._store.update_meeting(meeting_id, {"status": "live", "mode": mode})
        self._live[meeting_id] = {
            "items": [], "turns": 0, "started_at": time.time(),
            "last_topics": [],
        }
        try:
            from dash_backend.assistant.presence import get_presence_engine
            get_presence_engine().claim(
                "meetings", "in_meeting",
                detail=f"{meeting.get('title', meeting_id)} ({mode})",
                meta={"meeting_id": meeting_id, "mode": mode},
            )
        except Exception:
            pass
        return meeting

    def ingest_turn(
        self, meeting_id: str, speaker: str, text: str,
        ts: float | None = None,
    ) -> dict[str, Any]:
        """One transcript turn → extraction + scope-change detection.

        Deterministic only — never blocks the audio path (spec #46).
        Returns what the UI/live panel should show for this turn.
        """
        session = self._live.get(meeting_id)
        meeting = self._store.get_meeting(meeting_id)
        if session is None or meeting is None:
            raise ValueError(f"meeting {meeting_id} is not live")
        when = ts if ts is not None else time.time()
        self._store.update_meeting(meeting_id, {"transcript": None})  # no-op guard
        items: list[ExtractedItem] = extract_items(text, speaker=speaker, ts=when)
        session["turns"] += 1
        session["items"].extend(items)

        alerts: list[str] = []
        scope_change = None
        if items:
            existing = self._store.list_requirements(
                client_id=meeting.get("client_id"))
            for it in items:
                if it.category == "requirement":
                    change = detect_requirement_change(
                        it.text, [r for r in existing if r["id"]]
                    )
                    if change:
                        scope_change = change
                        alerts.append(
                            "Possible requirement change: "
                            f"\"{it.text[:80]}\" conflicts with an earlier "
                            "requirement. Owner review needed."
                        )
                if it.category == "commitment" and meeting.get("mode") != "authorized_participant":
                    alerts.append(
                        f"Commitment language detected from {speaker}: "
                        f"\"{it.text[:80]}\" — no commitment was made."
                    )
        # Persist transcript turn (bounded to the store write)
        meeting_rec = self._store.get_meeting(meeting_id)
        transcript = (meeting_rec.get("transcript") or [])
        transcript.append({"speaker": speaker, "text": text[:500], "ts": when})
        self._store.update_meeting(meeting_id, {"transcript": transcript[-400:]})
        self._push_turn_alerts(meeting_id, alerts)

        return {
            "turn": session["turns"],
            "items": [it.to_dict() for it in items],
            "alerts": alerts,
            "scope_change": (
                {"prior": scope_change["prior"]["id"],
                 "prior_text": scope_change["prior"]["text"][:120]}
                if scope_change else None
            ),
        }

    def _push_turn_alerts(self, meeting_id: str, alerts: list[str]) -> None:
        """Best-effort WS push of live meeting alerts (decisions.md #92).
        Private to the owner — never rendered into the meeting itself."""
        if not alerts:
            return
        try:
            from dash_backend.assistant.push import push_assistant_event
            push_assistant_event(None, {
                "type": "meeting.alert", "meeting_id": meeting_id,
                "alerts": alerts,
            })
        except Exception:
            logger.exception("assistant push failed for meeting alerts")
        try:
            from dash_backend.assistant.mobile_bridge import push_meeting_alert
            push_meeting_alert(meeting_id, alerts)
        except Exception:
            logger.exception("mobile push failed for meeting alerts")

    async def notify_owner_private(self, meeting_id: str, message: str,
                                   urgency: str = "important") -> None:
        """Private owner alert — desktop notification, never the meeting."""
        if self._notifier is not None:
            try:
                await self._notifier.show(
                    title=f"DASH ({urgency}) — private",
                    message=message[:180],
                )
            except Exception:
                logger.exception("private owner notification failed")

    def end_meeting(self, meeting_id: str) -> dict[str, Any] | None:
        """Close the meeting: summary + requirements + action items (spec #31/#32)."""
        session = self._live.pop(meeting_id, None)
        meeting = self._store.get_meeting(meeting_id)
        if meeting is None:
            return None
        try:
            if not self._live:  # no other meetings live
                from dash_backend.assistant.presence import get_presence_engine
                get_presence_engine().release("meetings")
        except Exception:
            pass
        items = session["items"] if session else []
        agg = summarize_extraction(items)
        transcript = meeting.get("transcript") or []

        summary = {
            "turns": len(transcript),
            "participants": sorted({t["speaker"] for t in transcript}),
            "counts": agg["counts"],
            "needs_clarification": agg["needs_clarification"],
            "requirements_detected": [
                it.to_dict() for it in items if it.category == "requirement"
            ],
            "decisions": [
                it.to_dict() for it in items if it.category == "decision"
            ],
            "questions": [
                it.to_dict() for it in items if it.category == "question"
            ],
            "commitments_flagged": [
                it.to_dict() for it in items if it.category == "commitment"
            ],
        }
        self._store.update_meeting(meeting_id, {
            "status": "completed", "summary": summary,
        })

        # Persist detected requirements with honest status (never confirmed
        # automatically — spec #17/#48).
        client_id = meeting.get("client_id")
        project_id = meeting.get("project_id")
        for it in items:
            if it.category == "requirement":
                status = ("clarification_needed" if it.ambiguity
                          else "detected")
                self._store.add_requirement(
                    client_id=client_id, project_id=project_id,
                    text=it.text, status=status,
                    source=f"meeting:{meeting_id}",
                    confidence=it.confidence,
                )
        # Owner action items ("Shadow will send...") — reminders for the owner.
        for it in items:
            if it.category == "commitment" and (it.owner_of_commitment or "").lower() in ("shadow", "owner", "i", "we"):
                self._store.add_action_item(
                    text=it.text, owner="Shadow",
                    due=it.deadline_hint, source=f"meeting:{meeting_id}",
                    meeting_id=meeting_id, client_id=client_id,
                )
        if session is not None:
            # §24 (decisions.md #127): the results proactively reach the
            # owner — only for meetings that actually went live (a re-end
            # of an already-closed meeting never re-notifies).
            self._deliver_summary_contact(meeting_id, meeting, summary)
        return summary

    def _deliver_summary_contact(self, meeting_id: str,
                                 meeting: dict[str, Any],
                                 summary: dict[str, Any]) -> None:
        """Post-meeting summary → owner via the shared #119 policy.

        A summary is "important" — never urgent/critical — so by policy it
        cannot interrupt by voice or phone; it reaches the ws always and
        the desktop when hours/floor allow. Failure to deliver must never
        fail the meeting close itself.
        """
        try:
            item: dict[str, Any] = {
                "kind": "meeting_summary",
                "meeting_id": meeting_id,
                "text": (
                    f"Meeting '{meeting.get('title', meeting_id)}' ended — "
                    f"{len(summary.get('requirements_detected', []))} requirement(s), "
                    f"{len(summary.get('decisions', []))} decision(s), "
                    f"{len(summary.get('commitments_flagged', []))} commitment(s) "
                    "flagged. Summary is ready."),
                "urgency": "important",
            }
            channels: list[str] = ["ws", "digest"]
            try:
                from dash_backend.assistant.urgency import route_contact
                hour_fn = self._local_hour_fn or (lambda: _dt.datetime.now().hour)
                decision = route_contact(
                    item["urgency"], prefs=self._store.get_preferences(),
                    local_hour=hour_fn)
                channels = list(decision.channels)
            except Exception:
                logger.exception("meeting summary routing failed")
            item["channels"] = channels

            from dash_backend.assistant.push import push_assistant_event
            push_assistant_event(None, {
                "type": "proactive.digest", "items": [item]})

            if "desktop" in channels and self._notifier is not None:
                try:
                    loop = asyncio.get_running_loop()
                    self._pending.append(loop.create_task(
                        self._notifier.show(
                            title="DASH — meeting summary",
                            message=item["text"][:180])))
                except RuntimeError:
                    pass  # no running loop (sync test/shutdown): ws already delivered
            if self._audit is not None:
                try:
                    self._audit.log(
                        event_type="meeting_summary_contact",
                        action=meeting_id,
                        category="assistant",
                        status="notified",
                        details={"channels": channels},
                    )
                except Exception:
                    logger.exception("meeting summary audit failed")
        except Exception:
            logger.exception("meeting summary owner contact failed")


_engine: MeetingEngine | None = None


def get_meeting_engine() -> MeetingEngine:
    global _engine
    if _engine is None:
        _engine = MeetingEngine()
    return _engine
