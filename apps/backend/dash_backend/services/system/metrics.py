"""Metrics - Performance metrics collection and aggregation for DASH AI OS.

Provides:
- Counter metrics (increment/decrement)
- Gauge metrics (set current value)
- Histogram metrics (distribution)
- Timer metrics (duration measurement)
- Metric namespacing
- Metric tagging/labeling
- Periodic aggregation and reporting
- Prometheus-compatible output
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    SUMMARY = "summary"


@dataclass
class MetricPoint:
    """A single metric data point.
    
    Attributes:
        name: Metric name
        value: Metric value
        tags: Labels/tags
        timestamp: When recorded
        type: Metric type
    """
    name: str = ""
    value: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0
    type: MetricType = MetricType.GAUGE
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "type": self.type.value,
        }


class MetricsCollector:
    """Collects and aggregates performance metrics.
    
    Features:
    - Counter, Gauge, Histogram, Timer metrics
    - Metric tagging/labeling
    - Automatic aggregation
    - Prometheus-compatible output
    - Periodic reporting
    - Metric namespacing
    """
    
    def __init__(self, aggregation_interval: float = 60.0,
                 max_points_per_metric: int = 10000):
        self._aggregation_interval = aggregation_interval
        self._max_points_per_metric = max_points_per_metric
        
        # Metric storage
        self._counters: Dict[str, float] = {}
        self._counter_tags: Dict[str, Dict[str, str]] = {}
        self._gauges: Dict[str, float] = {}
        self._gauge_tags: Dict[str, Dict[str, str]] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._histogram_tags: Dict[str, Dict[str, str]] = {}
        self._timers: Dict[str, List[float]] = {}
        self._timer_tags: Dict[str, Dict[str, str]] = {}
        
        # Metric metadata
        self._metric_descriptions: Dict[str, str] = {}
        self._metric_units: Dict[str, str] = {}
        
        # Data points history
        self._points: Dict[str, List[MetricPoint]] = defaultdict(list)
        
        # Background tasks
        self._agg_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Report callbacks
        self._report_callbacks: List[Callable] = []
        
        # Stats
        self._stats = {
            "total_points_collected": 0,
            "total_aggregations": 0,
        }
    
    # ── Lifecycle ────────────────────────────────────────────
    
    async def start(self) -> None:
        """Start metrics collection."""
        self._running = True
        self._agg_task = asyncio.create_task(self._aggregation_loop())
        logger.info("MetricsCollector started")
    
    async def stop(self) -> None:
        """Stop metrics collection."""
        self._running = False
        if self._agg_task:
            self._agg_task.cancel()
            try:
                await self._agg_task
            except asyncio.CancelledError:
                pass
        logger.info("MetricsCollector stopped")
    
    # ── Counter Metrics ──────────────────────────────────────
    
    def increment(self, name: str, value: float = 1.0,
                   tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric.
        
        Args:
            name: Metric name
            value: Amount to increment
            tags: Optional tags
        """
        key = self._metric_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value
        if tags:
            self._counter_tags[key] = tags
        
        self._record_point(name, value, tags, MetricType.COUNTER)
    
    def decrement(self, name: str, value: float = 1.0,
                   tags: Optional[Dict[str, str]] = None) -> None:
        """Decrement a counter metric.
        
        Args:
            name: Metric name
            value: Amount to decrement
            tags: Optional tags
        """
        key = self._metric_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) - value
        if tags:
            self._counter_tags[key] = tags
        
        self._record_point(name, -value, tags, MetricType.COUNTER)
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """Get counter value.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Counter value
        """
        key = self._metric_key(name, tags)
        return self._counters.get(key, 0.0)
    
    # ── Gauge Metrics ────────────────────────────────────────
    
    def gauge(self, name: str, value: float,
               tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric.
        
        Args:
            name: Metric name
            value: Current value
            tags: Optional tags
        """
        key = self._metric_key(name, tags)
        self._gauges[key] = value
        if tags:
            self._gauge_tags[key] = tags
        
        self._record_point(name, value, tags, MetricType.GAUGE)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Gauge value or None
        """
        key = self._metric_key(name, tags)
        return self._gauges.get(key)
    
    # ── Histogram Metrics ────────────────────────────────────
    
    def histogram(self, name: str, value: float,
                   tags: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation.
        
        Args:
            name: Metric name
            value: Observed value
            tags: Optional tags
        """
        key = self._metric_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        if tags:
            self._histogram_tags[key] = tags
        
        self._record_point(name, value, tags, MetricType.HISTOGRAM)
    
    def get_histogram(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Dict with count, min, max, mean, p50, p90, p99
        """
        key = self._metric_key(name, tags)
        values = self._histograms.get(key, [])
        
        if not values:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "p50": 0, "p90": 0, "p99": 0}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "count": n,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(sorted_values) / n,
            "p50": sorted_values[int(n * 0.50)],
            "p90": sorted_values[int(n * 0.90)],
            "p99": sorted_values[int(n * 0.99)],
        }
    
    # ── Timer Metrics ────────────────────────────────────────
    
    @dataclass
    class Timer:
        """A timer context manager for measuring durations."""
        name: str
        tags: Dict[str, str]
        collector: "MetricsCollector"
        start: float = 0.0
        
        def __enter__(self):
            self.start = time.perf_counter()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = (time.perf_counter() - self.start) * 1000  # ms
            self.collector.timing(self.name, duration, self.tags)
    
    def timer(self, name: str, tags: Optional[Dict[str, str]] = None) -> "Timer":
        """Create a timer context manager.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Timer context manager
        """
        return self.Timer(name, tags or {}, self)
    
    def timing(self, name: str, duration_ms: float,
                tags: Optional[Dict[str, str]] = None) -> None:
        """Record a timing metric.
        
        Args:
            name: Metric name
            duration_ms: Duration in milliseconds
            tags: Optional tags
        """
        key = self._metric_key(name, tags)
        if key not in self._timers:
            self._timers[key] = []
        self._timers[key].append(duration_ms)
        if tags:
            self._timer_tags[key] = tags
        
        self._record_point(name, duration_ms, tags, MetricType.TIMER)
    
    def get_timing(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get timing statistics.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Dict with count, min, max, mean, p50, p90, p99
        """
        key = self._metric_key(name, tags)
        values = self._timers.get(key, [])
        
        if not values:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "p50": 0, "p90": 0, "p99": 0}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "count": n,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(sorted_values) / n,
            "median": sorted_values[n // 2],
            "p50": sorted_values[int(n * 0.50)],
            "p90": sorted_values[int(n * 0.90)],
            "p99": sorted_values[int(n * 0.99)],
        }
    
    # ── Metric Descriptions ──────────────────────────────────
    
    def describe_metric(self, name: str, description: str,
                         unit: str = "") -> None:
        """Add a description for a metric.
        
        Args:
            name: Metric name
            description: Human-readable description
            unit: Unit of measurement
        """
        self._metric_descriptions[name] = description
        self._metric_units[name] = unit
    
    # ── Internal ─────────────────────────────────────────────
    
    @staticmethod
    def _metric_key(name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Generate a unique key for a metric+tgs combination.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Unique key string
        """
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def _record_point(self, name: str, value: float,
                       tags: Optional[Dict[str, str]], metric_type: MetricType) -> None:
        """Record a data point.
        
        Args:
            name: Metric name
            value: Value
            tags: Tags
            metric_type: Type of metric
        """
        point = MetricPoint(
            name=name,
            value=value,
            tags=tags or {},
            type=metric_type,
        )
        
        self._points[name].append(point)
        self._stats["total_points_collected"] += 1
        
        # Trim if needed
        if len(self._points[name]) > self._max_points_per_metric:
            self._points[name] = self._points[name][-self._max_points_per_metric:]
    
    # ── Aggregation ──────────────────────────────────────────
    
    async def _aggregation_loop(self) -> None:
        """Periodic aggregation loop."""
        while self._running:
            try:
                await asyncio.sleep(self._aggregation_interval)
                self._aggregate()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Metrics aggregation error: %s", exc)
    
    def _aggregate(self) -> None:
        """Aggregate all metrics and generate reports."""
        report = self.get_report()
        
        # Notify callbacks
        for callback in self._report_callbacks:
            try:
                callback(report)
            except Exception as exc:
                logger.warning("Metrics report callback error: %s", exc)
        
        self._stats["total_aggregations"] += 1
        logger.debug("Metrics aggregated: %d data points",
                     self._stats["total_points_collected"])
    
    def add_report_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add a callback for metric reports.
        
        Args:
            callback: Function receiving report dict
        """
        self._report_callbacks.append(callback)
    
    # ── Report ───────────────────────────────────────────────
    
    def get_report(self) -> Dict[str, Any]:
        """Generate a comprehensive metrics report.
        
        Returns:
            Dict with all metrics and their values
        """
        report = {
            "counters": {},
            "gauges": {},
            "histograms": {},
            "timers": {},
            "descriptions": dict(self._metric_descriptions),
            "units": dict(self._metric_units),
            "timestamp": time.time(),
        }
        
        # Counters
        for key, value in self._counters.items():
            report["counters"][key] = value
        
        # Gauges
        for key, value in self._gauges.items():
            report["gauges"][key] = value
        
        # Histograms
        for key, _ in self._histograms.items():
            # Parse name from key
            name = key.split("[")[0] if "[" in key else key
            tags = self._histogram_tags.get(key, {})
            report["histograms"][key] = self.get_histogram(name, tags)
        
        # Timers
        for key, _ in self._timers.items():
            name = key.split("[")[0] if "[" in key else key
            tags = self._timer_tags.get(key, {})
            report["timers"][key] = self.get_timing(name, tags)
        
        return report
    
    def to_prometheus(self) -> str:
        """Format metrics as Prometheus text format.
        
        Returns:
            Prometheus-formatted string
        """
        lines = []
        
        for key, value in self._counters.items():
            name = key.split("[")[0] if "[" in key else key
            desc = self._metric_descriptions.get(name, "")
            if desc:
                lines.append(f"# HELP {name} {desc}")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        
        for key, value in self._gauges.items():
            name = key.split("[")[0] if "[" in key else key
            desc = self._metric_descriptions.get(name, "")
            if desc:
                lines.append(f"# HELP {name} {desc}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        
        return "\n".join(lines)
    
    # ── Stats ────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get metrics collector statistics."""
        return {
            **self._stats,
            "counters_count": len(self._counters),
            "gauges_count": len(self._gauges),
            "histograms_count": len(self._histograms),
            "timers_count": len(self._timers),
            "total_unique_metrics": len(set(
                list(self._counters.keys()) +
                list(self._gauges.keys()) +
                list(self._histograms.keys()) +
                list(self._timers.keys())
            )),
        }


# Global singleton
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global MetricsCollector singleton."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
