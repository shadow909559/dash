"""Live control-plane proof (decisions.md #94 companion).

Drives the REAL API on a running backend:
  confirmed requirement → convert → REAL orchestrator task created
  → traceability link stored → emergency stop (revokes approvals,
  pauses tasks) → approved send blocked by the gate → resume clears it
  → daily briefing from real state.

Usage: python scripts/assistant_control_live.py --port 8029 \
           --crm-dir <same DASH_CRM_DIR as the server>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

GATES: list[tuple[str, bool]] = []


def gate(name: str, ok: bool, detail: str = "") -> None:
    GATES.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _headers(state_dir: str) -> dict[str, str]:
    import os
    os.environ["DASH_IDENTITY_FILE"] = f"{state_dir}/identity.json"
    from dash_backend.security.local_identity import get_identity
    return {"Authorization": f"Bearer {get_identity().device_token}"}


async def main(port: int, crm_dir: str | None, state_dir: str) -> int:
    if not crm_dir:
        print("--crm-dir is required (must match the server's DASH_CRM_DIR)")
        return 2
    crm = Path(crm_dir)
    for f in ("crm.json", "requirements.json", "communications.json",
              "meetings.json", "action_items.json", "approvals.json"):
        p = crm / f
        if p.exists():
            p.unlink()
    print(f"[reset] CRM state cleared in {crm}")

    api = f"http://127.0.0.1:{port}/api/v1/assistant"
    h = _headers(state_dir)
    async with httpx.AsyncClient(timeout=30, headers=h) as c:
        r = await c.post(f"{api}/clients", json={"name": "ControlCo"})
        client_id = r.json()["id"]
        r = await c.post(f"{api}/requirements", json={
            "client_name": "ControlCo", "text": "Add WhatsApp notifications",
            "status": "confirmed", "confidence": 0.9})
        req_id = r.json()["id"]
        gate("confirmed requirement recorded", r.status_code == 200 and req_id)

        # 1. Requirement → REAL orchestrator task (#142)
        r = await c.post(f"{api}/requirements/{req_id}/convert")
        conv = r.json() if r.status_code == 200 else {"detail": r.text[:120]}
        task_id = conv.get("task_id")
        gate("convert created REAL orchestrator task", r.status_code == 200 and task_id,
             str(conv)[:100])

        # 2. Traceability link stored on the requirement (#143)
        r = await c.get(f"{api}/requirements")
        rec = next((x for x in r.json().get("requirements", [])
                    if x["id"] == req_id), {})
        gate("traceability link recorded", task_id in rec.get("task_ids", [])
             and rec.get("status") == "planned", str(rec.get("task_ids")))

        # 3. The task exists in the orchestrator's own state
        if task_id:
            r = await c.get(f"http://127.0.0.1:{port}/api/v1/agent/task/{task_id}")
            gate("task visible in orchestrator state", r.status_code == 200,
                 (r.json().get("goal") or "")[:80] if r.status_code == 200 else r.text[:80])

        # 4. A pending approval to revoke
        r = await c.post(f"{api}/messages/prepare", json={
            "client_name": "ControlCo", "text": "Pre-stop message."})
        approval_id = r.json().get("approval", {}).get("id")

        # 5. Emergency stop (#109)
        r = await c.post(f"{api}/control/stop")
        stop = r.json()
        gate("emergency stop executed", r.status_code == 200 and stop.get("active") is True,
             f"paused={len(stop.get('paused_tasks', []))} revoked={len(stop.get('revoked_approvals', []))}")
        gate("pending approval revoked by stop", approval_id in stop.get("revoked_approvals", []))
        if task_id:
            r2 = await c.get(f"http://127.0.0.1:{port}/api/v1/agent/task/{task_id}")
            status = r2.json().get("status") if r2.status_code == 200 else "?"
            gate("task paused or already terminal", status in ("paused", "completed", "failed", "cancelled"),
                 f"status={status}")

        # 6. Gate blocks an approved send even after the stop
        r = await c.post(f"{api}/messages/prepare", json={
            "client_name": "ControlCo", "text": "Post-stop message."})
        ap2 = r.json()["approval"]["id"]
        r = await c.post(f"{api}/approvals/{ap2}/resolve",
                         json={"decision": "approve", "scope": "once"})
        r = await c.post(f"{api}/messages/send-approved", json={"approval_id": ap2})
        gate("approved send blocked by stop gate", r.status_code == 400
             and "emergency stop" in r.text.lower())

        # 7. Resume clears the gate; paused tasks stay paused
        r = await c.post(f"{api}/control/resume")
        gate("resume clears the gate", r.status_code == 200 and r.json().get("active") is False)
        r = await c.get(f"{api}/control/status")
        gate("control status reports inactive", r.json().get("active") is False)

        # 8. Daily briefing from real state (#77)
        r = await c.get(f"{api}/briefing")
        b = r.json()
        gate("daily briefing from real state", r.status_code == 200
             and b.get("pending_approvals") == 0 and "brief" in b.get("text", "").lower(),
             b.get("text", "")[:90].replace("\n", " | "))

    passed = sum(1 for _, ok in GATES if ok)
    print(f"\n== {passed}/{len(GATES)} gates passed ==")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8029)
    ap.add_argument("--crm-dir", required=True)
    ap.add_argument("--state-dir", required=True)
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.port, a.crm_dir, a.state_dir)))
