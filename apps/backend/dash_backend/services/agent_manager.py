"""Agent Manager — tracks all agents, their status, and what they're doing.

Supports multiple concurrent agents for multitasking:
- Each agent can use a different AI provider/model
- Real-time status tracking (idle, thinking, executing, speaking)
- Task history and current task per agent
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    ERROR = "error"
    OFFLINE = "offline"


class AgentRole(str, Enum):
    GENERAL = "general"
    CODER = "coder"
    RESEARCHER = "researcher"
    PLANNER = "planner"
    EXECUTOR = "executor"
    BROWSER = "browser"
    FILE_MANAGER = "file_manager"
    DEVOPS = "devops"


@dataclass
class AgentInfo:
    """Real-time info about a single agent."""
    id: str
    name: str
    role: AgentRole
    provider: str  # "ollama", "openai", "claude", "gemini"
    model: str
    status: AgentStatus = AgentStatus.IDLE
    current_task: str = ""
    current_task_id: str = ""
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_active: float = 0.0
    started_at: float = field(default_factory=time.time)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "provider": self.provider,
            "model": self.model,
            "status": self.status.value,
            "current_task": self.current_task,
            "current_task_id": self.current_task_id,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "uptime_seconds": int(time.time() - self.started_at),
            "error": self.error,
        }


@dataclass
class TaskRecord:
    """Record of a task dispatched to an agent."""
    id: str
    agent_id: str
    description: str
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "description": self.description,
            "status": self.status,
            "result": self.result[:500] if self.result else "",
            "duration_ms": int((self.completed_at - self.started_at) * 1000) if self.started_at else 0,
        }


class AgentManager:
    """Manages multiple concurrent agents with real-time status tracking."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = asyncio.Lock()

    async def register_default_agents(self) -> None:
        """Register the default agent fleet."""
        defaults = [
            ("DASH General", AgentRole.GENERAL, "ollama", "llama3.2:1b"),
            ("DASH Coder", AgentRole.CODER, "ollama", "llama3.2:1b"),
            ("DASH Researcher", AgentRole.RESEARCHER, "ollama", "llama3.2:1b"),
            ("DASH Planner", AgentRole.PLANNER, "ollama", "llama3.2:1b"),
            ("DASH Executor", AgentRole.EXECUTOR, "ollama", "llama3.2:1b"),
        ]
        for name, role, provider, model in defaults:
            agent = AgentInfo(
                id=str(uuid.uuid4()),
                name=name,
                role=role,
                provider=provider,
                model=model,
            )
            async with self._lock:
                self._agents[agent.id] = agent
        logger.info("Registered %d default agents", len(defaults))

    async def register_agent(
        self, name: str, role: AgentRole, provider: str, model: str
    ) -> AgentInfo:
        agent = AgentInfo(
            id=str(uuid.uuid4()),
            name=name,
            role=role,
            provider=provider,
            model=model,
        )
        async with self._lock:
            self._agents[agent.id] = agent
        logger.info("Registered agent: %s (%s/%s)", name, provider, model)
        return agent

    async def unregister_agent(self, agent_id: str) -> bool:
        async with self._lock:
            return self._agents.pop(agent_id, None) is not None

    async def get_agent(self, agent_id: str) -> AgentInfo | None:
        return self._agents.get(agent_id)

    async def list_agents(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [a.to_dict() for a in self._agents.values()]

    async def update_agent_status(
        self,
        agent_id: str,
        status: AgentStatus,
        task: str = "",
        task_id: str = "",
        error: str = "",
    ) -> None:
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return
            agent.status = status
            agent.last_active = time.time()
            if task:
                agent.current_task = task
            if task_id:
                agent.current_task_id = task_id
            if error:
                agent.error = error
            if status == AgentStatus.IDLE:
                agent.current_task = ""
                agent.current_task_id = ""
                agent.error = ""
            elif status == AgentStatus.THINKING:
                agent.current_task = task or "Processing..."
            elif status == AgentStatus.EXECUTING:
                agent.current_task = task or "Executing..."
            elif status == AgentStatus.SPEAKING:
                agent.current_task = task or "Responding..."
            elif status == AgentStatus.ERROR:
                agent.error = error

    async def dispatch_task(
        self, agent_id: str, description: str
    ) -> TaskRecord | None:
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        task = TaskRecord(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            description=description,
            status="running",
            started_at=time.time(),
        )
        async with self._lock:
            self._tasks[task.id] = task
        await self.update_agent_status(
            agent_id, AgentStatus.THINKING, description, task.id
        )
        return task

    async def complete_task(
        self, task_id: str, result: str = "", failed: bool = False
    ) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.completed_at = time.time()
        task.result = result
        task.status = "failed" if failed else "completed"
        agent = self._agents.get(task.agent_id)
        if agent:
            if failed:
                agent.tasks_failed += 1
            else:
                agent.tasks_completed += 1
            await self.update_agent_status(task.agent_id, AgentStatus.IDLE)

    async def list_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    async def get_stats(self) -> dict[str, Any]:
        async with self._lock:
            agents = list(self._agents.values())
        active = sum(1 for a in agents if a.status not in (AgentStatus.IDLE, AgentStatus.OFFLINE))
        return {
            "total_agents": len(agents),
            "active_agents": active,
            "idle_agents": len(agents) - active,
            "total_tasks": len(self._tasks),
            "running_tasks": sum(1 for t in self._tasks.values() if t.status == "running"),
            "completed_tasks": sum(1 for t in self._tasks.values() if t.status == "completed"),
            "failed_tasks": sum(1 for t in self._tasks.values() if t.status == "failed"),
            "agents": [a.to_dict() for a in agents],
        }


# Singleton
_manager: AgentManager | None = None


def get_agent_manager() -> AgentManager:
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager
