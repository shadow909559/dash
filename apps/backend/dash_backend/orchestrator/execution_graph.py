"""Execution Graph - DAG-based task execution with dependency resolution.

Supports:
- Directed Acyclic Graph (DAG) construction from planner tasks
- Dependency resolution for parallel execution
- Topological sorting for optimal execution order
- Output passing between dependent tasks
- Partial result preservation on failure
- Dynamic graph modification during execution
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Status of a task in the execution graph."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class TaskNode:
    """A single task node in the execution graph."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    tool: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempt: int = 0
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "tool": self.tool,
            "tool_args": self.tool_args,
            "result": self.result,
            "error": self.error,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
        }


class ExecutionGraph:
    """DAG-based execution graph for task orchestration.

    Supports:
    - Adding tasks with dependencies
    - Resolving execution order (topological sort)
    - Determining ready tasks (all dependencies met)
    - Passing outputs between tasks
    - Handling task failures and retries
    - Dynamic graph modification
    """

    def __init__(self):
        self._nodes: Dict[str, TaskNode] = {}
        self._node_order: List[str] = []  # Track insertion order
        self._context: Dict[str, Any] = {}  # Shared execution context

    # ──────────────────────────────────────────────
    # Node Management
    # ──────────────────────────────────────────────

    def add_node(self, node: TaskNode) -> str:
        """Add a task node to the graph.

        Args:
            node: The task node to add.

        Returns:
            The task_id of the added node.
        """
        self._nodes[node.task_id] = node
        self._node_order.append(node.task_id)
        logger.debug("Added task node: %s (%s)", node.name, node.task_id)
        return node.task_id

    def add_nodes(self, nodes: List[TaskNode]) -> List[str]:
        """Add multiple task nodes to the graph."""
        return [self.add_node(n) for n in nodes]

    def get_node(self, task_id: str) -> Optional[TaskNode]:
        """Get a task node by ID."""
        return self._nodes.get(task_id)

    def remove_node(self, task_id: str) -> bool:
        """Remove a task node from the graph."""
        if task_id in self._nodes:
            del self._nodes[task_id]
            self._node_order = [n for n in self._node_order if n != task_id]
            return True
        return False

    def has_node(self, task_id: str) -> bool:
        """Check if a node exists in the graph."""
        return task_id in self._nodes

    @property
    def size(self) -> int:
        """Number of nodes in the graph."""
        return len(self._nodes)

    @property
    def nodes(self) -> List[TaskNode]:
        """All nodes in insertion order."""
        return [self._nodes[nid] for nid in self._node_order if nid in self._nodes]

    @property
    def is_empty(self) -> bool:
        """Check if the graph has no nodes."""
        return len(self._nodes) == 0

    # ──────────────────────────────────────────────
    # Dependency Resolution
    # ──────────────────────────────────────────────

    def get_dependencies(self, task_id: str) -> List[TaskNode]:
        """Get all dependency nodes for a task."""
        node = self._nodes.get(task_id)
        if not node:
            return []
        return [self._nodes.get(dep_id) for dep_id in node.depends_on if dep_id in self._nodes]

    def get_dependents(self, task_id: str) -> List[TaskNode]:
        """Get all nodes that depend on a given task."""
        return [n for n in self._nodes.values() if task_id in n.depends_on]

    def get_ready_tasks(self) -> List[TaskNode]:
        """Get all tasks that are ready to execute (dependencies met)."""
        ready = []
        for node in self._nodes.values():
            if node.status != TaskStatus.PENDING:
                continue
            if self._are_dependencies_met(node):
                node.status = TaskStatus.READY
                ready.append(node)
        return ready

    def _are_dependencies_met(self, node: TaskNode) -> bool:
        """Check if all dependencies of a node are completed."""
        if not node.depends_on:
            return True
        for dep_id in node.depends_on:
            dep = self._nodes.get(dep_id)
            if dep is None:
                logger.warning("Dependency %s not found for task %s", dep_id, node.task_id)
                continue
            if dep.status == TaskStatus.FAILED:
                # If a dependency failed, this task is blocked
                node.status = TaskStatus.BLOCKED
                return False
            if dep.status != TaskStatus.COMPLETED:
                return False
        return True

    def get_execution_layers(self) -> List[List[TaskNode]]:
        """Resolve tasks into parallel execution layers.

        Returns layers where each layer contains tasks that can run in parallel.
        Uses topological sorting with Kahn's algorithm.
        """
        # Build in-degree map
        in_degree: Dict[str, int] = {}
        for node in self._nodes.values():
            in_degree[node.task_id] = 0

        for node in self._nodes.values():
            for dep_id in node.depends_on:
                if dep_id in self._nodes:
                    in_degree[node.task_id] = in_degree.get(node.task_id, 0) + 1

        # Kahn's algorithm
        layers: List[List[TaskNode]] = []
        queue = [
            nid for nid, degree in in_degree.items() if degree == 0
        ]

        visited: Set[str] = set()
        while queue:
            current_layer: List[TaskNode] = []
            next_queue: List[str] = []

            for nid in queue:
                if nid in visited:
                    continue
                visited.add(nid)
                node = self._nodes.get(nid)
                if node:
                    current_layer.append(node)

                # Decrease in-degree of dependents
                for dep_node in self.get_dependents(nid):
                    dep_id = dep_node.task_id
                    if dep_id in in_degree:
                        in_degree[dep_id] -= 1
                        if in_degree[dep_id] == 0 and dep_id not in visited:
                            next_queue.append(dep_id)

            if current_layer:
                layers.append(current_layer)
            queue = next_queue

        # Check for remaining nodes (circular dependencies)
        remaining = [nid for nid in self._nodes if nid not in visited]
        if remaining:
            logger.warning("Circular dependency detected for tasks: %s", remaining)
            for nid in remaining:
                node = self._nodes.get(nid)
                if node:
                    node.status = TaskStatus.BLOCKED
                    node.error = "Circular dependency detected"

        return layers

    # ──────────────────────────────────────────────
    # Output Passing
    # ──────────────────────────────────────────────

    def pass_output(self, from_task_id: str, to_task_id: str, output_key: str, input_key: Optional[str] = None) -> bool:
        """Pass an output from one task to another's input.

        Args:
            from_task_id: Source task ID
            to_task_id: Destination task ID
            output_key: Key in the source task's outputs
            input_key: Key in the destination task's inputs (defaults to output_key)

        Returns:
            True if the output was passed successfully.
        """
        source = self._nodes.get(from_task_id)
        dest = self._nodes.get(to_task_id)

        if not source or not dest:
            return False

        if output_key not in source.outputs:
            return False

        input_key = input_key or output_key
        dest.inputs[input_key] = source.outputs[output_key]
        return True

    def pass_outputs_to_dependents(self, task_id: str) -> int:
        """Pass all outputs of a completed task to its dependents.

        Returns the number of outputs passed.
        """
        count = 0
        node = self._nodes.get(task_id)
        if not node:
            return count

        for dep_node in self.get_dependents(task_id):
            for key, value in node.outputs.items():
                dep_node.inputs[key] = value
                count += 1

        return count

    # ──────────────────────────────────────────────
    # Status Management
    # ──────────────────────────────────────────────

    def mark_running(self, task_id: str) -> bool:
        """Mark a task as running."""
        node = self._nodes.get(task_id)
        if node:
            node.status = TaskStatus.RUNNING
            node.started_at = datetime.now(timezone.utc)
            return True
        return False

    def mark_completed(self, task_id: str, outputs: Optional[Dict[str, Any]] = None) -> bool:
        """Mark a task as completed with optional outputs."""
        node = self._nodes.get(task_id)
        if node:
            node.status = TaskStatus.COMPLETED
            node.completed_at = datetime.now(timezone.utc)
            if outputs:
                node.outputs = outputs
            self.pass_outputs_to_dependents(task_id)
            return True
        return False

    def mark_failed(self, task_id: str, error: str, should_retry: bool = True) -> bool:
        """Mark a task as failed."""
        node = self._nodes.get(task_id)
        if node:
            node.error = error
            node.attempt += 1

            if should_retry and node.attempt < node.max_attempts:
                node.status = TaskStatus.PENDING
                logger.info(
                    "Task %s (%s) failed, retrying (attempt %d/%d): %s",
                    task_id, node.name, node.attempt, node.max_attempts, error,
                )
            else:
                node.status = TaskStatus.FAILED
                logger.warning(
                    "Task %s (%s) failed permanently after %d attempts: %s",
                    task_id, node.name, node.attempt, error,
                )
                # Mark dependent tasks as blocked
                for dep_node in self.get_dependents(task_id):
                    dep_node.status = TaskStatus.BLOCKED
                    dep_node.error = f"Dependency {node.name} failed"

            return True
        return False

    def mark_skipped(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as skipped."""
        node = self._nodes.get(task_id)
        if node:
            node.status = TaskStatus.SKIPPED
            node.error = reason
            return True
        return False

    def get_status_summary(self) -> Dict[str, int]:
        """Get a summary of task statuses."""
        summary = {s.value: 0 for s in TaskStatus}
        for node in self._nodes.values():
            summary[node.status.value] = summary.get(node.status.value, 0) + 1
        return summary

    # ──────────────────────────────────────────────
    # Context Management
    # ──────────────────────────────────────────────

    def set_context_value(self, key: str, value: Any) -> None:
        """Set a value in the shared execution context."""
        self._context[key] = value

    def get_context_value(self, key: str, default: Any = None) -> Any:
        """Get a value from the shared execution context."""
        return self._context.get(key, default)

    # ──────────────────────────────────────────────
    # Serialization
    # ──────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph to a dictionary."""
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "context": self._context,
            "status_summary": self.get_status_summary(),
        }

    @classmethod
    def from_planner_tasks(cls, tasks: List[Dict[str, Any]]) -> "ExecutionGraph":
        """Create an execution graph from planner task descriptions.

        Args:
            tasks: List of task dicts from the planner (with name, description,
                  depends_on, tools, etc.)

        Returns:
            An ExecutionGraph populated with TaskNodes.
        """
        graph = cls()

        for task_data in tasks:
            node = TaskNode(
                name=task_data.get("name", "Unnamed Task"),
                description=task_data.get("description", ""),
                depends_on=[],  # Resolve dependency names to IDs later
                tool=task_data.get("tool"),
                tool_args=task_data.get("tool_args", {}),
                max_attempts=task_data.get("max_attempts", 3),
                metadata=task_data.get("metadata", {}),
            )
            graph.add_node(node)

        # Resolve dependency names to IDs
        name_to_id = {n.name: n.task_id for n in graph.nodes}
        for node in graph.nodes:
            original_deps = []
            # Find the original task data
            for task_data in tasks:
                if task_data.get("name") == node.name:
                    original_deps = task_data.get("depends_on", [])
                    break
            node.depends_on = [
                name_to_id.get(dep_name, dep_name)
                for dep_name in original_deps
                if dep_name in name_to_id
            ]

        return graph


def create_graph_from_plan(plan_tasks: List[Dict[str, Any]]) -> ExecutionGraph:
    """Convenience function to create an execution graph from a plan."""
    return ExecutionGraph.from_planner_tasks(plan_tasks)
