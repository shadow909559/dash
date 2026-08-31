"""EC2 Control — Start/stop the cloud backend from the Android app.

When PC is on: Android calls local backend → starts EC2 → cloud relay goes live
When PC is off: Android talks directly to EC2 cloud relay
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from fastapi import APIRouter
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ec2", tags=["ec2-control"])

# EC2 configuration from environment
EC2_INSTANCE_ID = os.getenv("EC2_INSTANCE_ID", "i-0546d2c1b0c7346a5")
EC2_REGION = os.getenv("EC2_REGION", "ap-south-1")
CLOUD_BACKEND_URL = os.getenv("CLOUD_BACKEND_URL", "http://15.206.185.189:8001")


def _aws_cmd(args: list[str]) -> dict[str, Any]:
    """Run an AWS CLI command and return parsed output.
    
    Returns a dict with either:
      - {"error": "..."} on failure
      - {"data": <parsed_json>} on success (wraps lists in dict)
    """
    cmd = ["aws"] + args + ["--region", EC2_REGION, "--output", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "AWS command failed"}
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        # Wrap lists so the return type is always a dict
        if isinstance(data, list):
            return {"data": data}
        return data
    except FileNotFoundError:
        return {"error": "AWS CLI not installed"}
    except subprocess.TimeoutExpired:
        return {"error": "AWS command timed out"}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON from AWS: {e}"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/status")
async def ec2_status() -> dict[str, Any]:
    """Get EC2 instance status."""
    result = _aws_cmd([
        "ec2", "describe-instances",
        "--instance-ids", EC2_INSTANCE_ID,
        "--query", "Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress,InstanceType]",
    ])
    if "error" in result:
        return {"state": "unknown", "error": result["error"]}

    # _aws_cmd wraps lists as {"data": [...]}, unwrap
    data = result.get("data", [])
    if not data:
        return {"state": "not_found", "error": "No data returned"}

    # JMESPath returns [[[id, state, ip, type]]]
    try:
        inst = data[0][0]
        if not inst:
            return {"state": "not_found", "error": "Instance not found"}
        return {
            "instance_id": inst[0],
            "state": inst[1],
            "public_ip": inst[2] or "",
            "instance_type": inst[3],
            "cloud_backend_url": CLOUD_BACKEND_URL,
        }
    except (IndexError, TypeError):
        return {"state": "not_found", "error": "Instance not found"}


@router.post("/start")
async def ec2_start() -> dict[str, Any]:
    """Start the EC2 instance (cloud relay comes online)."""
    status = await ec2_status()
    if status.get("state") == "running":
        return {"ok": True, "message": "Already running", "public_ip": status.get("public_ip", "")}
    if status.get("state") == "pending":
        return {"ok": True, "message": "Already starting"}

    result = _aws_cmd(["ec2", "start-instances", "--instance-ids", EC2_INSTANCE_ID])
    if "error" in result:
        return {"ok": False, "error": result["error"]}

    return {
        "ok": True,
        "message": "EC2 starting... cloud relay will be live in ~60 seconds",
        "instance_id": EC2_INSTANCE_ID,
    }


@router.post("/stop")
async def ec2_stop() -> dict[str, Any]:
    """Stop the EC2 instance (zero cost when stopped)."""
    status = await ec2_status()
    if status.get("state") == "stopped":
        return {"ok": True, "message": "Already stopped"}
    if status.get("state") == "stopping":
        return {"ok": True, "message": "Already stopping"}

    result = _aws_cmd(["ec2", "stop-instances", "--instance-ids", EC2_INSTANCE_ID])
    if "error" in result:
        return {"ok": False, "error": result["error"]}

    return {"ok": True, "message": "EC2 stopping... cloud relay going offline"}


@router.get("/cloud-status")
async def cloud_status() -> dict[str, Any]:
    """Check if the cloud backend on EC2 is reachable."""
    import httpx
    try:
        timeout = httpx.Timeout(connect=2.0, read=2.0, write=2.0, pool=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{CLOUD_BACKEND_URL}/health")
            return {
                "reachable": resp.status_code == 200,
                "url": CLOUD_BACKEND_URL,
                "status_code": resp.status_code,
            }
    except Exception as e:
        return {"reachable": False, "url": CLOUD_BACKEND_URL, "error": str(e)}
