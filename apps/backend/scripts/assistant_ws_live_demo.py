"""Live WS-push proof for assistant events (decisions.md #92).

Connects a REAL websocket client to the real /ws endpoint (device-token
auth in the handshake), then drives the REST API exactly like the UI
would: create client + approval request → receive approval.created push
→ resolve it → receive approval.resolved push → run a live meeting turn
with a scope change → receive meeting.alert push.

Usage: python scripts/assistant_ws_live_demo.py --port 8028
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import websockets

BASE = None  # set in main


def _token() -> str:
    from dash_backend.security.local_identity import get_identity

    return get_identity().device_token


async def drive_rest(port: int) -> dict:
    """Create the approval + meeting fixtures through the REST API."""
    api = f"http://127.0.0.1:{port}/api/v1/assistant"
    headers = {"Authorization": f"Bearer {_token()}"}
    async with httpx.AsyncClient(timeout=20, headers=headers) as c:
        r = await c.post(f"{api}/clients", json={"name": "WsProbe"})
        if r.status_code == 409:
            r = await c.get(f"{api}/clients/WsProbe")
        client_id = r.json()["id"]
        r = await c.post(f"{api}/requirements", json={
            "client_name": "WsProbe", "text": "Email notifications for alerts",
            "status": "confirmed", "confidence": 0.9})
        m = (await c.post(f"{api}/meetings", json={"title": "WS live"})).json()
        a = (await c.post(f"{api}/messages/prepare", json={
            "client_name": "WsProbe",
            "text": "WS push verification message."})).json()
        return {
            "approval_id": a["approval"]["id"],
            "meeting_id": m["id"],
            "client_id": client_id,
        }


async def main(port: int) -> int:
    ws_url = f"ws://127.0.0.1:{port}/api/v1/ws?token={_token()}"
    received: list[dict] = []

    async with websockets.connect(ws_url, open_timeout=15) as ws:

        async def reader() -> None:
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    received.append(msg)
                    if msg.get("type") == "session.info":
                        continue
                    print(f"  WS << {msg.get('type')}  "
                          f"{str(msg)[:110]}")
            except Exception:
                pass

        rtask = asyncio.create_task(reader())
        await asyncio.sleep(1.0)  # session.info lands; socket registered

        fixtures = await drive_rest(port)

        # Resolve the approval through the REST API like the Approvals UI
        api = f"http://127.0.0.1:{port}/api/v1/assistant"
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{api}/approvals/{fixtures['approval_id']}/resolve",
                json={"decision": "approve", "scope": "once"},
                headers={"Authorization": f"Bearer {_token()}"},
            )
            assert r.status_code == 200, r.text
        await asyncio.sleep(0.6)

        # Live meeting turn with a scope change → meeting.alert push
        async with httpx.AsyncClient(timeout=20) as c:
            await c.post(
                f"{api}/meetings/{fixtures['meeting_id']}/start",
                json={"mode": "listen_only"},
                headers={"Authorization": f"Bearer {_token()}"},
            )
            await c.post(
                f"{api}/meetings/{fixtures['meeting_id']}/turn",
                json={"speaker": "John (client)",
                      "text": "Actually we don't need email notifications anymore."},
                headers={"Authorization": f"Bearer {_token()}"},
            )
        await asyncio.sleep(1.0)
        rtask.cancel()

    types = [m.get("type") for m in received]
    gates = [
        ("approval.created pushed live", "approval.created" in types),
        ("approval.resolved pushed live", "approval.resolved" in types),
        ("meeting.alert pushed live", "meeting.alert" in types),
    ]
    print()
    ok = True
    for name, passed in gates:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print(f"\n== {sum(1 for _, p in gates if p)}/{len(gates)} WS gates passed ==")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8028)
    sys.exit(asyncio.run(main(ap.parse_args().port)))
