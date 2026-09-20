"""Capability status (spec #89/#90).

One honest surface answering "what can you do right now?": each
subsystem reports operational / degraded / unavailable with its real
reason. Never silently pretends an action succeeded when the backing
provider is down — this is the endpoint the UI reads to show degraded
mode (spec #90) instead of failing mysteriously later.
"""
from __future__ import annotations

import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def _check_stt() -> dict[str, Any]:
    try:
        from dash_backend.voice import get_provider
        p = get_provider("speech")
        if p is None:
            return {"state": "unavailable", "reason": "no STT provider registered"}
        engine = getattr(p, "engine", "unknown")
        return {"state": "operational", "detail": f"engine: {engine}"}
    except Exception as exc:
        return {"state": "unavailable", "reason": str(exc)[:120]}


def _check_tts() -> dict[str, Any]:
    try:
        from dash_backend.voice import get_provider
        p = get_provider("tts")
        if p is None:
            return {"state": "unavailable", "reason": "no TTS provider registered"}
        return {"state": "operational", "detail": "piper available"}
    except Exception as exc:
        return {"state": "unavailable", "reason": str(exc)[:120]}


def _check_llm() -> dict[str, Any]:
    try:
        from dash_backend.llm.provider_manager import get_ollama_manager
        m = get_ollama_manager()
        model = m.get_configured_model()
        if not model:
            return {"state": "degraded",
                    "reason": "no model configured — chat falls back to commands"}
        return {"state": "operational", "detail": f"model: {model}"}
    except Exception as exc:
        return {"state": "degraded", "reason": f"LLM unreachable: {str(exc)[:100]} "
                "— deterministic commands and grounded answers still work"}


def _check_outbound() -> dict[str, Any]:
    try:
        return {"state": "degraded", "detail": (
            "outbound transport is the local draft provider — messages are "
            "prepared, approved and recorded, but NOT delivered externally "
            "(no email/VoIP provider credential on this machine)")}
    except Exception as exc:
        return {"state": "unavailable", "reason": str(exc)[:120]}


def _check_calendar() -> dict[str, Any]:
    try:
        from dash_backend.services.email_calendar import CalendarService
        svc = CalendarService()
        n = len(svc.get_events())
        return {"state": "degraded", "detail": (
            f"local calendar operational ({n} event(s)); external providers "
            "(Google/Outlook) not connected")}
    except Exception as exc:
        return {"state": "unavailable", "reason": str(exc)[:120]}


def _check_persistence() -> dict[str, Any]:
    try:
        from dash_backend.assistant.crm_store import get_crm_store
        store = get_crm_store()
        n = len(store.list_clients())
        return {"state": "operational", "detail": f"CRM store readable ({n} client(s))"}
    except Exception as exc:
        return {"state": "unavailable", "reason": f"store unreadable: {str(exc)[:100]}"}


def _check_wake_loop() -> dict[str, Any]:
    import os
    if os.getenv("DASH_WAKE_LOOP_ENABLED", "0") != "1":
        return {"state": "unavailable",
                "reason": "disabled (DASH_WAKE_LOOP_ENABLED=0) — set 1 to listen"}
    return {"state": "operational", "detail": "wake-word loop enabled"}


def _check_push_transport() -> dict[str, Any]:
    try:
        from dash_backend.services.mobile_companion import PushNotificationService
        return dict(PushNotificationService().transport_status())
    except Exception as exc:
        return {"state": "unavailable", "reason": str(exc)[:120]}


_CHECKS = {
    "speech_to_text": _check_stt,
    "text_to_speech": _check_tts,
    "language_model": _check_llm,
    "outbound_communication": _check_outbound,
    "calendar": _check_calendar,
    "persistence": _check_persistence,
    "wake_word_listening": _check_wake_loop,
    "push_transport": _check_push_transport,
}


def capability_status() -> dict[str, Any]:
    """Full capability report with an overall verdict. degraded_mode is
    True when something is degraded/unavailable — the UI shows it, the
    owner is never left guessing (spec #90)."""
    systems = {}
    for name, check in _CHECKS.items():
        try:
            systems[name] = check()
        except Exception as exc:  # a check must never crash the report
            logger.exception("capability check failed: %s", name)
            systems[name] = {"state": "unknown", "reason": str(exc)[:120]}

    states = {v.get("state", "unknown") for v in systems.values()}
    if "unavailable" in states or "degraded" in states:
        overall = "degraded"
        missing = sorted(k for k, v in systems.items()
                         if v.get("state") in ("degraded", "unavailable"))
        message = ("DASH is in degraded mode: " + ", ".join(missing) +
                   ". Everything else works, and nothing will pretend "
                   "otherwise.")
    else:
        overall = "operational"
        message = "All subsystems operational."
    return {"overall": overall, "degraded_mode": overall != "operational",
            "message": message, "systems": systems,
            "checked_at": time.time()}
