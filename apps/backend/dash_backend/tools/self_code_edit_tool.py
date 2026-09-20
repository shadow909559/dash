"""Test-gated self-code-edit tool (docs/ROADMAP.md Phase 2, decisions.md #59).

Lets DASH edit his own source code under a gate that makes destruction
impossible-by-construction:

1. GIT CHECKPOINT FIRST, ALWAYS — any uncommitted changes to the target
   file are committed on the CURRENT branch (never a branch switch: this
   is the user's live checkout) tagged with a checkpoint message.
2. APPLY the requested edit (exact-match replacement, must be unambiguous).
3. RUN THE TEST GATE — a real pytest invocation against the backend suite.
4. AUTO-ROLLBACK if the gate is red: the file's pre-edit content (held in
   memory) is restored, so ONLY the edited file changes — unrelated dirty
   state in the user's checkout is never touched.

Honest limits (also stated in docs/ROADMAP.md Phase 2): the gate is the
test suite, not wisdom — coverage gaps are the real risk. Path guardrails
(``protected_path_markers``) block the edits that would disable the gate
itself (test files, security/auth code, this module, audit/identity).
"""
from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, PermissionLevel, ToolContext, ToolParameter
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


def _repo_root() -> Path:
    """The git working tree DASH edits (the dash/ checkout root)."""
    import os

    override = os.environ.get("DASH_SELF_EDIT_ROOT")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    return here.parents[3]


