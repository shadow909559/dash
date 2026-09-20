"""Startup model warm-up (#136).

Ollama only loads a model's weights on the first request after boot (or after
keep_alive expiry). On this machine that first token costs ~21 s with
dash-finetuned — paid by the FIRST user interaction after every backend
restart. Warm-up moves that cost into boot, where the user isn't waiting.

Honest semantics:
- Runs in the background after the server starts accepting requests; boot is
  never blocked.
- One tiny generate (num_predict=1) loads the weights; any failure is logged
  and ignored — warm-up must never take the backend down.
- If the configured model is not yet pulled, this is a no-op (the pull is the
  user's explicit action, not ours).
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


async def warm_ollama_model() -> dict[str, Any]:
    """Load the configured Ollama model into memory (num_predict=1).

    Returns a small honest report: {"warmed": bool, "model": str,
    "load_ms": float|None, "error": str|None}.
    """
    settings = get_settings()
    model = settings.ai_model or settings.ollama_model
    if not model:
        return {"warmed": False, "model": "", "load_ms": None, "error": "no model configured"}

    payload = {
        "model": model,
        "prompt": "hi",
        "stream": False,
        "num_predict": 1,
        "keep_alive": settings.ollama_keep_alive or "30m",
    }
    if not settings.ollama_thinking:
        payload["think"] = False
    options: dict[str, Any] = {}
    if settings.ollama_num_thread:
        options["num_thread"] = settings.ollama_num_thread
    if options:
        payload["options"] = options

    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    t0 = time.perf_counter()
    try:
        from dash_backend.llm.service import get_shared_client

        client = get_shared_client(120.0)
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        load_ms = (time.perf_counter() - t0) * 1000
        logger.info("Warm-up: model '%s' resident in %.0f ms", model, load_ms)
        return {"warmed": True, "model": model, "load_ms": round(load_ms, 1), "error": None}
    except Exception as exc:
        logger.warning("Warm-up failed for model '%s': %s", model, exc)
        return {"warmed": False, "model": model, "load_ms": None, "error": str(exc)}


_warmup_task: asyncio.Task | None = None


def start_model_warmup() -> asyncio.Task | None:
    """Schedule background warm-up; returns the task (for tests/cancel)."""
    global _warmup_task
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return None  # no running loop (e.g. pure import) — skip silently
    _warmup_task = asyncio.ensure_future(_run_and_log())
    return _warmup_task


async def _run_and_log() -> None:
    # Yield once so the server finishes binding before we hog the event loop.
    await asyncio.sleep(0)
    report = await warm_ollama_model()
    if not report["warmed"]:
        # Non-fatal by design; details already logged.
        pass


def stop_model_warmup() -> None:
    global _warmup_task
    if _warmup_task is not None and not _warmup_task.done():
        _warmup_task.cancel()
    _warmup_task = None
