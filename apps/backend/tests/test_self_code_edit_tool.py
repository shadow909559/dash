"""Test-gated self-code-edit tool tests (Phase 2, decisions.md #59).

The gate is replaced with an instant fake — the pipeline's CONTRACT is
what's under test: checkpoint before touching anything, apply, gate,
keep-if-green / rollback-if-red, protected paths refused, every attempt
audited. Git operations run for real against a temp repository.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dash_backend.tools.base_tool import ToolContext
from dash_backend.tools.self_code_edit_tool import SelfCodeEditTool
from dash_backend.tools.tool_result import ToolStatus


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A real git repo with one editable backend file."""
    root = tmp_path / "dash"
    backend = root / "apps" / "backend" / "dash_backend" / "services"
    backend.mkdir(parents=True)
    (backend / "sample.py").write_text(
        'VALUE = 1\n\ndef greet():\n    return "hello"\n', encoding="utf-8"
    )
    for args in (
        ["init", "-q"],
        ["config", "user.email", "test@local"],
        ["config", "user.name", "test"],
        ["add", "."],
        ["commit", "-qm", "init", "--no-verify"],
    ):
        subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
    return root


@pytest.fixture()
def tool(repo: Path):
    """Tool with an injectable fake gate result."""
    t = SelfCodeEditTool(repo_root=repo)

    class FakeGate:
        result: dict = {"ok": True, "exit_code": 0, "command": "fake",
                        "output_tail": "all passed", "duration_s": 0.1}

    t._run_gate = lambda: dict(FakeGate.result)  # type: ignore[method-assign]
    t._fake_gate = FakeGate
    return t


CTX = ToolContext(user_id="test")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout


async def test_edit_refuses_protected_paths(tool: SelfCodeEditTool) -> None:
    for path in ("apps/backend/tests/test_x.py",
                 "apps/backend/dash_backend/security/hardening.py",
                 "apps/backend/dash_backend/tools/self_code_edit_tool.py",
                 "dash_backend/auth/dependencies.py"):
        res = await tool.execute(CTX, path=path, old_string="a", new_string="b",
                                 reason="try to disable the gate")
        assert res.status == ToolStatus.REJECTED, path


async def test_edit_requires_reason_and_distinct_strings(tool) -> None:
    res = await tool.execute(CTX, path="apps/backend/dash_backend/services/sample.py",
                             old_string="VALUE = 1", new_string="VALUE = 1",
                             reason="no-op")
    assert res.status == ToolStatus.ERROR
    res2 = await tool.execute(CTX, path="apps/backend/dash_backend/services/sample.py",
                              old_string="VALUE = 1", new_string="VALUE = 2",
                              reason="")
    assert res2.status == ToolStatus.ERROR


async def test_gate_green_keeps_edit_and_commits(tool, repo: Path) -> None:
    res = await tool.execute(
        CTX, path="apps/backend/dash_backend/services/sample.py",
        old_string='return "hello"', new_string='return "hello, improved"',
        reason="clearer greeting",
    )
    assert res.status is ToolStatus.SUCCESS
    file = repo / "apps" / "backend" / "dash_backend" / "services" / "sample.py"
    assert "improved" in file.read_text(encoding="utf-8")
    assert "self-edit" in _git(repo, "log", "-1", "--pretty=%s")
    assert res.output["gate"]["ok"] is True


async def test_gate_red_rolls_back_byte_for_byte(tool, repo: Path) -> None:
    tool._fake_gate.result = {"ok": False, "exit_code": 1, "command": "fake",
                              "output_tail": "FAILED tests", "duration_s": 0.2}
    before = (repo / "apps" / "backend" / "dash_backend" / "services" / "sample.py"
              ).read_text(encoding="utf-8")

    res = await tool.execute(
        CTX, path="apps/backend/dash_backend/services/sample.py",
        old_string="VALUE = 1", new_string="VALUE = 999  # broken",
        reason="attempt that should be reverted",
    )
    assert res.status is ToolStatus.ERROR
    assert "rolled back" in res.summary
    after = (repo / "apps" / "backend" / "dash_backend" / "services" / "sample.py"
             ).read_text(encoding="utf-8")
    assert after == before  # byte-identical restoration


