"""Agent System - Multi-agent orchestration and coordination."""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio

from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


class AgentType(Enum):
    CODING = "coding"
    RESEARCH = "research"
    PLANNING = "planning"
    MEMORY = "memory"
    AUTOMATION = "automation"
    DESKTOP = "desktop"
    BROWSER = "browser"
    ORCHESTRATOR = "orchestrator"


class AgentState(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class Agent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: AgentType = AgentType.ORCHESTRATOR
    description: str = ""
    system_prompt: str = ""
    capabilities: List[str] = field(default_factory=list)
    state: AgentState = AgentState.IDLE
    current_task: Optional[str] = None
    performance_score: float = 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: Optional[datetime] = None

    # ── Common agent interface (expanded, additive) ──────────────────────
    # These are optional with defaults so existing constructions never break.
    priority: int = 2  # 1=low, 2=medium, 3=high, 4=critical
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    memory_access: str = "read"  # "none" | "read" | "read_write"
    execution_api: str = "async"  # "sync" | "async" | "stream"
    health_status: str = "healthy"  # "healthy" | "degraded" | "unhealthy" | "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the agent to a dict (ecosystem-ready)."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "state": self.state.value,
            "current_task": self.current_task,
            "performance_score": self.performance_score,
            "priority": self.priority,
            "permissions": list(self.permissions),
            "dependencies": list(self.dependencies),
            "tools": list(self.tools),
            "memory_access": self.memory_access,
            "execution_api": self.execution_api,
            "health_status": self.health_status,
        }


@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str = ""
    to_agent: str = ""
    content: str = ""
    message_type: str = "request"  # request, response, status
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AgentSystem:
    """Manages multi-agent communication and coordination."""
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self.agent_handlers: Dict[str, Callable] = {}
        self.communication_channel: Dict[str, List[AgentMessage]] = {}
        self.is_running = False
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the system."""
        self.agents[agent.id] = agent
        self.communication_channel[agent.id] = []
        logger.info(f"Registered agent: {agent.name} ({agent.id}) - {agent.type.value}")
    
    def register_handler(self, agent_id: str, handler: Callable) -> None:
        """Register a message handler for an agent."""
        self.agent_handlers[agent_id] = handler
        logger.info(f"Registered handler for agent: {agent_id}")
    
    async def send_message(self, from_agent: str, to_agent: str, content: str, message_type: str = "request", metadata: Dict[str, Any] = None) -> None:
        """Send a message from one agent to another."""
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            message_type=message_type,
            metadata=metadata or {},
        )
        
        self.communication_channel[to_agent].append(message)
        await self.message_queue.put(message)
        
        logger.debug(f"Message sent from {from_agent} to {to_agent}: {content[:50]}...")
    
    async def receive_message(self, agent_id: str) -> Optional[AgentMessage]:
        """Receive a message for a specific agent."""
        if agent_id not in self.communication_channel:
            return None
        
        if self.communication_channel[agent_id]:
            return self.communication_channel[agent_id].pop(0)
        
        return None
    
    async def orchestrate_agents(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Orchestrate multiple agents to complete a task."""
        context = context or {}
        results = {}
        
        logger.info(f"Orchestrating agents for task: {task}")
        
        # Select appropriate agents based on task
        task_lower = task.lower()
        selected_agents = []
        
        if "code" in task_lower or "program" in task_lower:
            selected_agents = [a for a in self.agents.values() if a.type == AgentType.CODING]
        elif "research" in task_lower or "search" in task_lower:
            selected_agents = [a for a in self.agents.values() if a.type == AgentType.RESEARCH]
        elif "plan" in task_lower or "strategy" in task_lower:
            selected_agents = [a for a in self.agents.values() if a.type == AgentType.PLANNING]
        elif "remember" in task_lower or "memory" in task_lower:
            selected_agents = [a for a in self.agents.values() if a.type == AgentType.MEMORY]
        elif "automate" in task_lower or "workflow" in task_lower:
            selected_agents = [a for a in self.agents.values() if a.type == AgentType.AUTOMATION]
        elif "desktop" in task_lower or "window" in task_lower:
            selected_agents = [a for a in self.agents.values() if a.type == AgentType.DESKTOP]
        elif "browser" in task_lower or "web" in task_lower:
            selected_agents = [a for a in self.agents.values() if a.type == AgentType.BROWSER]
        else:
            # Use orchestrator for general tasks
            selected_agents = [a for a in self.agents.values() if a.type == AgentType.ORCHESTRATOR]
        
        if not selected_agents:
            logger.warning(f"No agents available for task: {task}")
            return {"error": "No agents available"}
        
        # Execute tasks in parallel
        tasks = []
        for agent in selected_agents:
            if agent.id in self.agent_handlers:
                task = asyncio.create_task(
                    self.agent_handlers[agent.id](task, context),
                    name=f"agent_{agent.id}"
                )
                tasks.append(task)
        
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, agent in enumerate(selected_agents):
                agent_name = agent.name or agent.id
                results[agent_name] = task_results[i]
                logger.info(f"Agent {agent_name} completed task")
        
        return results
    
    async def start(self) -> None:
        """Start the agent system message processing loop."""
        self.is_running = True
        logger.info("Agent system started")
        
        while self.is_running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                
                # Route message to appropriate agent handler
                if message.to_agent in self.agent_handlers:
                    try:
                        await self.agent_handlers[message.to_agent](message)
                    except Exception as e:
                        logger.error(f"Handler error for agent {message.to_agent}: {e}")
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Agent system error: {e}")
                await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop the agent system."""
        self.is_running = False
        logger.info("Agent system stopped")
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[Agent]:
        """List all registered agents."""
        return list(self.agents.values())
    
    def get_agent_by_type(self, agent_type: AgentType) -> List[Agent]:
        """Get all agents of a specific type."""
        return [a for a in self.agents.values() if a.type == agent_type]
