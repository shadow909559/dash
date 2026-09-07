"""Wake-on-LAN service — send magic packets to power on devices on the LAN.

Usage:
    POST /api/v1/remote/wol  { "mac_address": "AA:BB:CC:DD:EE:FF" }
    POST /api/v1/remote/wol  { "broadcast": "192.168.1.255" }
"""

from __future__ import annotations

import asyncio
import socket
import struct
from typing import Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Default broadcast addresses to try
DEFAULT_BROADCASTS = ["255.255.255.255", "192.168.1.255", "10.0.0.255"]
WOL_PORT = 9


def _parse_mac(mac: str) -> bytes:
    """Parse a MAC address string into 6 raw bytes."""
    mac = mac.replace("-", ":").replace(".", ":").strip()
    parts = mac.split(":")
    if len(parts) != 6:
        raise ValueError(f"Invalid MAC address: {mac}")
    return bytes(int(p, 16) for p in parts)


def _build_magic_packet(mac: bytes) -> bytes:
    """Build a Wake-on-LAN magic packet: 6x 0xFF + 16x MAC."""
    return b"\xff" * 6 + mac * 16


async def send_wol(
    mac_address: str,
    broadcast: Optional[str] = None,
    port: int = WOL_PORT,
    count: int = 3,
) -> dict:
    """Send a Wake-on-LAN magic packet.

    Args:
        mac_address: Target MAC (e.g. "AA:BB:CC:DD:EE:FF").
        broadcast:   Broadcast IP (default: try all common subnets).
        port:        UDP port (default 9).
        count:       How many packets to send for reliability.

    Returns:
        Dict with summary and details.
    """
    mac = _parse_mac(mac_address)
    packet = _build_magic_packet(mac)

    targets = [broadcast] if broadcast else DEFAULT_BROADCASTS
    sent = 0
    errors = []

    for target in targets:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(3.0)
            for _ in range(count):
                sock.sendto(packet, (target, port))
                sent += 1
            sock.close()
            logger.info("WoL packet sent to %s via %s:%d", mac_address, target, port)
        except Exception as exc:
            errors.append(f"{target}: {exc}")
            logger.warning("WoL send failed via %s: %s", target, exc)

    return {
        "summary": f"Sent {sent} magic packets for {mac_address}",
        "mac_address": mac_address,
        "packets_sent": sent,
        "targets_tried": targets,
        "errors": errors,
    }


async def discover_mac_by_ip(ip_address: str) -> Optional[str]:
    """Try to discover a device's MAC via ARP table lookup.

    Returns MAC string or None if not found.
    """
    try:
        import subprocess
        import re

        if subprocess.run(["ping", "-n", "1", "-w", "1000", ip_address],
                          capture_output=True, timeout=3).returncode != 0:
            return None

        result = subprocess.run(
            ["arp", "-a", ip_address],
            capture_output=True, text=True, timeout=5,
        )
        match = re.search(r"([\da-fA-F]{2}[:-]){5}[\da-fA-F]{2}", result.stdout)
        if match:
            return match.group(0)
    except Exception as exc:
        logger.debug("ARP lookup failed for %s: %s", ip_address, exc)
    return None
