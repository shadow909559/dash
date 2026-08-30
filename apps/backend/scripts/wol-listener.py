"""
DASH Wake-on-LAN Listener
Listens for WoL packets and logs them.
The cloud backend sends WoL packets to wake this PC.

Run as: pythonw wol-listener.py (background, no console window)
Or: python wol-listener.py (for debugging)
"""

import socket
import struct
import subprocess
import logging
import os
from datetime import datetime

# Setup logging
LOG_DIR = os.path.join(os.path.expanduser("~"), ".dash", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "wol-listener.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("wol-listener")

# WoL uses UDP port 7 or 9
WOL_PORT = 9
BUFFER_SIZE = 1024


def get_mac_address() -> str:
    """Get the MAC address of this machine."""
    import uuid
    mac = uuid.getnode()
    return ":".join(f"{(mac >> (8 * i)) & 0xFF:02x}" for i in reversed(range(6)))


def send_wol_to_cloud(mac_address: str):
    """
    Send a WoL magic packet to wake this machine.
    This is called when the cloud backend wants to wake the PC.
    The magic packet is broadcast on the local network.
    """
    mac_bytes = bytes.fromhex(mac_address.replace(":", "").replace("-", ""))
    magic_packet = b"\xff" * 6 + mac_bytes * 16

    # Broadcast on local network
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(magic_packet, ("<broadcast>", WOL_PORT))
    sock.close()
    log.info(f"WoL magic packet sent for {mac_address}")


def handle_wol_packet(data: bytes, addr: tuple):
    """Handle an incoming WoL packet."""
    if len(data) >= 6 and data[:6] == b"\xff" * 6:
        log.info(f"WoL packet received from {addr[0]}:{addr[1]}")
        # The PC is already on if we're receiving this, but log it
        return True
    return False


def main():
    mac = get_mac_address()
    log.info(f"DASH WoL Listener started. MAC: {mac}")
    log.info(f"Listening on UDP port {WOL_PORT}")

    print(f"DASH WoL Listener")
    print(f"MAC Address: {mac}")
    print(f"Listening on UDP port {WOL_PORT}")
    print(f"Press Ctrl+C to stop")
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", WOL_PORT))
    sock.settimeout(1.0)  # 1 second timeout for clean shutdown

    try:
        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                if handle_wol_packet(data, addr):
                    log.info(f"WoL唤醒信号来自 {addr[0]}")
            except socket.timeout:
                continue
    except KeyboardInterrupt:
        log.info("WoL Listener stopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
