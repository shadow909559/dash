"""
DASH WoL Lambda Trigger — wakes the PC via Wake-on-LAN.

Triggered by:
- HTTP API Gateway (Android app sends GET /wol)
- SNS topic (scheduled wake)
- CloudWatch Events (scheduled wake)

The PC's MAC address and broadcast IP are stored in SSM Parameter Store.
"""

import json
import os
import socket
import struct
import boto3

ssm = boto3.client("ssm")
ec2 = boto3.client("ec2", region_name=os.environ.get("AWS_REGION", "ap-south-1"))

# Default values (overridden by SSM)
DEFAULT_MAC = os.environ.get("PC_MAC_ADDRESS", "AA:BB:CC:DD:EE:FF")
DEFAULT_BROADCAST = os.environ.get("BROADCAST_IP", "192.168.1.255")
DEFAULT_PORT = 9


def get_config():
    """Get WoL config from SSM Parameter Store."""
    try:
        params = ssm.get_parameters_by_path(
            Path="/dash/wol/",
            Recursive=True,
        )
        config = {}
        for p in params.get("Parameters", []):
            key = p["Name"].split("/")[-1]
            config[key] = p["Value"]
        return config
    except Exception:
        return {}


def send_wol(mac_address: str, broadcast_ip: str = "192.168.1.255", port: int = 9):
    """Send a Wake-on-LAN magic packet."""
    # Clean MAC address
    mac = mac_address.replace(":", "").replace("-", "").replace(".", "")
    if len(mac) != 12:
        raise ValueError(f"Invalid MAC address: {mac_address}")

    # Build magic packet: 6 bytes of 0xFF + 16 repetitions of MAC
    mac_bytes = bytes.fromhex(mac)
    magic = b"\xff" * 6 + mac_bytes * 16

    # Send via UDP broadcast
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, (broadcast_ip, port))

    return True


def lambda_handler(event, context):
    """Handle Lambda invocation."""
    config = get_config()

    mac = config.get("mac_address", DEFAULT_MAC)
    broadcast = config.get("broadcast_ip", DEFAULT_BROADCAST)
    port = int(config.get("port", DEFAULT_PORT))

    # No EC2 — using Cloudflare Tunnel (free forever)
    # The tunnel starts automatically via auto-start script

    try:
        # Send WoL packet
        send_wol(mac, broadcast, port)

        result = {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Wake-on-LAN packet sent",
                "mac": mac,
                "broadcast": broadcast,
            }),
        }

        # EC2 removed — Cloudflare Tunnel handles remote access

        return result

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "mac": mac,
            }),
        }
