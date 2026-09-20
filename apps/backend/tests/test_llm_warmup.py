"""Warm-up module tests (#136): honest, hermetic, non-fatal by design."""
from __future__ import annotations

import asyncio

import pytest

from dash_backend.llm import warmup


@pytest.mark.asyncio
async def test_warmup_sends_tiny_generate(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self): pass

    class FakeClient:
        async def post(self, url, json=None):
            captured["url"] = url
            captured["payload"] = json
            return FakeResp()

    monkeypatch.setattr(
        "dash_backend.llm.service.get_shared_client", lambda timeout: FakeClient()
    )

    report = await warmup.warm_ollama_model()
    assert report["warmed"] is True
    assert report["error"] is None
    assert report["load_ms"] is not None
    assert captured["payload"]["num_predict"] == 1
    assert captured["payload"]["prompt"] == "hi"
    assert "keep_alive" in captured["payload"]


@pytest.mark.asyncio
async def test_warmup_never_raises_on_failure(monkeypatch):
    class FakeClient:
        async def post(self, url, json=None):
            raise RuntimeError("ollama down")

    monkeypatch.setattr(
        "dash_backend.llm.service.get_shared_client", lambda timeout: FakeClient()
    )
    report = await warmup.warm_ollama_model()
    assert report["warmed"] is False
    assert "ollama down" in report["error"]


@pytest.mark.asyncio
async def test_start_and_stop_schedule_cycle():
    task = warmup.start_model_warmup()
    if task is not None:  # inside a running loop it must schedule
        assert not task.done() or task.cancelled()
    warmup.stop_model_warmup()  # idempotent, must not raise
