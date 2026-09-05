"""
Permission Manager for DASH PC Control Operations

Provides approval workflow for sensitive desktop operations.
Requires user confirmation before executing high-risk actions.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class PermissionLevel(Enum):
    """Permission levels for different operation types."""
    SAFE = "safe"  # No approval needed (e.g., read operations)
    LOW = "low"  # Minimal approval (e.g., open applications)
    MEDIUM = "medium"  # Explicit approval (e.g., file operations)
    HIGH = "high"  # Strict approval (e.g., system changes)
    CRITICAL = "critical"  # Requires confirmation (e.g., shutdown, delete)


class PermissionRequest:
    """Represents a pending permission request."""

    def __init__(
        self,
        request_id: str,
        operation: str,
        level: PermissionLevel,
        description: str,
        parameters: Optional[Dict] = None,
    ):
        import time as _time

        self.request_id = request_id
        self.operation = operation
        self.level = level
        self.description = description
        self.parameters = parameters or {}
        self.approved: Optional[bool] = None
        self.timestamp: float = _time.time()


class PermissionManager:
    """Manages permission requests and approvals for desktop operations."""
    
    def __init__(self):
        self._pending_requests: Dict[str, PermissionRequest] = {}
        self._approval_history: List[Dict] = []
        self._auto_approve_safe = True  # Auto-approve safe operations
        self._remember_approvals = True  # Remember approvals for session
        self._approved_operations: set = set()  # Session-approved operations
        
    def get_permission_level(self, operation: str) -> PermissionLevel:
        """Determine permission level for a given operation."""
        # Critical operations - system-wide changes
        critical_ops = {
            "shutdown", "restart", "hibernate", "sleep", "logoff",
            "delete_file", "delete_folder", "empty_recycle_bin",
            "format_drive", "partition_disk",
            "modify_registry", "install_service", "stop_service",
        }
        
        # High operations - significant changes
        high_ops = {
            "move_file", "copy_file", "rename_file",
            "install_software", "uninstall_software",
            "modify_environment", "modify_startup",
            "change_display_settings", "modify_network",
        }
        
        # Medium operations - file operations, window management
        medium_ops = {
            "open_file", "save_file", "create_folder",
            "maximize_window", "minimize_window", "close_window",
            "run_command", "run_script", "run_powershell",
        }
        
        # Low operations - read operations, basic controls
        low_ops = {
            "read_file", "list_files", "search_files",
            "open_application", "open_url", "open_tab",
            "get_volume", "set_volume", "get_brightness",
            "list_processes", "list_services",
        }
        
        if operation in critical_ops:
            return PermissionLevel.CRITICAL
        elif operation in high_ops:
            return PermissionLevel.HIGH
        elif operation in medium_ops:
            return PermissionLevel.MEDIUM
        elif operation in low_ops:
            return PermissionLevel.LOW
        else:
            return PermissionLevel.SAFE
    
    def request_permission(
        self,
        operation: str,
        description: str,
        parameters: Optional[Dict] = None,
    ) -> PermissionRequest:
        """Request permission for an operation."""
        level = self.get_permission_level(operation)
        
        # Auto-approve safe operations
        if level == PermissionLevel.SAFE and self._auto_approve_safe:
            request = PermissionRequest(
                request_id=self._generate_id(),
                operation=operation,
                level=level,
                description=description,
                parameters=parameters,
            )
            request.approved = True
            return request
        
        # Check if operation was already approved in this session
        if self._remember_approvals and operation in self._approved_operations:
            request = PermissionRequest(
                request_id=self._generate_id(),
                operation=operation,
                level=level,
                description=description,
                parameters=parameters,
            )
            request.approved = True
            return request
        
        # Create pending request for approval
        request = PermissionRequest(
            request_id=self._generate_id(),
            operation=operation,
            level=level,
            description=description,
            parameters=parameters,
        )
        self._pending_requests[request.request_id] = request
        logger.info(
            "Permission request created: %s (level: %s)",
            operation,
            level.value,
        )
        return request
    
    def approve_request(self, request_id: str, remember: bool = True) -> bool:
        """Approve a pending permission request."""
        import time as _time

        if request_id not in self._pending_requests:
            logger.warning("Request not found: %s", request_id)
            return False

        request = self._pending_requests[request_id]
        # Stale-request protection: pending approvals expire after 10 minutes.
        import time as _time

        if _time.time() - request.timestamp > 600:
            del self._pending_requests[request_id]
            logger.warning("Request expired before approval: %s", request.operation)
            return False
        request.approved = True
        
        # Remember approval for session if requested
        if remember and self._remember_approvals:
            self._approved_operations.add(request.operation)
        
        # Add to history
        self._approval_history.append({
            "operation": request.operation,
            "level": request.level.value,
            "approved": True,
            "timestamp": request.timestamp,
        })
        
        # Remove from pending
        del self._pending_requests[request_id]
        
        logger.info("Permission approved: %s", request.operation)
        return True
    
    def deny_request(self, request_id: str) -> bool:
        """Deny a pending permission request."""
        if request_id not in self._pending_requests:
            logger.warning("Request not found: %s", request_id)
            return False
        
        request = self._pending_requests[request_id]
        request.approved = False
        
        # Add to history
        self._approval_history.append({
            "operation": request.operation,
            "level": request.level.value,
            "approved": False,
            "timestamp": request.timestamp,
        })
        
        # Remove from pending
        del self._pending_requests[request_id]
        
        logger.info("Permission denied: %s", request.operation)
        return True
    
    def get_pending_requests(self) -> List[PermissionRequest]:
        """Get all pending permission requests."""
        return list(self._pending_requests.values())
    
    def get_request(self, request_id: str) -> Optional[PermissionRequest]:
        """Get a specific permission request."""
        return self._pending_requests.get(request_id)
    
    def clear_approved_operations(self) -> None:
        """Clear session-approved operations."""
        self._approved_operations.clear()
        logger.info("Cleared approved operations cache")
    
    def get_approval_history(self, limit: int = 100) -> List[Dict]:
        """Get approval history."""
        return self._approval_history[-limit:]
    
    def _generate_id(self) -> str:
        """Generate a unique request ID."""
        import time
        import random
        return f"perm_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"


# Global permission manager instance
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """Get the global permission manager instance."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager
