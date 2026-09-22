"""NotificationService - show desktop notifications.

Windows mechanism (decisions.md #69): a real Windows toast via the WinRT
``ToastNotificationManager``, dispatched through PowerShell — no modal
dialog, no new Python dependencies. The toast is fire-and-forget: the call
returns as soon as the OS accepts the notification; nobody has to dismiss
anything (the old ``MessageBoxW`` was modal and, before #61's fix, froze
the whole backend until clicked).

Contract:
- Never runs on the event loop (``asyncio.to_thread``) — the #61 rule stands.
- Never blocks the user either — no modal fallback on toast failure; the
  failure is raised honestly with the OS-side error text instead.
- Title/message reach PowerShell via environment variables and are
  HTML-escaped inside the toast XML — hostile text cannot inject XML or
  PowerShell.
- ``duration`` maps to the toast's own timing (short ≈ 5-7s, long ≈ 25s+);
  it is not a per-second contract, because toasts belong to the OS.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"

_TOAST_TIMEOUT_S = 15.0
# Brief wait for the acceptance marker; a process still alive after this
# is (with overwhelming likelihood) displaying the toast. Reaped later so
# no zombie PowerShell accumulates.
_TOAST_ACCEPT_S = 6.0
_TOAST_REAP_S = 60.0

# WinRT toast script. Values come from DASH_TOAST_* environment variables
# (never interpolated into the command line) and are HTML-escaped before
# being placed into the toast XML. The AUMID is the well-known
# prose-built-in PowerShell alias, which lets a non-packaged app raise
# toasts without an Appx identity.
_TOAST_PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$title = [System.Net.WebUtility]::HtmlEncode($env:DASH_TOAST_TITLE)
$message = [System.Net.WebUtility]::HtmlEncode($env:DASH_TOAST_MESSAGE)
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast duration=`"$env:DASH_TOAST_DURATION`"><visual><binding template=`"ToastText02`"><text id=`"1`">$title</text><text id=`"2`">$message</text></binding></visual></toast>")
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe').Show($toast)
Write-Output 'DASH_TOAST_OK'
"""


def _toast_timing(duration: int) -> str:
    """Map the requested seconds onto the toast's own timing vocabulary."""
    return "long" if int(duration) >= 20 else "short"


def _show_toast_ps_sync(title: str, message: str, duration: int) -> dict[str, Any]:
    """Dispatch one Windows toast (blocking worker; runs off the loop).

    Fire-and-forget semantics, honestly implemented: PowerShell exits as
    soon as the OS accepts the toast, EXCEPT that WinRT keeps the process
    alive for as long as the toast is on screen — a healthy dispatch can
    therefore outlive any reasonable wait (found live: the reminder toast
    displayed while the process hung past 15 s and the old wait raised
    TimeoutExpired on a *successful* notification). So: wait briefly for
    the acceptance marker; if the process merely lingers, the toast is
    showing — report success and reap the process when it's done.
    """
    env = dict(os.environ)
    env["DASH_TOAST_TITLE"] = str(title)
    env["DASH_TOAST_MESSAGE"] = str(message)
    env["DASH_TOAST_DURATION"] = _toast_timing(duration)
    argv = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        _TOAST_PS_SCRIPT,
    ]
    try:
        proc = subprocess.Popen(
            argv,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Windows toast failed: powershell.exe not found") from exc

    try:
        out, err = proc.communicate(timeout=_TOAST_ACCEPT_S)
    except subprocess.TimeoutExpired:
        # Still running: WinRT holds the process while the toast displays.
        # Reap it once the toast is gone; report the dispatch as done.
        threading.Timer(_TOAST_REAP_S, proc.kill).start()
        return {"mechanism": "windows-toast", "lingering": True}

    if proc.returncode != 0 or "DASH_TOAST_OK" not in (out or ""):
        stderr_tail = (err or "").strip()[-300:]
        raise RuntimeError(
            f"Windows toast failed (rc={proc.returncode}): {stderr_tail or 'no error output'}"
        )
    return {"mechanism": "windows-toast", "blocking": False}


class NotificationService(Singleton):
    """Show desktop notifications (non-blocking toast on Windows)."""

    async def show(
        self,
        title: str = "DASH",
        message: str = "",
        duration: int = 5,
    ) -> dict[str, Any]:
        """Show a desktop notification (never on the event loop)."""
        try:
            if IS_WINDOWS:
                result = await asyncio.to_thread(
                    _show_toast_ps_sync, str(title), str(message), int(duration)
                )
                return {
                    "summary": f"Notification shown: {title}",
                    **result,
                }
            else:
                # notify-send on Linux is already fire-and-forget.
                subprocess.run(
                    ["notify-send", title, message],
                    capture_output=True,
                    timeout=duration,
                )
                return {
                    "summary": f"Notification shown: {title}",
                    "mechanism": "notify-send",
                    "blocking": False,
                }
        except Exception as exc:
            logger.exception("Failed to show notification")
            raise RuntimeError(f"Failed to show notification: {exc}") from exc
