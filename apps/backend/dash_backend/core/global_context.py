"""Global AI Context - Unified shared state across all modules."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


class ThinkingState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    REASONING = "reasoning"
    TOOL_SELECTION = "tool_selection"
    EXECUTING = "executing"
    VERIFYING = "verifying"


class DeviceType(str, Enum):
    DESKTOP = "desktop"
    ANDROID = "android"
    WEB = "web"


@dataclass
class WindowInfo:
    title: str
    application: str
    process_id: Optional[int] = None
    position: Optional[Dict[str, int]] = None
    size: Optional[Dict[str, int]] = None
    is_focused: bool = False


@dataclass
class FileInfo:
    path: str
    name: str
    size: int
    type: str
    last_modified: datetime
    is_selected: bool = False


@dataclass
class TaskInfo:
    id: str
    description: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class UserProfile:
    user_id: str
    name: str
    preferences: Dict[str, Any] = field(default_factory=dict)
    voice_settings: Dict[str, Any] = field(default_factory=dict)
    accessibility_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceStatus:
    device_type: DeviceType
    device_id: str
    is_online: bool
    battery_level: Optional[int] = None
    is_charging: bool = False
    last_seen: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationContext:
    conversation_id: str
    message_count: int
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    summary: Optional[str] = None


class GlobalAIContext:
    """Central shared context for all DASH modules."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        
        # Conversation
        self.conversation_id: str = ""
        self.conversation_context: Optional[ConversationContext] = None
        
        # Task management
        self.current_task: Optional[TaskInfo] = None
        self.previous_task: Optional[TaskInfo] = None
        self.task_history: List[TaskInfo] = []
        
        # Desktop state
        self.current_window: Optional[WindowInfo] = None
        self.current_application: Optional[str] = None
        self.selected_files: List[FileInfo] = []
        self.clipboard_content: Optional[str] = None
        
        # Voice state
        self.voice_state: VoiceState = VoiceState.IDLE
        self.voice_provider: str = "openai"
        self.current_speech: Optional[str] = None
        
        # Thinking state
        self.thinking_state: ThinkingState = ThinkingState.IDLE
        self.thinking_progress: float = 0.0
        self.thinking_steps: List[str] = []
        
        # User profile
        self.user_profile: Optional[UserProfile] = None
        
        # Device status
        self.connected_devices: Dict[str, DeviceStatus] = {}
        self.primary_device: Optional[str] = None
        
        # Memory references
        self.recent_memories: List[str] = []
        self.current_context_tokens: int = 0
        
        # Notifications
        self.active_notifications: List[Dict[str, Any]] = []
        
        # Skills
        self.loaded_skills: List[str] = []
        self.active_skill: Optional[str] = None
        
        # Model
        self.current_model: str = "gpt-4"
        self.model_capabilities: List[str] = []
        
        # Services status
        self.service_status: Dict[str, bool] = {}
        
        # Internet
        self.internet_available: bool = True
        
        logger.info("Global AI Context initialized")
    
    async def set_conversation(self, conversation_id: str) -> None:
        """Set current conversation."""
        async with self._lock:
            self.conversation_id = conversation_id
            self.conversation_context = ConversationContext(
                conversation_id=conversation_id,
                message_count=0,
            )
            logger.info(f"Conversation set: {conversation_id}")
    
    async def set_current_task(self, task: TaskInfo) -> None:
        """Set current task and move previous to history."""
        async with self._lock:
            if self.current_task:
                self.previous_task = self.current_task
                self.task_history.append(self.current_task)
                # Keep only last 100 tasks
                if len(self.task_history) > 100:
                    self.task_history.pop(0)
            
            self.current_task = task
            logger.info(f"Current task set: {task.id}")
    
    async def complete_current_task(self, result: Any = None, error: str = None) -> None:
        """Mark current task as complete."""
        async with self._lock:
            if self.current_task:
                self.current_task.status = "completed" if not error else "failed"
                self.current_task.completed_at = datetime.now()
                self.current_task.result = result
                self.current_task.error = error
                
                self.task_history.append(self.current_task)
                self.previous_task = self.current_task
                self.current_task = None
                
                logger.info(f"Task completed: {self.current_task.id if self.current_task else 'N/A'}")
    
    async def set_current_window(self, window: WindowInfo) -> None:
        """Set current focused window."""
        async with self._lock:
            self.current_window = window
            self.current_application = window.application
            logger.debug(f"Current window: {window.title}")
    
    async def set_selected_files(self, files: List[FileInfo]) -> None:
        """Set selected files."""
        async with self._lock:
            self.selected_files = files
            logger.debug(f"Selected {len(files)} files")
    
    async def set_clipboard(self, content: str) -> None:
        """Set clipboard content."""
        async with self._lock:
            self.clipboard_content = content
            logger.debug("Clipboard updated")
    
    async def set_voice_state(self, state: VoiceState) -> None:
        """Set voice state."""
        async with self._lock:
            self.voice_state = state
            logger.debug(f"Voice state: {state}")
    
    async def set_thinking_state(self, state: ThinkingState, progress: float = 0.0) -> None:
        """Set thinking state."""
        async with self._lock:
            self.thinking_state = state
            self.thinking_progress = progress
            logger.debug(f"Thinking state: {state} ({progress:.1%})")
    
    async def add_thinking_step(self, step: str) -> None:
        """Add a thinking step."""
        async with self._lock:
            self.thinking_steps.append(step)
            logger.debug(f"Thinking step: {step}")
    
    async def clear_thinking_steps(self) -> None:
        """Clear thinking steps."""
        async with self._lock:
            self.thinking_steps = []
    
    async def set_user_profile(self, profile: UserProfile) -> None:
        """Set user profile."""
        async with self._lock:
            self.user_profile = profile
            logger.info(f"User profile set: {profile.user_id}")
    
    async def add_device(self, device: DeviceStatus) -> None:
        """Add or update connected device."""
        async with self._lock:
            self.connected_devices[device.device_id] = device
            if not self.primary_device:
                self.primary_device = device.device_id
            logger.info(f"Device added: {device.device_id} ({device.device_type})")
    
    async def remove_device(self, device_id: str) -> None:
        """Remove connected device."""
        async with self._lock:
            if device_id in self.connected_devices:
                del self.connected_devices[device_id]
                if self.primary_device == device_id:
                    self.primary_device = next(iter(self.connected_devices), None)
                logger.info(f"Device removed: {device_id}")
    
    async def set_device_online(self, device_id: str, online: bool) -> None:
        """Set device online status."""
        async with self._lock:
            if device_id in self.connected_devices:
                self.connected_devices[device_id].is_online = online
                self.connected_devices[device_id].last_seen = datetime.now()
                logger.debug(f"Device {device_id} online: {online}")
    
    async def add_notification(self, notification: Dict[str, Any]) -> None:
        """Add notification."""
        async with self._lock:
            self.active_notifications.append(notification)
            logger.debug(f"Notification added: {notification.get('title', 'N/A')}")
    
    async def dismiss_notification(self, notification_id: str) -> None:
        """Dismiss notification."""
        async with self._lock:
            self.active_notifications = [
                n for n in self.active_notifications 
                if n.get('id') != notification_id
            ]
            logger.debug(f"Notification dismissed: {notification_id}")
    
    async def load_skill(self, skill_name: str) -> None:
        """Load skill."""
        async with self._lock:
            if skill_name not in self.loaded_skills:
                self.loaded_skills.append(skill_name)
                logger.info(f"Skill loaded: {skill_name}")
    
    async def set_active_skill(self, skill_name: str) -> None:
        """Set active skill."""
        async with self._lock:
            self.active_skill = skill_name
            logger.info(f"Active skill: {skill_name}")
    
    async def set_model(self, model: str, capabilities: List[str]) -> None:
        """Set current model."""
        async with self._lock:
            self.current_model = model
            self.model_capabilities = capabilities
            logger.info(f"Model set: {model}")
    
    async def set_service_status(self, service: str, status: bool) -> None:
        """Set service status."""
        async with self._lock:
            self.service_status[service] = status
            logger.debug(f"Service {service}: {status}")
    
    async def set_internet_available(self, available: bool) -> None:
        """Set internet availability."""
        async with self._lock:
            self.internet_available = available
            logger.info(f"Internet available: {available}")
    
    async def get_full_context(self) -> Dict[str, Any]:
        """Get full context snapshot."""
        async with self._lock:
            return {
                "conversation": {
                    "id": self.conversation_id,
                    "context": self.conversation_context,
                },
                "task": {
                    "current": self.current_task,
                    "previous": self.previous_task,
                    "history": self.task_history[-10:],  # Last 10
                },
                "desktop": {
                    "window": self.current_window,
                    "application": self.current_application,
                    "selected_files": self.selected_files,
                    "clipboard": self.clipboard_content,
                },
                "voice": {
                    "state": self.voice_state,
                    "provider": self.voice_provider,
                    "current_speech": self.current_speech,
                },
                "thinking": {
                    "state": self.thinking_state,
                    "progress": self.thinking_progress,
                    "steps": self.thinking_steps,
                },
                "user": self.user_profile,
                "devices": {
                    "connected": self.connected_devices,
                    "primary": self.primary_device,
                },
                "memory": {
                    "recent": self.recent_memories,
                    "context_tokens": self.current_context_tokens,
                },
                "notifications": self.active_notifications,
                "skills": {
                    "loaded": self.loaded_skills,
                    "active": self.active_skill,
                },
                "model": {
                    "current": self.current_model,
                    "capabilities": self.model_capabilities,
                },
                "services": self.service_status,
                "internet": self.internet_available,
            }
    
    async def reset(self) -> None:
        """Reset context (for testing or session reset)."""
        async with self._lock:
            self.conversation_id = ""
            self.conversation_context = None
            self.current_task = None
            self.previous_task = None
            self.task_history = []
            self.current_window = None
            self.current_application = None
            self.selected_files = []
            self.clipboard_content = None
            self.voice_state = VoiceState.IDLE
            self.thinking_state = ThinkingState.IDLE
            self.thinking_progress = 0.0
            self.thinking_steps = []
            self.active_notifications = []
            self.active_skill = None
            logger.info("Global AI Context reset")


# Singleton instance
_global_context: Optional[GlobalAIContext] = None


def get_global_context() -> GlobalAIContext:
    """Get or create global context singleton."""
    global _global_context
    if _global_context is None:
        _global_context = GlobalAIContext()
    return _global_context
