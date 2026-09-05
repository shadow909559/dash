"""Resource Manager - System resource monitoring for DASH AI OS.

Provides:
- CPU usage monitoring
- Memory usage monitoring
- Disk usage monitoring
- Network I/O monitoring
- GPU monitoring (via NVML/LibreHardwareMonitor)
- Process monitoring
- Resource limit checking
- Threshold alerts
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ResourceUsage:
    """Current resource usage snapshot.
    
    Attributes:
        cpu_percent: CPU usage percentage
        memory_percent: Memory usage percentage
        memory_gb: Memory used in GB
        memory_total_gb: Total memory in GB
        disk_percent: Disk usage percentage
        disk_free_gb: Free disk space in GB
        disk_total_gb: Total disk space in GB
        network_bytes_sent: Network bytes sent since last check
        network_bytes_recv: Network bytes received since last check
        gpu_percent: GPU usage percentage (if available)
        gpu_memory_percent: GPU memory usage percentage (if available)
        gpu_temperature: GPU temperature in Celsius (if available)
        cpu_temperature: CPU temperature in Celsius (if available)
        battery_percent: Battery percentage (if available)
        timestamp: When the snapshot was taken
    """
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_gb: float = 0.0
    memory_total_gb: float = 0.0
    disk_percent: float = 0.0
    disk_free_gb: float = 0.0
    disk_total_gb: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    gpu_percent: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    gpu_temperature: Optional[float] = None
    cpu_temperature: Optional[float] = None
    battery_percent: Optional[float] = None
    timestamp: float = 0.0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu": {"percent": self.cpu_percent},
            "memory": {
                "percent": self.memory_percent,
                "used_gb": round(self.memory_gb, 2),
                "total_gb": round(self.memory_total_gb, 2),
            },
            "disk": {
                "percent": self.disk_percent,
                "free_gb": round(self.disk_free_gb, 2),
                "total_gb": round(self.disk_total_gb, 2),
            },
            "network": {
                "bytes_sent": self.network_bytes_sent,
                "bytes_received": self.network_bytes_recv,
            },
            "gpu": {
                "percent": self.gpu_percent,
                "memory_percent": self.gpu_memory_percent,
                "temperature": self.gpu_temperature,
            },
            "cpu_temperature": self.cpu_temperature,
            "battery_percent": self.battery_percent,
            "timestamp": self.timestamp,
        }


@dataclass
class ResourceThreshold:
    """Resource usage threshold for alerts.
    
    Attributes:
        name: Threshold name
        metric: Metric to check
        warning: Warning threshold (percentage)
        critical: Critical threshold (percentage)
        enabled: Whether this threshold is active
    """
    name: str = ""
    metric: str = ""  # cpu, memory, disk, gpu
    warning: float = 80.0
    critical: float = 90.0
    enabled: bool = True


class ResourceManager:
    """Monitors system resource usage and enforces thresholds.
    
    Features:
    - CPU, memory, disk, network, GPU monitoring
    - Configurable thresholds with alerts
    - Periodic resource snapshots
    - Resource usage history
    - Cross-platform support (with psutil)
    """
    
    def __init__(self, check_interval: float = 5.0,
                 history_size: int = 360):  # 360 = 30 min at 5s interval
        self._check_interval = check_interval
        self._history_size = history_size
        self._history: List[ResourceUsage] = []
        
        # Thresholds
        self._thresholds: Dict[str, ResourceThreshold] = {
            "cpu": ResourceThreshold(name="CPU Usage", metric="cpu", warning=80, critical=90),
            "memory": ResourceThreshold(name="Memory Usage", metric="memory", warning=80, critical=90),
            "disk": ResourceThreshold(name="Disk Usage", metric="disk", warning=85, critical=95),
        }
        
        # Alert callbacks
        self._alert_callbacks: List[Callable] = []
        
        # Previous snapshot for delta calculations
        self._prev_snapshot: Optional[ResourceUsage] = None
        
        # Monitor task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Stats
        self._stats = {
            "total_snapshots": 0,
            "alerts_triggered": 0,
        }
    
    # ── Lifecycle ────────────────────────────────────────────
    
    async def start(self) -> None:
        """Start resource monitoring."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("ResourceManager started (interval=%.1fs)", self._check_interval)
    
    async def stop(self) -> None:
        """Stop resource monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("ResourceManager stopped")
    
    # ── Thresholds ───────────────────────────────────────────
    
    def set_threshold(self, name: str, metric: str,
                       warning: float, critical: float) -> None:
        """Set a resource threshold.
        
        Args:
            name: Human-readable name
            metric: Metric name (cpu, memory, disk, gpu)
            warning: Warning threshold percentage
            critical: Critical threshold percentage
        """
        self._thresholds[metric] = ResourceThreshold(
            name=name, metric=metric, warning=warning, critical=critical,
        )
    
    def add_alert_callback(self, callback: Callable[[str, str, float, float], None]) -> None:
        """Add a callback for threshold alerts.
        
        Args:
            callback: Function (metric_name, level, value, threshold)
        """
        self._alert_callbacks.append(callback)
    
    # ── Monitoring Loop ──────────────────────────────────────
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                usage = await self._get_resource_usage()
                self._history.append(usage)
                
                # Trim history
                if len(self._history) > self._history_size:
                    self._history.pop(0)
                
                # Check thresholds
                await self._check_thresholds(usage)
                
                self._stats["total_snapshots"] += 1
                self._prev_snapshot = usage
                
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Resource monitor error: %s", exc)
                await asyncio.sleep(5.0)
    
    async def _get_resource_usage(self) -> ResourceUsage:
        """Get current resource usage snapshot.
        
        Returns:
            ResourceUsage snapshot
        """
        usage = ResourceUsage()
        
        try:
            import psutil
            
            # CPU
            usage.cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory
            mem = psutil.virtual_memory()
            usage.memory_percent = mem.percent
            usage.memory_gb = mem.used / (1024 ** 3)
            usage.memory_total_gb = mem.total / (1024 ** 3)
            
            # Disk
            if os.name == 'nt':
                disk = psutil.disk_usage('C:\\')
            else:
                disk = psutil.disk_usage('/')
            usage.disk_percent = disk.percent
            usage.disk_free_gb = disk.free / (1024 ** 3)
            usage.disk_total_gb = disk.total / (1024 ** 3)
            
            # Network
            net = psutil.net_io_counters()
            if self._prev_snapshot:
                usage.network_bytes_sent = net.bytes_sent - self._prev_snapshot.network_bytes_sent
                usage.network_bytes_recv = net.bytes_recv - self._prev_snapshot.network_bytes_recv
            else:
                usage.network_bytes_sent = net.bytes_sent
                usage.network_bytes_recv = net.bytes_recv
            
            # Battery
            if hasattr(psutil, "sensors_battery"):
                battery = psutil.sensors_battery()
                if battery:
                    usage.battery_percent = battery.percent
            
            # CPU temperature
            try:
                temps = psutil.sensors_temperatures()
                if "coretemp" in temps:
                    usage.cpu_temperature = temps["coretemp"][0].current
                elif "cpu_thermal" in temps:
                    usage.cpu_temperature = temps["cpu_thermal"][0].current
            except Exception:
                pass
            
        except ImportError:
            logger.debug("psutil not available, using basic resource monitoring")
            usage.cpu_percent = 0.0
            usage.memory_percent = 0.0
            usage.disk_percent = 0.0
        
        return usage
    
    async def _check_thresholds(self, usage: ResourceUsage) -> None:
        """Check resource usage against thresholds.
        
        Args:
            usage: Current resource usage
        """
        checks = [
            ("cpu", usage.cpu_percent),
            ("memory", usage.memory_percent),
            ("disk", usage.disk_percent),
        ]
        
        if usage.gpu_percent is not None:
            checks.append(("gpu", usage.gpu_percent))
        
        for metric, value in checks:
            threshold = self._thresholds.get(metric)
            if not threshold or not threshold.enabled:
                continue
            
            if value >= threshold.critical:
                await self._alert(metric, "critical", value, threshold.critical)
                self._stats["alerts_triggered"] += 1
            elif value >= threshold.warning:
                await self._alert(metric, "warning", value, threshold.warning)
                self._stats["alerts_triggered"] += 1
    
    async def _alert(self, metric: str, level: str,
                      value: float, threshold: float) -> None:
        """Send resource alert.
        
        Args:
            metric: Metric name
            level: Alert level (warning/critical)
            value: Current value
            threshold: Threshold value
        """
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(metric, level, value, threshold)
                else:
                    callback(metric, level, value, threshold)
            except Exception as exc:
                logger.warning("Resource alert callback error: %s", exc)
    
    # ── Data Access ──────────────────────────────────────────
    
    def get_current_usage(self) -> Optional[ResourceUsage]:
        """Get the most recent resource usage snapshot.
        
        Returns:
            ResourceUsage or None
        """
        if self._history:
            return self._history[-1]
        return None
    
    def get_history(self, limit: Optional[int] = None) -> List[ResourceUsage]:
        """Get resource usage history.
        
        Args:
            limit: Maximum entries
            
        Returns:
            List of ResourceUsage
        """
        if limit:
            return self._history[-limit:]
        return list(self._history)
    
    def get_average_usage(self, minutes: int = 5) -> Dict[str, float]:
        """Get average resource usage over a time period.
        
        Args:
            minutes: Time period in minutes
            
        Returns:
            Dict with average cpu, memory, disk percentages
        """
        count_needed = int(minutes * 60 / self._check_interval)
        samples = self._history[-count_needed:] if count_needed > 0 else self._history
        
        if not samples:
            return {"cpu": 0, "memory": 0, "disk": 0}
        
        return {
            "cpu": sum(s.cpu_percent for s in samples) / len(samples),
            "memory": sum(s.memory_percent for s in samples) / len(samples),
            "disk": sum(s.disk_percent for s in samples) / len(samples),
        }
    
    def get_gpu_info(self) -> Optional[Dict[str, Any]]:
        """Get GPU information if available.
        
        Returns:
            GPU info dict or None
        """
        try:
            import pynvml
            
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            info = {
                "name": pynvml.nvmlDeviceGetName(handle),
                "temperature": pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU),
                "utilization": pynvml.nvmlDeviceGetUtilizationRates(handle).gpu,
                "memory_total": pynvml.nvmlDeviceGetMemoryInfo(handle).total / (1024 ** 3),
                "memory_used": pynvml.nvmlDeviceGetMemoryInfo(handle).used / (1024 ** 3),
                "memory_free": pynvml.nvmlDeviceGetMemoryInfo(handle).free / (1024 ** 3),
            }
            
            pynvml.nvmlShutdown()
            return info
            
        except ImportError:
            return None
        except Exception as exc:
            logger.debug("GPU info not available: %s", exc)
            return None
    
    # ── Stats ────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get resource manager statistics."""
        current = self.get_current_usage()
        avg = self.get_average_usage()
        
        return {
            **self._stats,
            "current": current.to_dict() if current else None,
            "average_5min": avg,
            "history_size": len(self._history),
            "check_interval": self._check_interval,
            "thresholds": {
                k: {"warning": v.warning, "critical": v.critical, "enabled": v.enabled}
                for k, v in self._thresholds.items()
            },
        }


# Global singleton
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get or create the global ResourceManager singleton."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager
