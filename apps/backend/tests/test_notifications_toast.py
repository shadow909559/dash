"""Toast notification tests (decisions.md #69, composite-task fix 2026-09-23).

The #61 defect class was a MODAL Win32 MessageBox in the notification path:
blocking until dismissed, and (before the to_thread fix) freezing the whole
backend. These tests pin the replacement contract hermetically — no real
PowerShell spawns, no real toast appears:

- Windows notifications go through the PowerShell WinRT toast script with
  arguments passed via environment variables (never interpolated into the
  command line — hostile text cannot inject XML or PowerShell).
- No modal MessageBox anywhere in the module.
- Success returns the legacy ``summary`` key plus honest mechanism metadata.
- A dispatch whose PowerShell process lingers past the acceptance window is
  SUCCESS (WinRT holds the process while the toast displays — found live
  when a reminder toast displayed while the old wait raised TimeoutExpired
  on a healthy notification); the process is reaped afterwards, and no
  error is raised.
- Failure (non-zero rc, missing marker, missing powershell) raises
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


class FakeProc:
    """Hermetic stand-in for subprocess.Popen."""

    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "DASH_TOAST_OK\n",
        stderr: str = "",
        linger: bool = False,
    ) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._linger = linger
        self.killed = False

    def communicate(self, timeout=None):
        if self._linger:
            raise subprocess.TimeoutExpired(cmd="powershell", timeout=timeout)
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True


class FakeTimer:
    """Records (delay, fn) without spawning a real thread."""

    instances: list["FakeTimer"] = []

    def __init__(self, delay, fn, *args):
        self.delay = delay
        self.fn = fn
        self.args = args
        self.started = False
        FakeTimer.instances.append(self)

    def start(self):
        self.started = True


@pytest.fixture()
def windows_mode(monkeypatch: pytest.MonkeyPatch, proc: FakeProc) -> list[dict[str, Any]]:
    """Force the Windows path and capture subprocess.Popen calls."""
    calls: list[dict[str, Any]] = []

    def fake_popen(argv, **kwargs):
        calls.append({"argv": argv, **kwargs})
        return proc

    monkeypatch.setattr(notif_mod, "IS_WINDOWS", True)
    monkeypatch.setattr(notif_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(notif_mod.threading, "Timer", FakeTimer)
    FakeTimer.instances.clear()
    return calls


@pytest.fixture()
def proc() -> FakeProc:
    return FakeProc()


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

    @pytest.mark.asyncio
    async def test_lingering_dispatch_is_success_and_reaped(
        self, windows_mode: list[dict[str, Any]]
    ) -> None:
        """Healthy dispatch that outlives the acceptance window (the toast
        is on screen): success result, no exception, process reaped later."""
        lingering = FakeProc(linger=True)
        windows_mode  # fixture already wired; swap the proc
        import dash_backend.services.notifications as nm

        # re-patch Popen to return the lingering proc
        monkey = getattr(windows_mode, "_monkeypatch", None)

        # simplest: patch again here
        # (the fixture records argv; we only need the return value changed)
        result_container: dict[str, Any] = {}

        async def call():
            # _show_toast_ps_sync runs in a thread; call it directly
            result_container["r"] = nm._show_toast_ps_sync("t", "m", 5)

        import threading as _t

        orig_popen = nm.subprocess.Popen

        def lingering_popen(argv, **kwargs):
            return lingering

        nm.subprocess.Popen = lingering_popen
        try:
            await call()
        finally:
            nm.subprocess.Popen = orig_popen

        assert result_container["r"]["mechanism"] == "windows-toast"
        assert result_container["r"]["lingering"] is True
        # a reap timer was armed and kills the process when it fires
        assert FakeTimer.instances and FakeTimer.instances[-1].started
        FakeTimer.instances[-1].fn()
        assert lingering.killed is True


class TestFailureHonesty:
    @pytest.mark.asyncio
    async def test_nonzero_returncode_raises_with_stderr(
        self, windows_mode: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_popen(argv, **kwargs):
            return FakeProc(returncode=1, stdout="", stderr="winrt exploded")

        monkeypatch.setattr(notif_mod.subprocess, "Popen", fake_popen)
        with pytest.raises(RuntimeError, match=r"rc=1.*winrt exploded") as ei:
            await NotificationService().show()
        assert "winrt exploded" in str(ei.value)

    @pytest.mark.asyncio
    async def test_missing_marker_raises(
        self, windows_mode: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_popen(argv, **kwargs):
            return FakeProc(returncode=0, stdout="unexpected output")

        monkeypatch.setattr(notif_mod.subprocess, "Popen", fake_popen)
        with pytest.raises(RuntimeError, match="Windows toast failed"):
            await NotificationService().show()

    def test_missing_powershell_raises_cleanly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def real_popen_missing(argv, **kwargs):
            raise FileNotFoundError("powershell")

        monkeypatch.setattr(notif_mod.subprocess, "Popen", real_popen_missing)
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

        class FakeCompleted:
            returncode = 0
            stdout = b""
            stderr = b""

        def fake_run(argv, **kwargs):
            calls.append({"argv": argv, **kwargs})
            return FakeCompleted()

        monkeypatch.setattr(notif_mod, "IS_WINDOWS", False)
        monkeypatch.setattr(notif_mod.subprocess, "run", fake_run)
        result = await NotificationService().show(title="T", message="m")
        assert result["summary"] == "Notification shown: T"
        assert result["mechanism"] == "notify-send"
        assert calls[0]["argv"][:1] == ["notify-send"]
