# Planner

## Overview

DASH includes a planning system that decomposes user goals into actionable steps with dependency tracking and progress monitoring.

## Architecture

```
User Goal -> Decompose -> Steps with Dependencies -> Execute -> Track Progress
```

## Components

### Goal

Represents a high-level objective:

```python
class Goal(Base):
    id: UUID
    user_id: UUID (FK -> users)
    name: str
    description: Optional[str]
    status: str (pending, running, completed, failed)
    created_at: datetime
    updated_at: datetime
```

### Task

Represents a single actionable step within a goal:

```python
class Task(Base):
    id: UUID
    goal_id: UUID (FK -> goals)
    name: str
    description: str
    status: str (pending, running, completed, failed)
    dependencies: List[UUID] (task IDs)
    attempt: int
    meta_data: dict
    created_at: datetime
    updated_at: datetime
```

## Decomposition

DASH uses two strategies for decomposing goals:

1. **Planner (LLM-based)**: Uses the configured LLM to intelligently decompose goals
2. **Heuristic Fallback**: Splits description into sentences when LLM is unavailable

## Execution

- Background worker loop picks pending tasks
- Row-level locking (FOR UPDATE SKIP LOCKED) for multi-worker safety
- Heartbeat mechanism to detect stuck workers
- Automatic reset of stuck tasks after timeout

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/planner/goals` | Create goal |
| GET | `/api/v1/planner/goals` | List goals |
| GET | `/api/v1/planner/goals/{id}` | Get goal with tasks |
| POST | `/api/v1/planner/goals/{id}/start` | Start executing goal |
