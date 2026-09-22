"""Pin the clipboard-command fix (2026-09-22).

The command interceptor called ``ClipboardService.write()`` — a method that
never existed (the real API is ``copy()``), so every voice/chat clipboard
command failed into the honest-error path ("Clipboard write failed:
'ClipboardService' object has no attribute 'write'"). The #143 phantom-call
checker excludes instance-attribute calls by design, so this regression pin
is the guard: the write handler must go through the REAL service method and
report success only when the service succeeds.
"""

from __future__ import annotations

import asyncio
from typing import Any

import dash_backend.services.command_interceptor as ci
from dash_backend.services.clipboard import ClipboardService


def test_clipboard_write_uses_the_real_copy_method(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_copy(self: ClipboardService, text: str) -> dict[str, Any]:
        calls.append(text)
        return {"summary": f"Copied {len(text)} chars to clipboard"}

    monkeypatch.setattr(ClipboardService, "copy", fake_copy)

    result = asyncio.run(ci._execute_clipboard_write("hello dash"))

    assert calls == ["hello dash"]
    assert result["action"] == "clipboard_write"
    assert "error" not in result
    assert "hello dash" in result["summary"]


def test_clipboard_write_reports_service_failure_honestly(monkeypatch) -> None:
    async def boom(self: ClipboardService, text: str) -> dict[str, Any]:
        raise RuntimeError("OpenClipboard failed")

    monkeypatch.setattr(ClipboardService, "copy", boom)

    result = asyncio.run(ci._execute_clipboard_write("hello dash"))

    assert result["action"] == "clipboard_write"
    assert "OpenClipboard failed" in result["error"]
    assert "failed" in result["summary"].lower()


def test_clipboard_service_has_no_write_method() -> None:
    # The service API is copy/paste/read/clear; guard against someone
    # "fixing" the handler by adding a fake write() to the service instead
    # of using the real method.
    assert not hasattr(ClipboardService, "write")
    assert hasattr(ClipboardService, "copy")
