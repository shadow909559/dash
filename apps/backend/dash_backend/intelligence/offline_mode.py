"""Offline Mode - Offline functionality and synchronization."""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import json
from pathlib import Path

from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


class SyncStatus(Enum):
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"


@dataclass
class OfflineAction:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sync_status: SyncStatus = SyncStatus.PENDING
    retry_count: int = 0
    error: Optional[str] = None


class OfflineMode:
    """Manages offline functionality and synchronization."""
    
    def __init__(self, storage_path: str = "offline_cache"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.is_online = True
        self.offline_actions: List[OfflineAction] = []
        self.local_cache: Dict[str, Any] = {}
        self.sync_queue: asyncio.Queue[OfflineAction] = asyncio.Queue()
        self.is_syncing = False
        # Injectable async callable (action_type, parameters) -> Any that
        # performs the action against the live service.
        self._online_handler: Optional[Any] = None
        
        # Load cached data
        self._load_cache()
        self._load_offline_actions()
    
    def _load_cache(self) -> None:
        """Load local cache from disk."""
        cache_file = self.storage_path / "cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    self.local_cache = json.load(f)
                logger.info(f"Loaded local cache with {len(self.local_cache)} entries")
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")
    
    def _save_cache(self) -> None:
        """Save local cache to disk."""
        cache_file = self.storage_path / "cache.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(self.local_cache, f, default=str)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _load_offline_actions(self) -> None:
        """Load offline actions from disk."""
        actions_file = self.storage_path / "actions.json"
        if actions_file.exists():
            try:
                with open(actions_file, "r") as f:
                    actions_data = json.load(f)
                    self.offline_actions = [
                        OfflineAction(**action) for action in actions_data
                    ]
                logger.info(f"Loaded {len(self.offline_actions)} offline actions")
            except Exception as e:
                logger.error(f"Failed to load offline actions: {e}")
    
    def _save_offline_actions(self) -> None:
        """Save offline actions to disk."""
        actions_file = self.storage_path / "actions.json"
        try:
            with open(actions_file, "w") as f:
                json.dump(
                    [action.__dict__ for action in self.offline_actions],
                    f,
                    default=str
                )
        except Exception as e:
            logger.error(f"Failed to save offline actions: {e}")
    
    def set_online(self, online: bool) -> None:
        """Set online/offline status."""
        self.is_online = online
        logger.info(f"Set online status: {online}")
        
        if online and not self.is_syncing:
            asyncio.create_task(self._sync_offline_actions())
    
    async def execute_action(self, action_type: str, parameters: Dict[str, Any], online_only: bool = False) -> Any:
        """Execute an action, handling offline mode."""
        if self.is_online or not online_only:
            # Execute online
            try:
                result = await self._execute_online(action_type, parameters)
                return result
            except Exception as e:
                logger.error(f"Online execution failed: {e}")
                if not online_only:
                    # Fall back to offline
                    return await self._execute_offline(action_type, parameters)
                raise
        else:
            # Execute offline
            return await self._execute_offline(action_type, parameters)
    
    def set_online_handler(self, handler) -> None:
        """Register the async callable that executes actions online.

        Args:
            handler: Async callable ``(action_type, parameters) -> Any``.
        """
        self._online_handler = handler
        logger.info("Online execution handler registered")

    async def _execute_online(self, action_type: str, parameters: Dict[str, Any]) -> Any:
        """Execute action online via the registered handler."""
        if self._online_handler is None:
            raise NotImplementedError("Online execution handler not set")
        return await self._online_handler(action_type, parameters)
    
    async def _execute_offline(self, action_type: str, parameters: Dict[str, Any]) -> Any:
        """Execute action offline and queue for sync."""
        action = OfflineAction(
            action_type=action_type,
            parameters=parameters,
        )
        
        self.offline_actions.append(action)
        await self.sync_queue.put(action)
        self._save_offline_actions()
        
        logger.info(f"Executed offline action: {action_type}")
        
        # Return a placeholder result
        return {"status": "offline_queued", "action_id": action.id}
    
    async def _sync_offline_actions(self) -> None:
        """Sync offline actions when back online."""
        if self.is_syncing:
            return
        
        self.is_syncing = True
        logger.info("Starting offline action sync")
        
        try:
            while not self.sync_queue.empty():
                action = await self.sync_queue.get()
                
                try:
                    # Retry online execution
                    result = await self._execute_online(action.action_type, action.parameters)
                    
                    # Update status
                    action.sync_status = SyncStatus.SYNCED
                    logger.info(f"Synced action: {action.action_type}")
                
                except Exception as e:
                    action.sync_status = SyncStatus.FAILED
                    action.error = str(e)
                    action.retry_count += 1
                    
                    if action.retry_count < 3:
                        # Re-queue for retry
                        await self.sync_queue.put(action)
                        logger.warning(f"Sync failed, re-queueing: {action.action_type}")
                    else:
                        logger.error(f"Sync failed permanently: {action.action_type}: {e}")
                
                self._save_offline_actions()
        
        finally:
            self.is_syncing = False
            logger.info("Offline action sync completed")
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Get value from local cache."""
        return self.local_cache.get(key)
    
    def cache_set(self, key: str, value: Any) -> None:
        """Set value in local cache."""
        self.local_cache[key] = value
        self._save_cache()
    
    def cache_delete(self, key: str) -> bool:
        """Delete value from local cache."""
        if key in self.local_cache:
            del self.local_cache[key]
            self._save_cache()
            return True
        return False
    
    def get_offline_actions(self) -> List[OfflineAction]:
        """Get all offline actions."""
        return self.offline_actions.copy()
    
    def get_pending_sync_count(self) -> int:
        """Get count of pending sync actions."""
        return len([a for a in self.offline_actions if a.sync_status == SyncStatus.PENDING])
    
    def clear_offline_actions(self) -> None:
        """Clear all offline actions."""
        self.offline_actions.clear()
        self._save_offline_actions()
        logger.info("Cleared all offline actions")
    
    def get_status(self) -> Dict[str, Any]:
        """Get offline mode status."""
        return {
            "is_online": self.is_online,
            "is_syncing": self.is_syncing,
            "pending_sync_count": self.get_pending_sync_count(),
            "total_offline_actions": len(self.offline_actions),
            "cache_size": len(self.local_cache),
        }