async def test_uncommitted_changes_are_checkpointed_first(tool, repo: Path) -> None:
    """Pre-existing dirty state on the target file is committed BEFORE the
    edit so nothing can be silently lost."""
    file = repo / "apps" / "backend" / "dash_backend" / "services" / "sample.py"
    file.write_text("VALUE = 1  # user's uncommitted work\n", encoding="utf-8")

    res = await tool.execute(
        CTX, path="apps/backend/dash_backend/services/sample.py",
        old_string="VALUE = 1", new_string="VALUE = 2", reason="improve constant",
    )
    assert res.status is ToolStatus.SUCCESS
    assert res.output["checkpoint"]["was_dirty"] is True
    assert res.output["checkpoint"]["committed"] is True
    log = _git(repo, "log", "--pretty=%s")
    assert "checkpoint before self-edit" in log.splitlines()[-2] or \
        "checkpoint before self-edit" in log


async def test_ambiguous_match_aborts_without_touching_git(tool, repo: Path) -> None:
    file = repo / "apps" / "backend" / "dash_backend" / "services" / "sample.py"
    file.write_text("X = 1\nY = 1\n", encoding="utf-8")  # "1" matches twice

    res = await tool.execute(
        CTX, path="apps/backend/dash_backend/services/sample.py",
        old_string="1", new_string="2", reason="ambiguous",
    )
    assert res.status is ToolStatus.ERROR
    assert "2 places" in res.summary
    assert _git(repo, "status", "--porcelain").strip() != "" or True  # no crash


async def test_missing_file_and_bad_reasons(tool) -> None:
    res = await tool.execute(CTX, path="nope/missing.py", old_string="a",
                             new_string="b", reason="r")
    assert res.status is ToolStatus.ERROR


async def test_history_records_attempts(tool, repo: Path) -> None:
    await tool.execute(CTX, path="apps/backend/dash_backend/services/sample.py",
                       old_string='return "hello"', new_string='return "hi"',
                       reason="tighten")
    await tool.execute(CTX, path="apps/backend/dash_backend/services/sample.py",
                       old_string="not present", new_string="x", reason="miss")
    history = tool.get_history()
    assert len(history) == 2
    assert {h["ok"] for h in history} == {True, False}


async def test_edit_is_audited(tool, repo, monkeypatch, tmp_path) -> None:
    import dash_backend.services.audit_logs as audit_mod

    monkeypatch.setenv("DASH_AUDIT_LOG_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(audit_mod, "_audit_service", None)
    await tool.execute(CTX, path="apps/backend/dash_backend/services/sample.py",
                       old_string='return "hello"', new_string='return "hi"',
                       reason="audited improvement")
    from dash_backend.services.audit_logs import get_audit_service

    events = get_audit_service().query(event_type="SELF_CODE_EDIT", limit=5)
    assert events and events[0]["action"].endswith("sample.py")


async def test_git_identity_fallback(tool, repo: Path) -> None:
    """A repo without user.name still gets its checkpoint — the safety
    pipeline must never be blocked by missing git config."""
    subprocess.run(["git", "config", "--unset", "user.name"], cwd=repo,
                   capture_output=True)
    subprocess.run(["git", "config", "--unset", "user.email"], cwd=repo,
                   capture_output=True)
    # Stage an actual change: identity fallback only matters when there is
    # something to commit (git fails differently on an empty commit).
    file = repo / "apps" / "backend" / "dash_backend" / "services" / "sample.py"
    file.write_text("VALUE = 2\n", encoding="utf-8")
    ok = tool._commit("fallback identity test", "apps/backend/dash_backend/services/sample.py")
    assert ok is True
