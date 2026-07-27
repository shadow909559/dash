"""Desktop System Monitoring Package.

Collects real-time hardware, network, storage, battery, GPU, and
system information for streaming to clients via WebSocket.
"""

from __future__ import annotations

from .system_monitor import SystemMonitor, get_system_monitor

__all__ = ["SystemMonitor", "get_system_monitor"]