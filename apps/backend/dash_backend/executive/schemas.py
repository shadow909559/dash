from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid


class GoalCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GoalRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None


class TaskRead(BaseModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    attempt: int
    metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime


class StartGoalResponse(BaseModel):
    goal_id: uuid.UUID
    started: bool
    message: Optional[str] = None
