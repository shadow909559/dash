"""System Services for DASH AI OS.

Provides core system-level services:
- Scheduler: Task scheduling with cron-like expressions
- Cache Manager: Multi-tier caching (memory, Redis)
- Resource Manager: CPU, memory, disk, network monitoring
- Health Monitor: Component health checks and reporting
- Metrics: Performance metrics collection and aggregation
- Telemetry: System telemetry data collection
- Diagnostics: System diagnostics and troubleshooting
- System Monitor: Real-time system metrics collection and WebSocket broadcasting
"""

from __future__ import annotations

from .system_monitor import SystemMonitor, get_system_monitor
from .cache_manager import CacheManager, get_cache_manager
from .scheduler import SystemScheduler, get_system_scheduler
from .health_monitor import HealthMonitor, get_health_monitor
from .metrics import MetricsCollector, get_metrics_collector
from .resource_manager import ResourceManager, get_resource_manager

__all__ = [
    "SystemMonitor",
    "get_system_monitor",
    "CacheManager",
    "get_cache_manager",
    "SystemScheduler",
    "get_system_scheduler",
    "HealthMonitor",
    "get_health_monitor",
    "MetricsCollector",
    "get_metrics_collector",
    "ResourceManager",
    "get_resource_manager",
]
