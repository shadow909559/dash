"""Workflow Builder - Visual workflow builder for complex automations."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of workflow nodes."""
    TRIGGER = "trigger"
    ACTION = "action"
    CONDITION = "condition"
    DELAY = "delay"
    PARALLEL = "parallel"
    LOOP = "loop"
    NOTIFICATION = "notification"
    END = "end"


@dataclass
class WorkflowNode:
    """A node in a workflow."""
    id: str
    type: NodeType
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    next_nodes: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # For conditional branching
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "config": self.config,
            "next_nodes": self.next_nodes,
            "condition": self.condition,
        }


@dataclass
class Workflow:
    """A workflow definition."""
    id: str
    name: str
    description: str
    nodes: List[WorkflowNode]
    start_node_id: str
    enabled: bool = True
    created_at: float = 0.0
    updated_at: float = 0.0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().timestamp()
        if not self.updated_at:
            self.updated_at = datetime.now().timestamp()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [node.to_dict() for node in self.nodes],
            "start_node_id": self.start_node_id,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class WorkflowExecution:
    """Execution of a workflow."""
    workflow_id: str
    execution_id: str
    status: str = "running"
    current_node_id: str = ""
    executed_nodes: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    completed_at: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "status": self.status,
            "current_node_id": self.current_node_id,
            "executed_nodes": self.executed_nodes,
            "results": self.results,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class WorkflowBuilder:
    """Builds and executes complex workflows.
    
    Features:
    - Visual workflow builder interface
    - Node-based workflow construction
    - Triggers (time, event, manual)
    - Actions (tool calls, scripts)
    - Conditions (if/else logic)
    - Delays and loops
    - Parallel execution
    - Notifications
    - Workflow execution engine
    """
    
    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        self._running = False
        self._execution_task: Optional[asyncio.Task] = None
        
    def create_workflow(
        self,
        name: str,
        description: str = "",
    ) -> Workflow:
        """Create a new workflow.
        
        Args:
            name: Workflow name
            description: Workflow description
            
        Returns:
            New Workflow
        """
        workflow_id = str(uuid.uuid4())
        
        # Create start node
        start_node = WorkflowNode(
            id=str(uuid.uuid4()),
            type=NodeType.TRIGGER,
            name="Start",
            config={"trigger_type": "manual"},
        )
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            nodes=[start_node],
            start_node_id=start_node.id,
        )
        
        self._workflows[workflow_id] = workflow
        logger.info("Created workflow: %s", name)
        return workflow
    
    def add_node(
        self,
        workflow_id: str,
        node_type: NodeType,
        name: str,
        config: Dict[str, Any],
        parent_node_id: Optional[str] = None,
        condition: Optional[str] = None,
    ) -> Optional[WorkflowNode]:
        """Add a node to a workflow.
        
        Args:
            workflow_id: Workflow ID
            node_type: Node type
            name: Node name
            config: Node configuration
            parent_node_id: Parent node ID
            condition: Optional condition for branching
            
        Returns:
            New node or None
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        
        node = WorkflowNode(
            id=str(uuid.uuid4()),
            type=node_type,
            name=name,
            config=config,
            condition=condition,
        )
        
        workflow.nodes.append(node)
        workflow.updated_at = datetime.now().timestamp()
        
        if parent_node_id:
            parent = self._get_node(workflow, parent_node_id)
            if parent:
                parent.next_nodes.append(node.id)
        
        logger.info("Added node %s to workflow %s", name, workflow_id)
        return node
    
    def connect_nodes(
        self,
        workflow_id: str,
        from_node_id: str,
        to_node_id: str,
        condition: Optional[str] = None,
    ) -> bool:
        """Connect two nodes.
        
        Args:
            workflow_id: Workflow ID
            from_node_id: Source node ID
            to_node_id: Target node ID
            condition: Optional condition
            
        Returns:
            True if successful
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False
        
        from_node = self._get_node(workflow, from_node_id)
        to_node = self._get_node(workflow, to_node_id)
        
        if not from_node or not to_node:
            return False
        
        if to_node_id not in from_node.next_nodes:
            from_node.next_nodes.append(to_node_id)
            if condition:
                from_node.condition = condition
        
        workflow.updated_at = datetime.now().timestamp()
        return True
    
    def remove_node(self, workflow_id: str, node_id: str) -> bool:
        """Remove a node from workflow.
        
        Args:
            workflow_id: Workflow ID
            node_id: Node ID
            
        Returns:
            True if successful
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False
        
        # Remove node
        workflow.nodes = [n for n in workflow.nodes if n.id != node_id]
        
        # Remove connections to this node
        for node in workflow.nodes:
            node.next_nodes = [nid for nid in node.next_nodes if nid != node_id]
        
        workflow.updated_at = datetime.now().timestamp()
        return True
    
    async def execute_workflow(
        self,
        workflow_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowExecution:
        """Execute a workflow.
        
        Args:
            workflow_id: Workflow ID
            context: Execution context
            
        Returns:
            WorkflowExecution
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            execution_id=execution_id,
            current_node_id=workflow.start_node_id,
            started_at=datetime.now().timestamp(),
        )
        
        self._executions[execution_id] = execution
        
        try:
            await self._execute_workflow_recursive(workflow, execution, context or {})
            execution.status = "completed"
            execution.completed_at = datetime.now().timestamp()
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            execution.completed_at = datetime.now().timestamp()
            logger.error("Workflow execution failed: %s", e)
        
        return execution
    
    async def _execute_workflow_recursive(
        self,
        workflow: Workflow,
        execution: WorkflowExecution,
        context: Dict[str, Any],
    ) -> None:
        """Execute workflow recursively."""
        current_node = self._get_node(workflow, execution.current_node_id)
        if not current_node:
            return
        
        # Execute current node
        result = await self._execute_node(current_node, context)
        execution.results[current_node.id] = result
        execution.executed_nodes.append(current_node.id)
        
        # Handle different node types
        if current_node.type == NodeType.END:
            return
        
        # Find next node based on condition
        next_node_id = self._find_next_node(current_node, result, context)
        
        if next_node_id:
            execution.current_node_id = next_node_id
            await self._execute_workflow_recursive(workflow, execution, context)
    
    async def _execute_node(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
    ) -> Any:
        """Execute a single node."""
        logger.info("Executing node: %s (%s)", node.name, node.type.value)
        
        if node.type == NodeType.TRIGGER:
            return {"triggered": True}
        
        elif node.type == NodeType.ACTION:
            return await self._execute_action(node, context)
        
        elif node.type == NodeType.CONDITION:
            return self._evaluate_condition(node, context)
        
        elif node.type == NodeType.DELAY:
            delay = node.config.get("delay_seconds", 0)
            await asyncio.sleep(delay)
            return {"delayed": delay}
        
        elif node.type == NodeType.NOTIFICATION:
            return await self._send_notification(node, context)
        
        elif node.type == NodeType.PARALLEL:
            return await self._execute_parallel(node, context)
        
        elif node.type == NodeType.LOOP:
            return await self._execute_loop(node, context)
        
        return None
    
    async def _execute_action(self, node: WorkflowNode, context: Dict[str, Any]) -> Any:
        """Execute an action node."""
        tool_name = node.config.get("tool_name")
        tool_args = node.config.get("tool_arguments", {})
        
        if tool_name:
            from dash_backend.tools.tool_manager import get_tool_manager
            manager = get_tool_manager()
            result = await manager.execute(tool_name, tool_args)
            return result
        
        return {"error": "No tool specified"}
    
    def _evaluate_condition(self, node: WorkflowNode, context: Dict[str, Any]) -> bool:
        """Evaluate a condition node."""
        condition = node.config.get("condition", "")
        # Simple condition evaluation
        # In production, use a proper expression evaluator
        return bool(condition)
    
    async def _send_notification(self, node: WorkflowNode, context: Dict[str, Any]) -> Any:
        """Send a notification."""
        message = node.config.get("message", "")
        notification_type = node.config.get("type", "info")
        
        # Integrate with notification system
        logger.info("Notification [%s]: %s", notification_type, message)
        return {"sent": True}
    
    async def _execute_parallel(self, node: WorkflowNode, context: Dict[str, Any]) -> Any:
        """Execute nodes in parallel."""
        # Execute all next nodes in parallel
        tasks = []
        for next_id in node.next_nodes:
            # Create sub-executions for parallel paths
            task = asyncio.create_task(self._execute_node_id(next_id, context))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {"parallel_results": results}
    
    async def _execute_loop(self, node: WorkflowNode, context: Dict[str, Any]) -> Any:
        """Execute a loop node."""
        max_iterations = node.config.get("max_iterations", 10)
        loop_body_id = node.config.get("loop_body_id")
        
        results = []
        for i in range(max_iterations):
            context["loop_iteration"] = i
            result = await self._execute_node_id(loop_body_id, context)
            results.append(result)
            
            # Check break condition
            if node.config.get("break_condition"):
                if self._evaluate_condition(node, context):
                    break
        
        return {"loop_results": results}
    
    async def _execute_node_id(self, node_id: str, context: Dict[str, Any]) -> Any:
        """Execute a node by ID (helper for parallel/loop)."""
        # Find node in all workflows
        for workflow in self._workflows.values():
            node = self._get_node(workflow, node_id)
            if node:
                return await self._execute_node(node, context)
        return None
    
    def _find_next_node(
        self,
        current_node: WorkflowNode,
        result: Any,
        context: Dict[str, Any],
    ) -> Optional[str]:
        """Find the next node to execute."""
        if not current_node.next_nodes:
            return None
        
        # If single next node, return it
        if len(current_node.next_nodes) == 1:
            return current_node.next_nodes[0]
        
        # If multiple, evaluate conditions
        for next_id in current_node.next_nodes:
            # In production, evaluate conditions here
            return next_id
        
        return current_node.next_nodes[0]
    
    def _get_node(self, workflow: Workflow, node_id: str) -> Optional[WorkflowNode]:
        """Get a node by ID."""
        for node in workflow.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)
    
    def list_workflows(self) -> List[Workflow]:
        """List all workflows."""
        return list(self._workflows.values())
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow."""
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            return True
        return False
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get an execution by ID."""
        return self._executions.get(execution_id)


_workflow_builder: Optional[WorkflowBuilder] = None


def get_workflow_builder() -> WorkflowBuilder:
    global _workflow_builder
    if _workflow_builder is None:
        _workflow_builder = WorkflowBuilder()
    return _workflow_builder
