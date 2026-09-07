"""Health Monitor - Component health checks and reporting for DASH AI OS.

Provides:
- Component health checks
- Health status aggregation
- Health history tracking
- Configurable check intervals
- Alert thresholds
- Health webhook notifications
- Dependency health tracking
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """A single health check definition.
    
    Attributes:
        name: Check name
        check_fn: Async function returning (bool, dict)
        interval_seconds: How often to run
        timeout: Maximum check execution time
        critical: If True, failure is critical
        last_status: Last check result
        last_run: When last checked
        last_error: Last error message
        consecutive_failures: Number of consecutive failures
    """
    name: str = ""
    check_fn: Optional[Callable] = None
    interval_seconds: float = 60.0
    timeout: float = 10.0
    critical: bool = True
    last_status: HealthStatus = HealthStatus.UNKNOWN
    last_run: float = 0.0
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    last_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.last_status.value,
            "last_run": self.last_run,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "critical": self.critical,
            "interval": self.interval_seconds,
            "details": self.last_details,
        }


@dataclass
class HealthReport:
    """Overall health report.
    
    Attributes:
        status: Overall health status
        checks: List of check results
        timestamp: When the report was generated
        summary: Human-readable summary
        healthy_count: Number of healthy checks
        degraded_count: Number of degraded checks
        unhealthy_count: Number of unhealthy checks
        unknown_count: Number of unknown checks
    """
    status: HealthStatus = HealthStatus.UNKNOWN
    checks: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = 0.0
    summary: str = ""
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    unknown_count: int = 0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "checks": self.checks,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "healthy": self.healthy_count,
            "degraded": self.degraded_count,
            "unhealthy": self.unhealthy_count,
            "unknown": self.unknown_count,
        }


class HealthMonitor:
    """Monitors health of all system components.
    
    Features:
    - Configurable health checks
    - Automatic periodic checking
    - Health history tracking
    - Alert on status changes
    - Dependencies tracking
    - Report generation
    """
    
    def __init__(self, check_interval: float = 60.0):
        self._check_interval = check_interval
        self._checks: Dict[str, HealthCheck] = {}
        self._history: List[HealthReport] = []
        self._max_history: int = 100
        self._dependencies: Dict[str, List[str]] = {}  # check_name -> [dependencies]
        
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Alert callbacks
        self._alert_callbacks: List[Callable] = []
        
        # Stats
        self._stats = {
            "total_checks_run": 0,
            "total_failures": 0,
            "total_recoveries": 0,
        }
    
    # ── Lifecycle ────────────────────────────────────────────
    
    async def start(self) -> None:
        """Start the health monitor."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("HealthMonitor started with %d checks", len(self._checks))
    
    async def stop(self) -> None:
        """Stop the health monitor."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("HealthMonitor stopped")
    
    # ── Check Registration ───────────────────────────────────
    
    def register_check(self, name: str, check_fn: Callable,
                        interval_seconds: float = 60.0,
                        timeout: float = 10.0,
                        critical: bool = True,
                        dependencies: Optional[List[str]] = None) -> str:
        """Register a health check.
        
        Args:
            name: Check name
            check_fn: Async function returning (is_healthy, details_dict)
            interval_seconds: How often to run
            timeout: Maximum execution time
            critical: If True, failure contributes to overall UNHEALTHY
            dependencies: List of check names that must pass first
            
        Returns:
            Check name
        """
        check = HealthCheck(
            name=name,
            check_fn=check_fn,
            interval_seconds=interval_seconds,
            timeout=timeout,
            critical=critical,
        )
        self._checks[name] = check
        
        if dependencies:
            self._dependencies[name] = dependencies
        
        logger.info("Registered health check '%s' (interval=%.1fs, critical=%s)",
                     name, interval_seconds, critical)
        return name
    
    def unregister_check(self, name: str) -> bool:
        """Unregister a health check.
        
        Args:
            name: Check name to remove
            
        Returns:
            True if removed
        """
        if name in self._checks:
            del self._checks[name]
            self._dependencies.pop(name, None)
            return True
        return False
    
    # ── Alert Callbacks ──────────────────────────────────────
    
    def add_alert_callback(self, callback: Callable[[str, HealthStatus, HealthStatus, str], None]) -> None:
        """Add a callback for health status changes.
        
        Args:
            callback: Function receiving (check_name, old_status, new_status, message)
        """
        self._alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable) -> bool:
        """Remove an alert callback.
        
        Args:
            callback: Callback to remove
            
        Returns:
            True if removed
        """
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)
            return True
        return False
    
    # ── Monitor Loop ─────────────────────────────────────────
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._run_checks()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Health monitor loop error: %s", exc)
                await asyncio.sleep(5.0)
    
    async def _run_checks(self) -> None:
        """Run all registered health checks."""
        for name, check in self._checks.items():
            now = time.time()
            
            # Check if it's time to run
            if now - check.last_run < check.interval_seconds:
                continue
            
            # Check dependencies
            deps = self._dependencies.get(name, [])
            deps_healthy = all(
                self._checks.get(dep, HealthCheck()).last_status == HealthStatus.HEALTHY
                for dep in deps
            )
            if not deps_healthy:
                check.last_status = HealthStatus.UNKNOWN
                check.last_error = f"Dependencies not healthy: {deps}"
                continue
            
            # Run the check
            await self._run_single_check(name, check)
    
    async def _run_single_check(self, name: str, check: HealthCheck) -> None:
        """Run a single health check.
        
        Args:
            name: Check name
            check: HealthCheck object
        """
        if not check.check_fn:
            return
        
        try:
            start = time.time()
            is_healthy, details = await asyncio.wait_for(
                check.check_fn(),
                timeout=check.timeout,
            )
            elapsed = (time.time() - start) * 1000
            
            old_status = check.last_status
            check.last_run = start
            
            if is_healthy:
                if check.last_status != HealthStatus.HEALTHY:
                    self._stats["total_recoveries"] += 1
                    await self._alert(name, old_status, HealthStatus.HEALTHY,
                                      f"Recovered (latency={elapsed:.0f}ms)")
                
                check.last_status = HealthStatus.HEALTHY
                check.last_error = None
                check.consecutive_failures = 0
            else:
                check.consecutive_failures += 1
                check.last_status = HealthStatus.DEGRADED if check.consecutive_failures < 3 else HealthStatus.UNHEALTHY
                check.last_error = details.get("error", "Check failed")
                
                if check.last_status != old_status:
                    await self._alert(name, old_status, check.last_status, details.get("error", ""))
                
                self._stats["total_failures"] += 1
            
            check.last_details = {**details, "latency_ms": elapsed}
            self._stats["total_checks_run"] += 1
            
        except asyncio.TimeoutError:
            check.last_status = HealthStatus.UNHEALTHY
            check.last_error = f"Timeout ({check.timeout}s)"
            check.consecutive_failures += 1
            self._stats["total_failures"] += 1
            await self._alert(name, check.last_status, HealthStatus.UNHEALTHY, check.last_error)
            
        except Exception as exc:
            check.last_status = HealthStatus.UNHEALTHY
            check.last_error = str(exc)
            check.consecutive_failures += 1
            self._stats["total_failures"] += 1
            await self._alert(name, check.last_status, HealthStatus.UNHEALTHY, str(exc))
    
    async def _alert(self, name: str, old_status: HealthStatus,
                      new_status: HealthStatus, message: str) -> None:
        """Send alerts for status changes.
        
        Args:
            name: Check name
            old_status: Previous status
            new_status: New status
            message: Alert message
        """
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(name, old_status, new_status, message)
                else:
                    callback(name, old_status, new_status, message)
            except Exception as exc:
                logger.warning("Health alert callback error: %s", exc)
    
    # ── Report Generation ────────────────────────────────────
    
    def get_report(self) -> HealthReport:
        """Generate a comprehensive health report.
        
        Returns:
            HealthReport with all check results
        """
        report = HealthReport()
        
        for name, check in self._checks.items():
            check_dict = check.to_dict()
            report.checks.append(check_dict)
            
            if check.last_status == HealthStatus.HEALTHY:
                report.healthy_count += 1
            elif check.last_status == HealthStatus.DEGRADED:
                report.degraded_count += 1
            elif check.last_status == HealthStatus.UNHEALTHY:
                report.unhealthy_count += 1
            else:
                report.unknown_count += 1
        
        # Determine overall status
        if report.unhealthy_count > 0:
            report.status = HealthStatus.UNHEALTHY
            report.summary = f"{report.unhealthy_count} component(s) unhealthy"
        elif report.degraded_count > 0:
            report.status = HealthStatus.DEGRADED
            report.summary = f"{report.degraded_count} component(s) degraded"
        elif report.healthy_count == len(self._checks):
            report.status = HealthStatus.HEALTHY
            report.summary = "All systems healthy"
        else:
            report.status = HealthStatus.UNKNOWN
            report.summary = "Some components not yet checked"
        
        # Record history
        self._history.append(report)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        return report
    
    def get_history(self, limit: int = 10) -> List[HealthReport]:
        """Get health report history.
        
        Args:
            limit: Maximum reports
            
        Returns:
            List of HealthReport
        """
        return self._history[-limit:]
    
    def get_check(self, name: str) -> Optional[HealthCheck]:
        """Get a specific health check.
        
        Args:
            name: Check name
            
        Returns:
            HealthCheck or None
        """
        return self._checks.get(name)
    
    def run_check_now(self, name: str) -> Optional[HealthCheck]:
        """Run a specific check immediately.
        
        Args:
            name: Check name
            
        Returns:
            HealthCheck result or None
        """
        check = self._checks.get(name)
        if check:
            asyncio.create_task(self._run_single_check(name, check))
        return check
    
    # ── Stats ────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get health monitor statistics."""
        report = self.get_report()
        return {
            **self._stats,
            "status": report.status.value,
            "healthy_checks": report.healthy_count,
            "degraded_checks": report.degraded_count,
            "unhealthy_checks": report.unhealthy_count,
            "total_checks": len(self._checks),
            "history_size": len(self._history),
        }


# Global singleton
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get or create the global HealthMonitor singleton."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
