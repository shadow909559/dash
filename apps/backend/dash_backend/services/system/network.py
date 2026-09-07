"""Network monitoring: download/upload speed, current IP, hostname, WiFi, latency."""

from __future__ import annotations

import platform
import socket
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_HAS_PSUTIL = False

try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    logger.info("psutil not available – network speed metrics will be unavailable")


# ---------------------------------------------------------------------------
# Network I/O counters (for speed calculation)
# ---------------------------------------------------------------------------

_prev_net_io: dict[str, Any] = {}
_prev_net_time: float = 0.0

def _get_gateway_and_dns() -> dict[str, Any]:
    """Get default gateway and DNS servers."""
    result: dict[str, Any] = {
        "gateway": None,
        "dns_servers": [],
    }
    try:
        if platform.system() == "Windows":
            import subprocess
            output = subprocess.check_output(
                ["ipconfig", "/all"],
                timeout=5, text=True
            )
            for line in output.splitlines():
                line = line.strip()
                if "Default Gateway" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        gw = parts[1].strip()
                        if gw and gw != ":":
                            result["gateway"] = gw
                if "DNS Servers" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        dns = parts[1].strip()
                        if dns:
                            result["dns_servers"].append(dns)
                elif result["dns_servers"] and line.strip() and "." in line:
                    try:
                        socket.inet_aton(line.strip())
                        result["dns_servers"].append(line.strip())
                    except OSError:
                        pass
        else:
            try:
                with open("/etc/resolv.conf") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            parts = line.split()
                            if len(parts) >= 2:
                                result["dns_servers"].append(parts[1])
            except Exception:
                pass
            try:
                import subprocess
                output = subprocess.check_output(
                    ["ip", "route", "show", "default"],
                    timeout=5, text=True
                )
                parts = output.split()
                if len(parts) >= 3:
                    result["gateway"] = parts[2]
            except Exception:
                pass
    except Exception:
        pass
    return result


def _get_wifi_info() -> dict[str, Any]:
    """Get WiFi name and signal strength on Windows."""
    result: dict[str, Any] = {
        "wifi_name": None,
        "signal_strength": None,
        "ethernet_connected": None,
    }
    if platform.system() != "Windows":
        return result
    try:
        import subprocess
        try:
            eth_output_result = subprocess.run(
                ["wmic", "nic", "where", "NetEnabled=TRUE", "get", "Name,NetConnectionStatus", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            eth_output = eth_output_result.stdout
            for line in eth_output.splitlines():
                if "Ethernet" in line or "eth" in line.lower():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        status = parts[-1].strip()
                        if status == "2":
                            result["ethernet_connected"] = True
                            break
                        elif status == "7":
                            result["ethernet_connected"] = False
        except Exception:
            pass

        try:
            wifi_output = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                timeout=5, text=True
            )
            for line in wifi_output.splitlines():
                line = line.strip()
                if "SSID" in line and "BSSID" not in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        result["wifi_name"] = parts[1].strip()
                if "Signal" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        signal = parts[1].strip().replace("%", "")
                        try:
                            result["signal_strength"] = int(signal)
                        except ValueError:
                            pass
        except Exception:
            pass
    except Exception:
        pass
    return result


def _get_latency() -> float | None:
    """Measure network latency by pinging a public DNS server."""
    try:
        if platform.system() == "Windows":
            import subprocess
            output = subprocess.check_output(
                ["ping", "-n", "1", "-w", "3000", "8.8.8.8"],
                timeout=5, text=True
            )
            for line in output.splitlines():
                if "time=" in line or "time<" in line:
                    import re
                    match = re.search(r"time[=<>](\d+(?:\.?\d*))", line)
                    if match:
                        return float(match.group(1))
        else:
            import subprocess
            output = subprocess.check_output(
                ["ping", "-c", "1", "-W", "3", "8.8.8.8"],
                timeout=5, text=True
            )
            for line in output.splitlines():
                if "time=" in line:
                    import re
                    match = re.search(r"time=(\d+(?:\.?\d*))", line)
                    if match:
                        return float(match.group(1))
    except Exception:
        pass
    return None


def _sample_net_io() -> dict[str, Any] | None:
    """Grab current net_io_counters, returning sent/recv bytes and timestamp."""
    global _prev_net_io, _prev_net_time
    if not _HAS_PSUTIL or _psutil is None:
        return None

    try:
        counters = _psutil.net_io_counters()
        now = time.time()
        result = {
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "timestamp": now,
        }
        return result
    except Exception:
        logger.exception("Failed to sample net IO")
        return None


def _calculate_speed(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> tuple[float, float]:
    """Calculate download/upload speed in bytes per second."""
    dt = current["timestamp"] - previous["timestamp"]
    if dt <= 0:
        return 0.0, 0.0
    down_bps = (current["bytes_recv"] - previous["bytes_recv"]) / dt
    up_bps = (current["bytes_sent"] - previous["bytes_sent"]) / dt
    return max(0.0, down_bps), max(0.0, up_bps)


def get_network_info() -> dict[str, Any]:
    """Return network stats: download speed, upload speed, current IP, hostname."""
    global _prev_net_io, _prev_net_time

    result: dict[str, Any] = {
        "download_speed_bps": None,
        "upload_speed_bps": None,
        "download_speed_mbps": None,
        "upload_speed_mbps": None,
        "ip_address": None,
        "hostname": None,
        "interfaces": [],
        "latency_ms": None,
        "gateway": None,
        "dns_servers": [],
        "wifi_name": None,
        "signal_strength": None,
        "ethernet_connected": None,
    }

    # Hostname
    try:
        result["hostname"] = socket.gethostname()
    except Exception:
        pass

    # IP address
    try:
        # Connect to a public DNS to determine outward-facing IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        result["ip_address"] = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            result["ip_address"] = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass

    # Network interfaces
    try:
        if _HAS_PSUTIL and _psutil is not None:
            addrs = _psutil.net_if_addrs()
            stats = _psutil.net_if_stats()
            for iface_name, iface_addrs in addrs.items():
                info: dict[str, Any] = {"name": iface_name}
                s = stats.get(iface_name)
                if s:
                    info["isup"] = s.isup
                    info["speed"] = s.speed
                for addr in iface_addrs:
                    if addr.family == socket.AF_INET:
                        info["ip"] = addr.address
                        info["netmask"] = addr.netmask
                result["interfaces"].append(info)
    except Exception:
        logger.exception("Failed to enumerate network interfaces")

    # Latency
    result["latency_ms"] = _get_latency()

    # WiFi and ethernet info
    wifi_info = _get_wifi_info()
    result["wifi_name"] = wifi_info.get("wifi_name")
    result["signal_strength"] = wifi_info.get("signal_strength")
    result["ethernet_connected"] = wifi_info.get("ethernet_connected")

    # Gateway and DNS
    gw_dns = _get_gateway_and_dns()
    result["gateway"] = gw_dns.get("gateway")
    result["dns_servers"] = gw_dns.get("dns_servers", [])

    # Speed calculation using delta sampling
    current_sample = _sample_net_io()
    if current_sample is not None and _prev_net_io:
        down_bps, up_bps = _calculate_speed(current_sample, _prev_net_io)
        result["download_speed_bps"] = round(down_bps, 1)
        result["upload_speed_bps"] = round(up_bps, 1)
        result["download_speed_mbps"] = round(down_bps / 1_000_000, 2)
        result["upload_speed_mbps"] = round(up_bps / 1_000_000, 2)

    # Store current sample for next call
    if current_sample is not None:
        _prev_net_io = current_sample
        _prev_net_time = current_sample["timestamp"]

    return result