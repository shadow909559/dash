"""
AI Provider Health Monitor
Monitors the health of the configured AI provider (Ollama/OpenAI) in the background.
Publishes health status updates to the event bus and WebSocket so frontend can stay informed.
Does NOT block application startup if the provider is unavailable.
Integrates with OllamaManager for auto-start and recovery.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

from dash_backend.logging_config import get_logger
from dash_backend.config import get_settings
from dash_backend.llm.service import check_provider_health
from dash_backend.llm.provider_manager import get_ollama_manager, ProviderStatus, ProviderHealth
from dash_backend.events.event_bus import get_event_bus

logger = get_logger(__name__)

@dataclass
class ProviderHealthStatus:
    healthy: bool = False
    last_check: float = 0
    provider: str = ""
    configured_model: Optional[str] = None
    model_available: bool = False
    installed_models: list[str] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    status: str = "checking"  # checking, starting, ready, model_missing, unavailable, error
    message: str = "Checking AI provider..."  # User-friendly message

    def __post_init__(self):
        if self.installed_models is None:
            self.installed_models = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "last_check": self.last_check,
            "provider": self.provider,
            "configured_model": self.configured_model,
            "model_available": self.model_available,
            "installed_models": self.installed_models,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "message": self.message,
        }

class AIProviderHealthMonitor:
    """Background service that monitors AI provider health."""
    
    _instance: Optional["AIProviderHealthMonitor"] = None
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_status = ProviderHealthStatus()
        self._check_interval = 30  # Check every 30 seconds by default
        self._settings = get_settings()
        self._ollama_manager = get_ollama_manager()
        self._websocket_manager = None  # Will be set if available
    
    @classmethod
    def get_instance(cls) -> "AIProviderHealthMonitor":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = AIProviderHealthMonitor()
        return cls._instance
    
    @property
    def current_status(self) -> ProviderHealthStatus:
        """Get the latest health status."""
        return self._current_status
    
    def is_healthy(self) -> bool:
        """Return whether the provider is currently healthy."""
        return self._current_status.healthy
    
    async def start(self):
        """Start the health monitor."""
        if self._running:
            logger.warning("AI Provider Health Monitor already running")
            return
        
        self._running = True
        logger.info("Starting AI Provider Health Monitor")
        
        # Do an initial check immediately
        await self._check_and_publish()
        
        # Start the background monitoring loop
        self._task = asyncio.create_task(self._monitoring_loop())
    
    async def stop(self):
        """Stop the health monitor."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("AI Provider Health Monitor stopped")
    
    async def _monitoring_loop(self):
        """Background loop that periodically checks provider health."""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_and_publish()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in AI provider health monitoring loop")
                await asyncio.sleep(5)  # Short delay before retrying
    
    async def _check_and_publish(self):
        """Check provider health and publish updates to event bus and WebSocket."""
        try:
            # Use OllamaManager for comprehensive health check with auto-start
            provider_health = await self._ollama_manager.ensure_provider_ready()

            # Update current status
            previous_health = self._current_status.healthy
            previous_status = self._current_status.status

            self._current_status.healthy = provider_health.status == ProviderStatus.READY
            self._current_status.last_check = time.time()
            self._current_status.provider = provider_health.provider
            self._current_status.configured_model = provider_health.configured_model
            self._current_status.model_available = provider_health.model_available
            self._current_status.installed_models = provider_health.installed_models
            self._current_status.error = provider_health.error
            self._current_status.latency_ms = provider_health.latency_ms
            self._current_status.status = provider_health.status.value
            self._current_status.message = provider_health.message

            # Log status change
            if previous_health != self._current_status.healthy:
                if self._current_status.healthy:
                    logger.info("AI provider is now HEALTHY: %s", provider_health.message)
                else:
                    logger.warning("AI provider is now UNHEALTHY: %s", provider_health.error or provider_health.message)

            if previous_status != self._current_status.status:
                logger.info("AI provider status changed: %s -> %s", previous_status, self._current_status.status)

            # Publish to event bus
            event_bus = get_event_bus()
            await event_bus.publish_sync(
                topic="ai.provider.health",
                data=self._current_status.to_dict(),
                source="ai_provider_health_monitor",
            )

            # Publish to WebSocket directly (not wrapped in notification.push)
            try:
                from dash_backend.api.routes.notifications import _websocket_connections
                from dash_backend.auth.dependencies import resolve_owner_user
                from dash_backend.db.session import AsyncSessionLocal

                # Get owner user ID for WebSocket broadcast
                async with AsyncSessionLocal() as session:
                    owner_user = await resolve_owner_user(session)
                    user_id = str(owner_user.id)

                # Send directly to WebSocket connections without notification.push wrapper
                if user_id in _websocket_connections:
                    import asyncio
                    for ws in _websocket_connections[user_id]:
                        try:
                            await ws.send_json({
                                "type": "ai.provider.status",
                                "status": self._current_status.status,
                                "provider": self._current_status.provider,
                                "configured_model": self._current_status.configured_model,
                                "model_available": self._current_status.model_available,
                                "installed_models": self._current_status.installed_models,
                                "error": self._current_status.error,
                                "latency_ms": self._current_status.latency_ms,
                                "message": self._current_status.message,
                            })
                        except Exception:
                            # Remove dead connections
                            _websocket_connections[user_id].remove(ws)
                logger.debug("Published provider status to WebSocket for user %s", user_id)
            except Exception:
                logger.exception("Failed to publish provider status to WebSocket")

        except Exception as e:
            logger.exception("Failed to check AI provider health")
            # Update status with error
            self._current_status.healthy = False
            self._current_status.status = "error"
            self._current_status.error = str(e)
            self._current_status.message = "AI engine check failed."
            self._current_status.last_check = time.time()
    
    async def force_check(self) -> Dict[str, Any]:
        """Force an immediate health check and return the result."""
        await self._check_and_publish()
        return self._current_status.to_dict()

# Global instance getter to match service patterns
def get_ai_provider_health_monitor() -> AIProviderHealthMonitor:
    """Get the singleton AI provider health monitor instance."""
    return AIProviderHealthMonitor.get_instance()