class SelfCodeEditTool(BaseTool):
    """Propose an edit → checkpoint → apply → test gate → keep-or-rollback."""

    name = "self_code_edit"
    description = (
        "Edit DASH's own source code SAFELY: a git checkpoint of the target "
        "file is taken first, your edit is applied, the backend test suite "
        "runs as a gate, and the edit is automatically rolled back if any "
        "test fails. Use for self-improvements you can justify. Files under "
        "tests/, auth/, security/, and this tool's own module are protected "
        "and cannot be edited here."
    )
    parameters = [
        ToolParameter(
            "path",
            "File to edit, relative to the repo root (e.g. "
            "apps/backend/dash_backend/services/foo.py).",
            type="string",
            required=True,
        ),
        ToolParameter(
            "old_string",
            "Exact text to replace (must match the file precisely, and in "
            "exactly one place).",
            type="string",
            required=True,
        ),
        ToolParameter(
            "new_string",
            "Replacement text. Pass empty string to delete the old text.",
            type="string",
            required=True,
        ),
        ToolParameter(
            "reason",
            "Why this edit improves DASH. Recorded in the audit log.",
            type="string",
            required=True,
        ),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "self"

    # Edits that could disable the gate itself or break identity are
    # refused outright — the gate must not be able to remove its own gate.
    protected_path_markers = (
        "tests/", "test_", "conftest",
        "security", "auth", "identity",
        "self_code_edit_tool", "self_heal",
        "audit", "secrets",
    )

    GATE_TIMEOUT_S = 900

    def __init__(self, repo_root: Optional[Path] = None,
                 gate_command: Optional[list[str]] = None) -> None:
        self._repo_root = Path(repo_root) if repo_root else _repo_root()
        self._gate_command = gate_command
        self._history: list[dict] = []

    # ── git plumbing (blocking — always called via to_thread) ──────

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self._repo_root, capture_output=True, text=True,
            check=check, timeout=60,
        )

    def _commit(self, message: str, path_rel: str) -> bool:
        """Commit the target file. Repos without user.name/email configured
        fall back to an explicit DASH identity so the safety pipeline can
        never be blocked by git config — checkpointing is the safety net."""
        self._git("add", "--", path_rel)
        proc = self._git("commit", "-m", message, "--no-verify", check=False)
        if proc.returncode == 0:
            return True
        proc = self._git(
            "-c", "user.name=DASH Self-Edit",
            "-c", "user.email=dash-self-edit@localhost",
            "commit", "-m", message, "--no-verify", check=False,
        )
        return proc.returncode == 0

    def _checkpoint(self, path_rel: str) -> dict:
        """Commit the target file's uncommitted state (if any) on the
        current branch so the pre-edit content is recoverable in git."""
        dirty = self._git("status", "--porcelain", "--", path_rel).stdout.strip()
        info: dict[str, Any] = {"was_dirty": bool(dirty), "committed": False}
        if dirty:
            info["committed"] = self._commit(
                f"checkpoint before self-edit of {path_rel}", path_rel
            )
        info["pre_edit_commit"] = self._git("rev-parse", "HEAD").stdout.strip()
        return info

    def _rollback(self, target: Path, pre_edit_content: str, path_rel: str) -> None:
        """Restore ONLY the edited file. Never touches other paths; never
        raises past a warning — a failed rollback must at least be loud."""
        try:
            target.write_text(pre_edit_content, encoding="utf-8")
            # Belt and braces: also discard any index diff for this file.
            self._git("checkout", "--", path_rel)
        except Exception:
            logger.exception(
                "Self-edit rollback failed for %s — the checkpoint commit "
                "on the current branch still holds the pre-edit content",
                path_rel,
            )

    # ── the test gate ──────────────────────────────────────────────

    def _gate_cwd(self) -> Path:
        backend = self._repo_root / "apps" / "backend"
        return backend if (backend / "tests").is_dir() else self._repo_root

    def _run_gate(self) -> dict:
        """The gate is a REAL pytest run of the backend suite. A slow gate
        is the price of a safe one; the command is recorded either way."""
        cmd = self._gate_command or [
            "python", "-m", "pytest", "tests", "-q",
            "--ignore=tests/test_api_sweep.py",
            "-x", "--timeout=120", "-p", "no:cacheprovider",
        ]
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd, cwd=self._gate_cwd(),
                capture_output=True, text=True, timeout=self.GATE_TIMEOUT_S,
            )
            tail = "\n".join((proc.stdout or "").splitlines()[-25:])
            return {
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "command": " ".join(cmd),
                "output_tail": tail,
                "duration_s": round(time.perf_counter() - started, 1),
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False, "exit_code": None, "command": " ".join(cmd),
                "output_tail": f"gate timed out after {self.GATE_TIMEOUT_S}s",
                "duration_s": round(time.perf_counter() - started, 1),
            }

    # ── BaseTool API ───────────────────────────────────────────────

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_rel = str(kwargs.get("path", "")).strip().replace("\\", "/")
        old_string = str(kwargs.get("old_string", ""))
        new_string = str(kwargs.get("new_string", ""))
        reason = str(kwargs.get("reason", "")).strip()

        if not path_rel or old_string == new_string:
            return ToolResult(
                tool_name=self.name, status=ToolStatus.ERROR,
                error_message="path required and old_string must differ from new_string",
            )
        if not reason:
            return ToolResult(
                tool_name=self.name, status=ToolStatus.ERROR,
                error_message="a reason is required — self-edits are recorded",
            )
        normalized = path_rel.lstrip("./")
        if any(marker in normalized for marker in self.protected_path_markers):
            return ToolResult(
                tool_name=self.name, status=ToolStatus.REJECTED,
                summary="edit refused: protected path",
                output={"path": normalized,
                        "reason": "the test gate must not be able to disable itself"},
            )
        target = self._repo_root / normalized
        if not target.is_file():
            return ToolResult(
                tool_name=self.name, status=ToolStatus.ERROR,
                error_message=f"file not found: {normalized}",
            )

        # Everything blocking happens in a worker thread.
        try:
            outcome = await asyncio.to_thread(
                self._edit_sync, normalized, old_string, new_string, reason
            )
        except Exception as exc:
            logger.exception("Self-edit pipeline crashed")
            outcome = {"path": normalized, "ok": False,
                       "summary": f"self-edit pipeline failed before completion: {exc}"}
        status = ToolStatus.SUCCESS if outcome["ok"] else ToolStatus.ERROR
        return ToolResult(
            tool_name=self.name, status=status,
            summary=outcome["summary"],
            output=outcome,
            error_message="" if outcome["ok"] else outcome["summary"],
        )

    # ── synchronous edit pipeline ──────────────────────────────────

    def _edit_sync(self, path_rel: str, old_string: str, new_string: str,
                   reason: str) -> dict:
        outcome: dict[str, Any] = {"path": path_rel, "reason": reason}
        started = time.perf_counter()
        target = self._repo_root / path_rel

        try:
            source = target.read_text(encoding="utf-8")
        except OSError as exc:
            return {**outcome, "ok": False, "summary": f"unreadable: {exc}"}

        count = source.count(old_string)
        if count == 0:
            outcome.update(ok=False,
                           summary="old_string not found in file — nothing changed")
            self._record(outcome)  # failed attempts belong to the track record
            return outcome
        if count > 1:
            outcome.update(ok=False,
                           summary=f"old_string matches {count} places — aborting "
                                   f"(self-edits must be unambiguous; include more "
                                   f"surrounding context)")
            self._record(outcome)
            return outcome

        outcome["checkpoint"] = self._checkpoint(path_rel)
        target.write_text(source.replace(old_string, new_string, 1),
                          encoding="utf-8")

        gate = self._run_gate()
        outcome["gate"] = gate
        if gate["ok"]:
            committed = self._commit(f"self-edit {path_rel}: {reason[:80]}", path_rel)
            sha = (self._git("rev-parse", "--short", "HEAD").stdout.strip()
                   if committed else "(uncommitted)")
            outcome.update(ok=True, summary=(
                f"edit applied and verified by the test gate in "
                f"{gate['duration_s']}s (commit {sha})"
            ))
        else:
            self._rollback(target, source, path_rel)
            outcome.update(ok=False, summary=(
                f"test gate FAILED after {gate['duration_s']}s — edit rolled "
                f"back; the file is byte-identical to before the edit"
            ))
        outcome["duration_s"] = round(time.perf_counter() - started, 1)

        self._record(outcome)
        return outcome

    def _record(self, outcome: dict) -> None:
        self._history.append(outcome)
        del self._history[:-20]
        try:
            from dash_backend.services.audit_logs import get_audit_service

            get_audit_service().log(
                event_type="SELF_CODE_EDIT",
                action=outcome["path"],
                status="ok" if outcome["ok"] else "rolled_back",
                details={
                    "reason": outcome["reason"],
                    "gate_exit": outcome.get("gate", {}).get("exit_code"),
                    "checkpoint": outcome.get("checkpoint", {}).get("pre_edit_commit", ""),
                },
            )
        except Exception:
            logger.debug("Self-edit audit entry failed", exc_info=True)

    def get_history(self) -> list[dict]:
        """Recent self-edit attempts, including rolled-back ones — a
        self-improving agent must be able to show its own track record."""
        return list(self._history)
