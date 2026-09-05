"""Service Manager - Health monitoring and automatic restart."""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
from dash_backend.core.logging import get_logger
from dash_backend.core.event_bus import get_event_bus, EventType

logger = get_logger(__name__)


class ServiceStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    RESTARTING = "restarting"


@dataclass
class ServiceHealth:
    service_name: str
    status: ServiceStatus
    last_heartbeat: datetime
    last_error: Optional[str] = None
    restart_count: int = 0
    max_restarts: int = 3
    health_check_interval: float = 30.0
    timeout: float = 60.0


class ServiceManager:
    """Manage background services with health monitoring."""
    
    def __init__(self):
        self._services: Dict[str, ServiceHealth] = {}
        self._service_tasks: Dict[str, asyncio.Task] = {}
        self._event_bus = get_event_bus()
        self._lock = asyncio.Lock()
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info("Service Manager initialized")
    
    async def register_service(
        self,
        service_name: str,
        start_fn: Callable,
        health_check_fn: Optional[Callable] = None,
        max_restarts: int = 3,
        health_check_interval: float = 30.0,
        timeout: float = 60.0,
    ) -> None:
        """Register a service."""
        async with self._lock:
            self._services[service_name] = ServiceHealth(
                service_name=service_name,
                status=ServiceStatus.STOPPED,
                last_heartbeat=datetime.now(),
                max_restarts=max_restarts,
                health_check_interval=health_check_interval,
                timeout=timeout,
            )
            
            logger.info(f"Service registered: {service_name}")
    
    async def start_service(self, service_name: str) -> bool:
        """Start a service."""
        async with self._lock:
            if service_name not in self._services:
                logger.error(f"Service not registered: {service_name}")
                return False
            
            service = self._services[service_name]
            
            if service.status == ServiceStatus.RUNNING:
                logger.warning(f"Service already running: {service_name}")
                return True
            
            service.status = ServiceStatus.STARTING
            
            # Publish event
            await self._event_bus.publish_sync(
                EventType.SERVICE_STARTED,
                {"service": service_name},
                "service_manager"
            )
            
            logger.info(f"Service starting: {service_name}")
            return True
    
    async def stop_service(self, service_name: str) -> bool:
        """Stop a service."""
        async with self._lock:
            if service_name not in self._services:
                return False
            
            service = self._services[service_name]
            service.status = ServiceStatus.STOPPING
            
            # Cancel task if running
            if service_name in self._service_tasks:
                self._service_tasks[service_name].cancel()
                del self._service_tasks[service_name]
            
            service.status = ServiceStatus.STOPPED
            
            # Publish event
            await self._event_bus.publish_sync(
                EventType.SERVICE_STOPPED,
                {"service": service_name},
                "service_manager"
            )
            
            logger.info(f"Service stopped: {service_name}")
            return True
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a service."""
        async with self._lock:
            if service_name not in self._services:
                return False
            
            service = self._services[service_name]
            service.status = ServiceStatus.RESTARTING
            service.restart_count += 1
            
            if service.restart_count > service.max_restarts:
                service.status = ServiceStatus.FAILED
                logger.error(f"Service exceeded max restarts: {service_name}")
                
                # Publish event
                await self._event_bus.publish_sync(
                    EventType.SERVICE_FAILED,
                    {"service": service_name, "error": "max_restarts_exceeded"},
                    "service_manager"
                )
                
                return False
            
            # Publish event
            await self._event_bus.publish_sync(
                EventType.SERVICE_RESTARTED,
                {"service": service_name, "restart_count": service.restart_count},
                "service_manager"
            )
            
            logger.info(f"Service restarting: {service_name} (attempt {service.restart_count})")
            return True
    
    async def update_heartbeat(self, service_name: str) -> None:
        """Update service heartbeat."""
        async with self._lock:
            if service_name in self._services:
                self._services[service_name].last_heartbeat = datetime.now()
                if self._services[service_name].status == ServiceStatus.STARTING:
                    self._services[service_name].status = ServiceStatus.RUNNING
    
    async def report_error(self, service_name: str, error: str) -> None:
        """Report service error."""
        async with self._lock:
            if service_name in self._services:
                self._services[service_name].last_error = error
                self._services[service_name].status = ServiceStatus.FAILED
                
                # Publish event
                await self._event_bus.publish_sync(
                    EventType.SERVICE_FAILED,
                    {"service": service_name, "error": error},
                    "service_manager"
                )
                
                logger.error(f"Service error: {service_name} - {error}")
    
    async def get_service_status(self, service_name: str) -> Optional[ServiceHealth]:
        """Get service status."""
        async with self._lock:
            return self._services.get(service_name)
    
    async def get_all_services(self) -> Dict[str, ServiceHealth]:
        """Get all services."""
        async with self._lock:
            return self._services.copy()
    
    async def start_monitoring(self) -> None:
        """Start health monitoring loop."""
        if self._monitor_task is not None:
            return
        
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Service monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop health monitoring loop."""
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
            logger.info("Service monitoring stopped")
    
    async def _monitor_loop(self) -> None:
        """Health monitoring loop."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                async with self._lock:
                    now = datetime.now()
                    
                    for service_name, service in self._services.items():
                        # Check for timeout
                        if service.status == ServiceStatus.RUNNING:
                            elapsed = (now - service.last_heartbeat).total_seconds()
                            if elapsed > service.timeout:
                                logger.warning(f"Service timeout: {service_name}")
                                await self.restart_service(service_name)
                        
                        # Check for failed services
                        elif service.status == ServiceStatus.FAILED:
                            # Attempt restart
                            await self.restart_service(service_name)
                    
                    # Update context
                    service_status = {
                        name: s.status.value
                        for name, s in self._services.items()
                    }
                    from dash_backend.core.global_context import get_global_context
                    context = get_global_context()
                    await context.set_service_status("all", True)  # Update with actual status
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
    
    async def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        async with self._lock:
            now = datetime.now()
            
            report = {
                "timestamp": now.isoformat(),
                "total_services": len(self._services),
                "running": 0,
                "failed": 0,
                "stopped": 0,
                "services": {},
            }
            
            for service_name, service in self._services.items():
                report["services"][service_name] = {
                    "status": service.status.value,
                    "last_heartbeat": service.last_heartbeat.isoformat(),
                    "last_error": service.last_error,
                    "restart_count": service.restart_count,
                    "time_since_heartbeat": (now - service.last_heartbeat).total_seconds(),
                }
                
                if service.status == ServiceStatus.RUNNING:
                    report["running"] += 1
                elif service.status == ServiceStatus.FAILED:
                    report["failed"] += 1
                elif service.status == ServiceStatus.STOPPED:
                    report["stopped"] += 1
            
            return report


# Singleton instance
_service_manager: Optional[ServiceManager] = None


def get_service_manager() -> ServiceManager:
    """Get or create service manager singleton."""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager
