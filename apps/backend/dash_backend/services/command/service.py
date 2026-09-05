"""Command service — orchestrates the full command pipeline.

Android -> Backend -> Desktop -> Execution -> Result -> Android

Handles:
  - Command lifecycle (pending -> approved -> running -> completed/failed)
  - Permission checks (approval from desktop user)
  - Routing commands to the correct system service
  - Result streaming back to the source
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any, Callable

from dash_backend.logging_config import get_logger
from dash_backend.services.command.models import (
    ApprovalRequest,
    CommandCategory,
    CommandRequest,
    CommandResult,
    CommandStatus,
    PermissionDecision,
)
from dash_backend.services.command.queue import CommandQueue, QueueEntry

_SERVICES: dict[str, object] = {}

logger = get_logger(__name__)


def _get_service(name: str) -> object | None:
    return _SERVICES.get(name)


def _set_service(name: str, service: object) -> None:
    _SERVICES[name] = service


class CommandService:
    """Central orchestrator for remote command execution."""

    def __init__(self) -> None:
        self._queue = CommandQueue(
            max_concurrent=5,
            max_queue_per_source=200,
            default_timeout=60.0,
        )
        self._pending_approvals: dict[str, ApprovalRequest] = {}
        self._running = True
        self._processor_task: asyncio.Task | None = None
        self._approval_callback: Callable[[ApprovalRequest], None] | None = None
        self._result_callback: Callable[[CommandResult], None] | None = None

    def start(self) -> None:
        """Start the background command processor."""
        if self._processor_task is None or self._processor_task.done():
            self._running = True
            self._processor_task = asyncio.create_task(self._process_loop())
            logger.info("CommandService processor started")

    async def stop(self) -> None:
        """Gracefully stop the command processor."""
        self._running = False
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            logger.info("CommandService processor stopped")

    def set_approval_callback(self, cb: Callable[[ApprovalRequest], None] | None) -> None:
        self._approval_callback = cb

    def set_result_callback(self, cb: Callable[[CommandResult], None] | None) -> None:
        self._result_callback = cb

    async def submit(self, request: CommandRequest, *, auto_approve: bool = False) -> CommandResult:
        """Submit a command for execution."""
        from dash_backend.services.permissions import get_permission_service

        perm_service = get_permission_service()

        if perm_service.is_denied(request.user_id or "", request.category.value, request.action):
            return CommandResult(command_id=request.command_id, status=CommandStatus.REJECTED, error="Command is denied forever")

        always_allowed = perm_service.is_always_allowed(request.user_id or "", request.category.value, request.action)
        needs_approval = request.requires_approval and not always_allowed and not auto_approve

        if needs_approval:
            approval = ApprovalRequest(
                command_id=request.command_id,
                category=request.category,
                action=request.action,
                params=request.params,
                description=self._describe_command(request),
                source=request.source,
                created_at=datetime.now(UTC).isoformat(),
            )
            self._pending_approvals[request.command_id] = approval

            if self._approval_callback:
                try:
                    self._approval_callback(approval)
                except Exception:
                    logger.exception("Approval callback failed")

            deadline = time.monotonic() + 60.0
            while request.command_id in self._pending_approvals:
                if time.monotonic() > deadline:
                    self._pending_approvals.pop(request.command_id, None)
                    return CommandResult(command_id=request.command_id, status=CommandStatus.TIMEOUT, error="Approval timed out")
                await asyncio.sleep(0.1)

        future = await self._queue.enqueue(request)
        result = await future
        self._notify_result(result)
        return result

    async def approve(self, command_id: str, decision: PermissionDecision = PermissionDecision.ALLOW_ONCE) -> bool:
        """Approve or reject a pending command."""
        approval = self._pending_approvals.pop(command_id, None)
        if approval is None:
            logger.warning("Approval not found for %s", command_id)
            return False

        if decision == PermissionDecision.ALWAYS_ALLOW:
            from dash_backend.services.permissions import get_permission_service
            get_permission_service().add_always_allowed("", approval.category.value, approval.action)

        if decision == PermissionDecision.DENY_FOREVER:
            from dash_backend.services.permissions import get_permission_service
            get_permission_service().add_denied_forever("", approval.category.value, approval.action)

        if decision in (PermissionDecision.DENY, PermissionDecision.DENY_FOREVER):
            self._notify_result(CommandResult(command_id=command_id, status=CommandStatus.REJECTED, error="Command rejected by user"))
            return True

        request = CommandRequest(command_id=command_id, category=approval.category, action=approval.action, params=approval.params, source=approval.source, requires_approval=False)
        future = await self._queue.enqueue(request)
        result = await future
        self._notify_result(result)
        return True

    async def reject(self, command_id: str) -> bool:
        return await self.approve(command_id, PermissionDecision.DENY)

    async def _process_loop(self) -> None:
        while self._running:
            try:
                entry = await self._queue.dequeue()
                if entry is None:
                    continue
                asyncio.create_task(self._execute_entry(entry))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in command processor loop")
                await asyncio.sleep(0.5)

    async def _execute_entry(self, entry: QueueEntry) -> None:
        request = entry.request
        command_id = request.command_id
        started_at = datetime.now(UTC).isoformat()

        try:
            output = await self._route_command(request)
            completed_at = datetime.now(UTC).isoformat()
            duration = self._calc_duration_ms(started_at, completed_at)
            result = CommandResult(command_id=command_id, status=CommandStatus.COMPLETED, started_at=started_at, completed_at=completed_at, result=output, summary=output.get("summary", ""), duration_ms=duration)
        except Exception as exc:
            completed_at = datetime.now(UTC).isoformat()
            duration = self._calc_duration_ms(started_at, completed_at)
            logger.exception("Command %s failed", command_id)
            result = CommandResult(command_id=command_id, status=CommandStatus.FAILED, started_at=started_at, completed_at=completed_at, error=str(exc), duration_ms=duration)

        await self._queue.complete(command_id, result)

    async def _route_command(self, request: CommandRequest) -> dict[str, Any]:
        cat, action, params = request.category, request.action, request.params
        if cat == CommandCategory.SYSTEM:
            return await self._execute_system(action, params)
        elif cat == CommandCategory.APPS:
            return await self._execute_app(action, params)
        elif cat == CommandCategory.CLIPBOARD:
            return await self._execute_clipboard(action, params)
        elif cat == CommandCategory.NOTIFICATIONS:
            return await self._execute_notification(action, params)
        elif cat == CommandCategory.WINDOW:
            return await self._execute_window(action, params)
        elif cat == CommandCategory.MOUSE:
            return await self._execute_mouse(action, params)
        elif cat == CommandCategory.KEYBOARD:
            return await self._execute_keyboard(action, params)
        elif cat == CommandCategory.FILES:
            return await self._execute_file(action, params)
        elif cat == CommandCategory.TERMINAL:
            return await self._execute_terminal(action, params)
        elif cat == CommandCategory.BROWSER:
            return await self._execute_browser(action, params)
        raise ValueError(f"Unknown category: {cat}")

    async def _execute_system(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        import subprocess
        actions_map = {
            "shutdown": (["shutdown", "/s", "/t", "5"], "Shutdown initiated"),
            "restart": (["shutdown", "/r", "/t", "5"], "Restart initiated"),
            "sleep": (["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"], "Sleep initiated"),
            "hibernate": (["shutdown", "/h"], "Hibernate initiated"),
            "lock": (["rundll32.exe", "user32.dll,LockWorkStation"], "Workstation locked"),
            "logout": (["shutdown", "/l"], "Logout initiated"),
        }
        if action in actions_map:
            cmd, summary = actions_map[action]
            subprocess.run(cmd, timeout=10)
            return {"summary": summary}
        if action == "volume":
            return {"summary": f"Volume set to {params.get('level', 50)}%"}
        if action == "brightness":
            return {"summary": f"Brightness set to {params.get('level', 50)}%"}
        if action == "get_system_info":
            from dash_backend.services.system import SystemMonitor
            return await SystemMonitor().collect()
        raise ValueError(f"Unknown system action: {action}")

    async def _execute_app(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.applications import ApplicationService
        svc = _get_service("applications")
        if svc is None:
            svc = ApplicationService()
            _set_service("applications", svc)
        if action == "launch":
            return await svc.launch(params.get("path", ""), params.get("args", []))
        elif action == "close":
            return await svc.close(params.get("name", ""))
        elif action == "kill":
            return await svc.kill(params.get("name", ""))
        elif action == "restart":
            return await svc.restart(params.get("name", ""), params.get("path"))
        raise ValueError(f"Unknown app action: {action}")

    async def _execute_clipboard(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.clipboard import ClipboardService
        svc = ClipboardService()
        if action == "copy":
            return await svc.copy(params.get("text", ""))
        elif action == "read":
            return await svc.read()
        elif action == "clear":
            return await svc.clear()
        raise ValueError(f"Unknown clipboard action: {action}")

    async def _execute_notification(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.notifications import NotificationService
        svc = NotificationService()
        if action == "show":
            return await svc.show(params.get("title", "DASH"), params.get("message", ""), params.get("duration", 5))
        raise ValueError(f"Unknown notification action: {action}")

    async def _execute_window(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.window import WindowService
        svc = WindowService()
        if action == "list":
            return await svc.list_windows()
        elif action == "focus":
            return await svc.focus(params.get("title", ""))
        elif action == "minimize":
            return await svc.minimize(params.get("title", ""))
        elif action == "maximize":
            return await svc.maximize(params.get("title", ""))
        elif action == "close_window":
            return await svc.close_window(params.get("title", ""))
        raise ValueError(f"Unknown window action: {action}")

    async def _execute_mouse(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.mouse import MouseService
        svc = MouseService()
        if action == "move":
            return await svc.move(params.get("x", 0), params.get("y", 0))
        elif action == "click":
            return await svc.click(params.get("button", "left"))
        elif action == "double_click":
            return await svc.double_click()
        elif action == "scroll":
            return await svc.scroll(params.get("clicks", 1))
        elif action == "position":
            return await svc.get_position()
        raise ValueError(f"Unknown mouse action: {action}")

    async def _execute_keyboard(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.keyboard import KeyboardService
        svc = KeyboardService()
        if action == "type":
            return await svc.type_text(params.get("text", ""))
        elif action == "hotkey":
            return await svc.hotkey(*params.get("keys", []))
        elif action == "press":
            return await svc.press(params.get("key", ""))
        raise ValueError(f"Unknown keyboard action: {action}")

    async def _execute_file(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.files import FileService
        svc = FileService()
        if action == "copy":
            return await svc.copy(params.get("source", ""), params.get("destination", ""))
        elif action == "move":
            return await svc.move(params.get("source", ""), params.get("destination", ""))
        elif action == "rename":
            return await svc.rename(params.get("path", ""), params.get("new_name", ""))
        elif action == "delete":
            return await svc.delete(params.get("path", ""))
        elif action == "create_folder":
            return await svc.create_folder(params.get("path", ""))
        elif action == "read_folder":
            return await svc.read_folder(params.get("path", "."))
        elif action == "search":
            return await svc.search_files(params.get("pattern", "*"), params.get("path", "."), params.get("max_results", 50))
        raise ValueError(f"Unknown file action: {action}")

    async def _execute_terminal(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.terminal import TerminalService
        svc = TerminalService()
        if action == "execute":
            return await svc.execute(params.get("command", ""), params.get("timeout", 30), params.get("working_directory"))
        elif action == "execute_script":
            return await svc.execute_script(params.get("script", ""))
        raise ValueError(f"Unknown terminal action: {action}")

    async def _execute_browser(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.services.browser import BrowserService
        svc = BrowserService()
        if action == "open_url":
            return await svc.open_url(params.get("url", ""))
        elif action == "open_tab":
            return await svc.open_tab(params.get("url", ""))
        elif action == "search":
            return await svc.search(params.get("query", ""))
        raise ValueError(f"Unknown browser action: {action}")

    def _describe_command(self, request: CommandRequest) -> str:
        cat, action = request.category.value, request.action
        desc_map = {
            ("system", "shutdown"): "Shut down the computer",
            ("system", "restart"): "Restart the computer",
            ("system", "sleep"): "Put the computer to sleep",
            ("system", "hibernate"): "Hibernate the computer",
            ("system", "lock"): "Lock the workstation",
            ("system", "logout"): "Log out the current user",
            ("system", "volume"): f"Set volume to {request.params.get('level', '?')}%",
            ("system", "brightness"): f"Set brightness to {request.params.get('level', '?')}%",
            ("apps", "launch"): f"Launch: {request.params.get('path', '?')}",
            ("apps", "close"): f"Close: {request.params.get('name', '?')}",
            ("apps", "kill"): f"Kill: {request.params.get('name', '?')}",
            ("clipboard", "copy"): "Copy to clipboard",
            ("clipboard", "read"): "Read clipboard",
            ("clipboard", "clear"): "Clear clipboard",
            ("notifications", "show"): f"Show: {request.params.get('message', '?')}",
            ("window", "list"): "List windows",
            ("window", "focus"): f"Focus: {request.params.get('title', '?')}",
            ("mouse", "move"): f"Move mouse to ({request.params.get('x', '?')}, {request.params.get('y', '?')})",
            ("mouse", "click"): f"Click {request.params.get('button', 'left')}",
            ("keyboard", "type"): f"Type {len(request.params.get('text', ''))} chars",
            ("keyboard", "hotkey"): f"Hotkey: {request.params.get('keys', [])}",
            ("files", "copy"): f"Copy {request.params.get('source', '?')}",
            ("files", "delete"): f"Delete {request.params.get('path', '?')}",
            ("terminal", "execute"): f"Execute: {str(request.params.get('command', '?'))[:50]}",
            ("browser", "open_url"): f"Open URL: {request.params.get('url', '?')}",
        }
        return desc_map.get((cat, action), f"Execute {cat}.{action}")

    @staticmethod
    def _calc_duration_ms(started_at: str, completed_at: str) -> float:
        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(completed_at)
            return (end - start).total_seconds() * 1000.0
        except Exception:
            return 0.0

    def _notify_result(self, result: CommandResult) -> None:
        if self._result_callback:
            try:
                self._result_callback(result)
            except Exception:
                logger.exception("Result callback failed")


# Singleton
_service: CommandService | None = None


def get_command_service() -> CommandService:
    global _service
    if _service is None:
        _service = CommandService()
    return _service
