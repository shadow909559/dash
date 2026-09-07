"""Phone control package for DASH AI OS.

Provides backend-only Android device control via ADB (no UI yet).
Integrates with the existing DASH architecture.
"""

from dash_backend.phone.adb_service import AdbService, get_adb_service

__all__ = ["AdbService", "get_adb_service"]
