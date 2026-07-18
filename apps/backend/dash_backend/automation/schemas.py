"""Pydantic schemas for automation API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AutomationCreate(BaseModel):
    name: str = Field(..., max_length=128)
    description: str | None = None
    trigger_type: str = Field(..., max_length=32)
    schedule: str = Field(..., max_length=256)
    tool_name: str = Field(..., max_length=128)
    tool_arguments: dict[str, Any] | None = None
    enabled: bool = True


class AutomationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    trigger_type: str
    schedule: str
    tool_name: str
    tool_arguments: dict[str, Any] | None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutomationExecutionRead(BaseModel):
    id: uuid.UUID
    automation_id: uuid.UUID
    status: str
    summary: str | None
    output: dict[str, Any] | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: float | None
    created_at: datetime

    model_config = {"from_attributes": True}

class AutomationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_type: str | None = None
    schedule: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    enabled: bool | None = None
