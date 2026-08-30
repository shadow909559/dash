"""Session Manager - Maintain state between launches."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import asyncio
from pathlib import Path
from dash_backend.core.logging import get_logger
from dash_backend.core.global_context import get_global_context
from dash_backend.core.event_bus import get_event_bus, EventType

logger = get_logger(__name__)


@dataclass
class SessionState:
    session_id: str
    started_at: datetime
    last_activity: datetime
    conversation_id: str
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    voice_state: str = "idle"
    windows: List[Dict[str, Any]] = field(default_factory=list)
    devices: List[Dict[str, Any]] = field(default_factory=list)
    notifications: List[Dict[str, Any]] = field(default_factory=list)
    memory_refs: List[str] = field(default_factory=list)
    custom_data: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manage session state between launches."""
    
    def __init__(self, session_dir: str = ".dash/sessions"):
        self._session_dir = Path(session_dir)
        self._session_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_session: Optional[SessionState] = None
        self._context = get_global_context()
        self._event_bus = get_event_bus()
        self._lock = asyncio.Lock()
        
        logger.info(f"Session Manager initialized (dir: {session_dir})")
    
    async def start_session(self) -> SessionState:
        """Start a new session."""
        async with self._lock:
            session_id = f"session_{datetime.now().timestamp()}"
            
            self._current_session = SessionState(
                session_id=session_id,
                started_at=datetime.now(),
                last_activity=datetime.now(),
                conversation_id=self._context.conversation_id,
            )
            
            # Save session
            await self._save_session()
            
            # Publish event
            await self._event_bus.publish_sync(
                EventType.SESSION_SAVED,
                {"session_id": session_id},
                "session_manager"
            )
            
            logger.info(f"Session started: {session_id}")
            return self._current_session
    
    async def restore_session(self, session_id: str) -> Optional[SessionState]:
        """Restore a previous session."""
        async with self._lock:
            session_file = self._session_dir / f"{session_id}.json"
            
            if not session_file.exists():
                logger.warning(f"Session file not found: {session_id}")
                return None
            
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                # Convert datetime strings back to datetime objects
                data['started_at'] = datetime.fromisoformat(data['started_at'])
                data['last_activity'] = datetime.fromisoformat(data['last_activity'])
                
                self._current_session = SessionState(**data)
                
                # Restore context
                await self._context.set_conversation(self._current_session.conversation_id)
                
                # Publish event
                await self._event_bus.publish_sync(
                    EventType.SESSION_RESTORED,
                    {"session_id": session_id},
                    "session_manager"
                )
                
                logger.info(f"Session restored: {session_id}")
                return self._current_session
                
            except Exception as e:
                logger.error(f"Failed to restore session {session_id}: {e}")
                return None
    
    async def save_session(self) -> bool:
        """Save current session state."""
        async with self._lock:
            if not self._current_session:
                return False
            
            try:
                # Update session from context
                self._current_session.last_activity = datetime.now()
                self._current_session.conversation_id = self._context.conversation_id
                
                # Convert to JSON-serializable format
                session_data = {
                    "session_id": self._current_session.session_id,
                    "started_at": self._current_session.started_at.isoformat(),
                    "last_activity": self._current_session.last_activity.isoformat(),
                    "conversation_id": self._current_session.conversation_id,
                    "tasks": self._current_session.tasks,
                    "voice_state": self._current_session.voice_state,
                    "windows": self._current_session.windows,
                    "devices": self._current_session.devices,
                    "notifications": self._current_session.notifications,
                    "memory_refs": self._current_session.memory_refs,
                    "custom_data": self._current_session.custom_data,
                }
                
                session_file = self._session_dir / f"{self._current_session.session_id}.json"
                with open(session_file, 'w') as f:
                    json.dump(session_data, f, indent=2)
                
                # Publish event
                await self._event_bus.publish_sync(
                    EventType.SESSION_SAVED,
                    {"session_id": self._current_session.session_id},
                    "session_manager"
                )
                
                logger.debug(f"Session saved: {self._current_session.session_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to save session: {e}")
                return False
    
    async def end_session(self) -> bool:
        """End current session and save final state."""
        async with self._lock:
            if not self._current_session:
                return False
            
            await self.save_session()
            
            session_id = self._current_session.session_id
            self._current_session = None
            
            logger.info(f"Session ended: {session_id}")
            return True
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions."""
        async with self._lock:
            sessions = []
            
            for session_file in self._session_dir.glob("*.json"):
                try:
                    with open(session_file, 'r') as f:
                        data = json.load(f)
                    
                    sessions.append({
                        "session_id": data.get("session_id"),
                        "started_at": data.get("started_at"),
                        "last_activity": data.get("last_activity"),
                        "conversation_id": data.get("conversation_id"),
                    })
                except Exception as e:
                    logger.error(f"Failed to read session file {session_file}: {e}")
            
            # Sort by last activity (newest first)
            sessions.sort(key=lambda x: x.get("last_activity", ""), reverse=True)
            
            return sessions
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        async with self._lock:
            session_file = self._session_dir / f"{session_id}.json"
            
            if session_file.exists():
                session_file.unlink()
                logger.info(f"Session deleted: {session_id}")
                return True
            
            return False
    
    async def cleanup_old_sessions(self, days: int = 30) -> int:
        """Clean up sessions older than specified days."""
        async with self._lock:
            cutoff = datetime.now() - timedelta(days=days)
            deleted = 0
            
            for session_file in self._session_dir.glob("*.json"):
                try:
                    with open(session_file, 'r') as f:
                        data = json.load(f)
                    
                    last_activity = datetime.fromisoformat(data.get("last_activity", ""))
                    
                    if last_activity < cutoff:
                        session_file.unlink()
                        deleted += 1
                        
                except Exception as e:
                    logger.error(f"Failed to process session file {session_file}: {e}")
            
            logger.info(f"Cleaned up {deleted} old sessions")
            return deleted
    
    async def update_task(self, task_id: str, task_data: Dict[str, Any]) -> None:
        """Update task in session."""
        async with self._lock:
            if not self._current_session:
                return
            
            # Find and update task
            for i, task in enumerate(self._current_session.tasks):
                if task.get("id") == task_id:
                    self._current_session.tasks[i].update(task_data)
                    break
            else:
                # Add new task
                self._current_session.tasks.append({"id": task_id, **task_data})
            
            await self.save_session()
    
    async def add_window(self, window_data: Dict[str, Any]) -> None:
        """Add window to session."""
        async with self._lock:
            if not self._current_session:
                return
            
            self._current_session.windows.append(window_data)
            await self.save_session()
    
    async def add_device(self, device_data: Dict[str, Any]) -> None:
        """Add device to session."""
        async with self._lock:
            if not self._current_session:
                return
            
            self._current_session.devices.append(device_data)
            await self.save_session()
    
    async def add_notification(self, notification_data: Dict[str, Any]) -> None:
        """Add notification to session."""
        async with self._lock:
            if not self._current_session:
                return
            
            self._current_session.notifications.append(notification_data)
            await self.save_session()
    
    def get_current_session(self) -> Optional[SessionState]:
        """Get current session state."""
        return self._current_session


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
