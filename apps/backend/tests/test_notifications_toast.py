"""Toast notification tests (decisions.md #69).

The #61 defect class was a MODAL Win32 MessageBox in the notification path:
blocking until dismissed, and (before the to_thread fix) freezing the whole
backend. These tests pin the replacement contract hermetically — no real
PowerShell spawns, no real toast appears:

- Windows notifications go through the PowerShell WinRT toast script with
  arguments passed via environment variables (never interpolated into the
  command line — hostile text cannot inject XML or PowerShell).
- No modal MessageBox anywhere in the module.
- Success returns the legacy ``summary`` key plus honest mechanism metadata.
- Failure (non-zero rc, missing marker, missing powershell, timeout) raises
  RuntimeError naming the cause — there is NO modal fallback to hide it.
- ``duration`` maps onto the OS's toast timing vocabulary (short/long).
"""

from __future__ import annotations

import asyncio
import inspect
import subprocess
from typing import Any

import pytest

import dash_backend.services.notifications as notif_mod
from dash_backend.services.notifications import (
    NotificationService,
    _show_toast_ps_sync,
    _toast_timing,
)


class FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: bytes = b"DASH_TOAST_OK\n", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture()
def windows_mode(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Force the Windows path and capture subprocess.run calls."""
    calls: list[dict[str, Any]] = []

    def fake_run(argv, **kwargs):
        calls.append({"argv": argv, **kwargs})
        return FakeCompleted()

    monkeypatch.setattr(notif_mod, "IS_WINDOWS", True)
    monkeypatch.setattr(notif_mod.subprocess, "run", fake_run)
    return calls


class TestWindowsToastPath:
    @pytest.mark.asyncio
    async def test_success_uses_powershell_and_returns_honest_metadata(
        self, windows_mode: list[dict[str, Any]]
    ) -> None:
        result = await NotificationService().show(title="Guardian", message="port scan seen")
        assert result["summary"] == "Notification shown: Guardian"
        assert result["mechanism"] == "windows-toast"
        assert result["blocking"] is False
        assert len(windows_mode) == 1
        argv = windows_mode[0]["argv"]
        assert argv[0] == "powershell"
        assert "-NoProfile" in argv and "-NonInteractive" in argv

    @pytest.mark.asyncio
    async def test_args_travel_via_env_not_command_line(
        self, windows_mode: list[dict[str, Any]]
    ) -> None:
        hostile = "'; Remove-Item C:\\ -Recurse; <script>alert(1)</script>"
        await NotificationService().show(title="T", message=hostile)
        call = windows_mode[0]
        argv_str = " ".join(call["argv"])
        env = call["env"]
        # The hostile text reaches the child only through the environment.
        assert env["DASH_TOAST_MESSAGE"] == hostile
        assert "Remove-Item" not in argv_str
        assert "alert(1)" not in argv_str

    @pytest.mark.asyncio
    async def test_duration_maps_to_toast_timing(
        self, windows_mode: list[dict[str, Any]]
    ) -> None:
        await NotificationService().show(duration=5)
        assert windows_mode[0]["env"]["DASH_TOAST_DURATION"] == "short"
        await NotificationService().show(duration=20)
        assert windows_mode[-1]["env"]["DASH_TOAST_DURATION"] == "long"

    def test_timing_mapping_table(self) -> None:
        assert _toast_timing(1) == "short"
        assert _toast_timing(19) == "short"
        assert _toast_timing(20) == "long"
        assert _toast_timing(60) == "long"

    @pytest.mark.asyncio
    async def test_runs_off_the_event_loop(
        self, windows_mode: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The blocking worker must run via asyncio.to_thread (#61 rule)."""
        seen: dict[str, bool] = {"on_thread": False}
        original_to_thread = asyncio.to_thread

        async def spy_to_thread(fn, *args, **kwargs):
            seen["on_thread"] = True
            return await original_to_thread(fn, *args, **kwargs)

        monkeypatch.setattr(notif_mod.asyncio, "to_thread", spy_to_thread)
        await NotificationService().show()
        assert seen["on_thread"] is True


class TestFailureHonesty:
    @pytest.mark.asyncio
    async def test_nonzero_returncode_raises_with_stderr(
        self, windows_mode: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(argv, **kwargs):
            return FakeCompleted(returncode=1, stdout=b"", stderr=b"winrt exploded")

        monkeypatch.setattr(notif_mod.subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match=r"rc=1.*winrt exploded") as ei:
            await NotificationService().show()
        assert "winrt exploded" in str(ei.value)

    @pytest.mark.asyncio
    async def test_missing_marker_raises(
        self, windows_mode: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(argv, **kwargs):
            return FakeCompleted(returncode=0, stdout=b"unexpected output")

        monkeypatch.setattr(notif_mod.subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="Windows toast failed"):
            await NotificationService().show()

    @pytest.mark.asyncio
    async def test_timeout_raises_named_cause(
        self, windows_mode: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(argv, **kwargs):
            raise subprocess.TimeoutExpired(cmd="powershell", timeout=15)

        monkeypatch.setattr(notif_mod.subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="timed out"):
            await NotificationService().show()

    def test_missing_powershell_raises_cleanly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def real_run_missing(argv, **kwargs):
            raise FileNotFoundError("powershell")

        monkeypatch.setattr(notif_mod.subprocess, "run", real_run_missing)
        with pytest.raises(RuntimeError, match="powershell.exe not found"):
            _show_toast_ps_sync("t", "m", 5)


class TestNoModalAnywhere:
    def test_module_never_calls_message_box(self) -> None:
        """The #61 disease: a modal MessageBox in the notification path.

        Checks call shapes (and the ctypes user32 access they require),
        not the word itself — the docstring's historical note is fine.
        """
        source = inspect.getsource(notif_mod)
        assert "MessageBox(" not in source
        assert "MessageBoxW(" not in source
        assert "windll" not in source

    def test_worker_is_a_plain_sync_function(self) -> None:
        # The only blocking work happens inside the module-level worker
        # that show() dispatches via to_thread.
        assert inspect.iscoroutinefunction(NotificationService.show) is True
        assert inspect.iscoroutinefunction(_show_toast_ps_sync) is False


class TestLinuxPath:
    @pytest.mark.asyncio
    async def test_notify_send_contract_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, Any]] = []

        def fake_run(argv, **kwargs):
            calls.append({"argv": argv, **kwargs})
            return FakeCompleted(returncode=0, stdout=b"", stderr=b"")

        monkeypatch.setattr(notif_mod, "IS_WINDOWS", False)
        monkeypatch.setattr(notif_mod.subprocess, "run", fake_run)
        result = await NotificationService().show(title="T", message="m")
        assert result["summary"] == "Notification shown: T"
        assert result["mechanism"] == "notify-send"
        assert calls[0]["argv"][:1] == ["notify-send"]
