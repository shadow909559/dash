"""Approval Dialog - User confirmation for dangerous actions."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRequest:
    id: str = ""
    action: str = ""
    description: str = ""
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"
    created_at: float = 0.0
    expires_at: float = 0.0
    status: str = "pending"
    response: Optional[bool] = None


class ApprovalDialog:
    def __init__(self, timeout: float = 60.0):
        self._timeout = timeout
        self._requests: Dict[str, ApprovalRequest] = {}
        self._futures: Dict[str, asyncio.Future] = {}
        self._callbacks: List[Callable] = []

    async def request_approval(self, action: str, description: str,
                                 tool_name: str = "", arguments: Dict = None,
                                 risk_level: str = "medium") -> ApprovalRequest:
        req = ApprovalRequest(
            id=str(uuid.uuid4()), action=action, description=description,
            tool_name=tool_name, arguments=arguments or {},
            risk_level=risk_level, created_at=time.time(),
            expires_at=time.time() + self._timeout,
        )
        self._requests[req.id] = req
        future = asyncio.get_event_loop().create_future()
        self._futures[req.id] = future
        for cb in self._callbacks:
            try:
                cb(req)
            except Exception:
                pass
        return req

    async def wait_for_response(self, request_id: str, timeout: Optional[float] = None) -> Optional[bool]:
        future = self._futures.get(request_id)
        if not future:
            return None
        try:
            result = await asyncio.wait_for(future, timeout or self._timeout)
            return result
        except asyncio.TimeoutError:
            req = self._requests.get(request_id)
            if req:
                req.status = "expired"
            return None

    def respond(self, request_id: str, approved: bool) -> bool:
        future = self._futures.get(request_id)
        if not future or future.done():
            return False
        req = self._requests.get(request_id)
        if req:
            req.status = "approved" if approved else "rejected"
            req.response = approved
        future.set_result(approved)
        return True

    def on_request(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def get_pending(self) -> List[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status == "pending"]

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)


_approval_dialog: Optional[ApprovalDialog] = None


def get_approval_dialog() -> ApprovalDialog:
    global _approval_dialog
    if _approval_dialog is None:
        _approval_dialog = ApprovalDialog()
    return _approval_dialog
