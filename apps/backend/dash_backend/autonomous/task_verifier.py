"""Deterministic step verification (decisions.md #90).

Every important step declares a completion condition; this module checks it
against the real system — no LLM judgement, no optimistic guessing. Outcomes:
VERIFIED / NOT_VERIFIED / FAILED. An unverifiable step is honestly reported
as NOT_VERIFIED, never silently passed.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger

from dash_backend.autonomous.task_state import TaskStep, Verification, VerificationStatus

logger = get_logger(__name__)

HTTP_TIMEOUT = 5.0


def _resolve_check_path(path: str) -> Path:
    """Resolve a verify-spec path with the SAME convention as the tools.

    Relative paths are sandbox-relative (decisions.md #91): create_file/
    write_file resolve args against DASH_FILES_SANDBOX, so a declared
    verification of "demo_folder/x.txt" must check the same location the
    tool wrote — not the server's cwd. Absolute paths pass through
    (verification is read-only, so wider reads are safe).
    """
    p = Path(path)
    if p.is_absolute() or not path:
        return p
    try:
        from dash_backend.tools.filesystem.filesystem_service import get_sandbox_root
        return get_sandbox_root() / path
    except Exception:
        return p


async def verify_step(step: TaskStep, tool_result: dict[str, Any] | None) -> Verification:
    """Run the step's declared ``verify`` check. Never raises.

    Steps WITHOUT a declared check get a derived, honestly-labelled check:
    the actual tool result is inspected — an error/failed result fails, an
    empty result is NOT_VERIFIED (nothing was observed), and a clean result
    passes as the weaker "tool reported success" verification. The agent
    still never *assumes* success: it reads the result it observed.
    """
    spec = step.verify
    if not spec or spec.get("type", "none") == "none":
        return _derive_default(tool_result)
    vtype = spec.get("type")
    try:
        if vtype == "file_exists":
            return _check_file_exists(spec.get("path", ""))
        if vtype == "file_contains":
            return _check_file_contains(spec.get("path", ""), spec.get("expect", ""))
        if vtype == "output_contains":
            return _check_output_contains(tool_result, spec.get("expect", ""))
        if vtype == "exit_code_zero":
            return _check_exit_code(tool_result)
        if vtype == "http_ok":
            return await _check_http_ok(spec.get("url", ""))
        return Verification(
            status=VerificationStatus.FAILED,
            detail=f"unknown verify type: {vtype}",
        )
    except Exception as exc:
        return Verification(status=VerificationStatus.FAILED, detail=f"verifier crashed: {exc}")


def _derive_default(tool_result: dict[str, Any] | None) -> Verification:
    """Default check when the plan declares no completion condition."""
    if not tool_result:
        return Verification(
            status=VerificationStatus.NOT_VERIFIED,
            detail="no completion condition declared and no tool result observed",
        )
    if "error" in tool_result or tool_result.get("status") in ("error", "failed"):
        detail = str(tool_result.get("error") or tool_result.get("status"))[:200]
        return Verification(status=VerificationStatus.FAILED, detail=f"tool reported failure: {detail}")
    return Verification(
        status=VerificationStatus.VERIFIED,
        detail="tool reported success (no stronger check declared)",
    )


def _check_file_exists(path: str) -> Verification:
    p = _resolve_check_path(path)
    if path and p.is_file():
        return Verification(status=VerificationStatus.VERIFIED, detail=f"file exists: {path}")
    return Verification(status=VerificationStatus.NOT_VERIFIED, detail=f"file missing: {path}")


def _check_file_contains(path: str, expect: str) -> Verification:
    p = _resolve_check_path(path)
    if not path or not p.is_file():
        return Verification(status=VerificationStatus.NOT_VERIFIED, detail=f"file missing: {path}")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return Verification(status=VerificationStatus.FAILED, detail=f"unreadable: {exc}")
    if expect and expect in content:
        return Verification(status=VerificationStatus.VERIFIED, detail=f"'{expect}' present in {path}")
    return Verification(
        status=VerificationStatus.NOT_VERIFIED,
        detail=f"'{expect}' not found in {path}",
    )


def _check_output_contains(tool_result: dict[str, Any] | None, expect: str) -> Verification:
    text = _result_text(tool_result)
    if expect and expect.lower() in text.lower():
        return Verification(status=VerificationStatus.VERIFIED, detail=f"output contains '{expect}'")
    return Verification(
        status=VerificationStatus.NOT_VERIFIED,
        detail=f"output missing '{expect}' (got: {text[:120]})",
    )


def _check_exit_code(tool_result: dict[str, Any] | None) -> Verification:
    if tool_result is None:
        return Verification(status=VerificationStatus.NOT_VERIFIED, detail="no tool result")
    for key in ("exit_code", "returncode", "code"):
        v = tool_result.get(key)
        if isinstance(v, int):
            if v == 0:
                return Verification(status=VerificationStatus.VERIFIED, detail="exit code 0")
            return Verification(status=VerificationStatus.FAILED, detail=f"exit code {v}")
    text = _result_text(tool_result).lower()
    if "error" in text or "failed" in text:
        return Verification(status=VerificationStatus.FAILED, detail="result reports error")
    return Verification(status=VerificationStatus.NOT_VERIFIED, detail="no exit code in result")


async def _check_http_ok(url: str) -> Verification:
    if not url:
        return Verification(status=VerificationStatus.FAILED, detail="no url given")
    def _fetch() -> int:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return int(resp.status)
    try:
        status = await asyncio.to_thread(_fetch)
        if 200 <= status < 300:
            return Verification(status=VerificationStatus.VERIFIED, detail=f"HTTP {status} from {url}")
        return Verification(status=VerificationStatus.NOT_VERIFIED, detail=f"HTTP {status} from {url}")
    except Exception as exc:
        return Verification(status=VerificationStatus.FAILED, detail=f"request failed: {exc}")


def _result_text(result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    parts = []
    for key in ("output", "stdout", "summary", "result", "message", "content"):
        v = result.get(key)
        if isinstance(v, str):
            parts.append(v)
    if not parts:
        try:
            parts.append(json.dumps(result, default=str))
        except (TypeError, ValueError):
            parts.append(str(result))
    return " ".join(parts)
