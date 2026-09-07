from __future__ import annotations

from typing import List, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from datetime import datetime
import uuid


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GoalCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5, description="1 = urgent .. 5 = low")
    deadline: Optional[datetime] = None


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    deadline: Optional[datetime] = None


class GoalRead(OrmModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    priority: Optional[int] = None
    deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Optional[dict] = Field(
        default=None,
        validation_alias=AliasChoices("meta_data", "metadata"),
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class GoalProgress(BaseModel):
    total_tasks: int
    completed_tasks: int
    percent: int


class GoalDetail(GoalRead):
    progress: GoalProgress
    tasks: List["TaskRead"] = []


class TaskCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    deadline: Optional[datetime] = None
    depends_on: Optional[List[uuid.UUID]] = Field(None, description="Task ids that must finish first")


class TaskUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    deadline: Optional[datetime] = None
    depends_on: Optional[List[uuid.UUID]] = None


class TaskRead(OrmModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    attempt: int
    priority: Optional[int] = None
    deadline: Optional[datetime] = None
    depends_on: Optional[List[str]] = None
    completed_at: Optional[datetime] = None
    metadata: Optional[dict] = Field(
        default=None,
        validation_alias=AliasChoices("meta_data", "metadata"),
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class CompleteTaskResponse(BaseModel):
    completed: bool
    task_id: uuid.UUID
    goal_completed: bool = False
    blocked_by: Optional[List[dict]] = None


class UpcomingItem(BaseModel):
    type: str  # "goal" | "task"
    id: uuid.UUID
    name: str
    status: str
    deadline: datetime
    overdue: bool
    goal_id: uuid.UUID
    goal_name: Optional[str] = None


class UpcomingResponse(BaseModel):
    window_days: int
    count: int
    items: List[UpcomingItem]


class StartGoalResponse(BaseModel):
    goal_id: uuid.UUID
    started: bool
    message: Optional[str] = None


GoalDetail.model_rebuild()
