"""Installed applications monitor."""

from __future__ import annotations

import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def get_installed_applications() -> list[dict[str, Any]]:
    """Return list of installed applications with version, publisher, path.

    Windows-only via registry. Returns empty list on other platforms.
    Each entry: name, version, publisher, install_path.
    """
    apps: list[dict[str, Any]] = []

    if platform.system() != "Windows":
        return apps

    # Fallback: read from registry
    try:
        import winreg
        reg_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        for reg_path in reg_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        except Exception:
                            continue
                        version = None
                        publisher = None
                        install_path = None
                        try:
                            version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                        except Exception:
                            pass
                        try:
                            publisher = winreg.QueryValueEx(subkey, "Publisher")[0]
                        except Exception:
                            pass
                        try:
                            install_path = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                        except Exception:
                            pass
                        if name:
                            apps.append({
                                "name": name,
                                "version": version,
                                "publisher": publisher,
                                "install_path": install_path,
                            })
                        winreg.CloseKey(subkey)
                    except Exception:
                        continue
                winreg.CloseKey(key)
            except Exception:
                continue
    except Exception:
        logger.exception("Failed to read registry for installed apps")

    return apps


def get_running_applications() -> list[dict[str, Any]]:
    """Return list of running applications (processes with windows).

    Each entry: name, pid, cpu_percent, memory_mb, window_title.
    """
    running: list[dict[str, Any]] = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = proc.info
                mem_mb = None
                if info.get("memory_info"):
                    mem_mb = round(info["memory_info"].rss / (1024 * 1024), 1)
                running.append({
                    "name": info["name"],
                    "pid": info["pid"],
                    "cpu_percent": info["cpu_percent"] or 0.0,
                    "memory_mb": mem_mb,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return running