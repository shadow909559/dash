"""Live restart-persistence verification (spec #93/#78, decisions.md #98).

Gates (two-phase — the server is killed between them):
  BEFORE: register device → prepare an approval-bearing message →
          push lands in the persisted queue; create a client record.
  AFTER (fresh process, same state dir):
          G3 queue file on disk + notification readable via API
          G4 a NEW push after restart works (file reloaded, not corrupted)
          G5 end-of-day summary is honest from records (no fabricated counts)

Server: python scripts/_bench_boot.py <port> <state-dir> with DASH_CRM_DIR
pointed into the same state dir (CRM + push queue persisted).

Usage:
  python scripts/assistant_persistence_live.py --port 8030 --phase before \
      --state-dir "C:/.../state"
  # ... restart the server on the same state dir ...
  python scripts/assistant_persistence_live.py --port 8030 --phase after \
      --state-dir "C:/.../state"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _auth(state_dir: str) -> dict[str, str]:
    os.environ["DASH_IDENTITY_FILE"] = f"{state_dir}/identity.json"
    from dash_backend.security.local_identity import get_identity
    return {"Authorization": f"Bearer {get_identity().device_token}",
            "Content-Type": "application/json"}


def _req(port: int, method: str, path: str, headers: dict,
         body: dict | None = None):
    r = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/v1/assistant{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def _notes_list(payload) -> list:
    return payload if isinstance(payload, list) else payload.get("notifications", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--phase", choices=["before", "after"], required=True)
    a = ap.parse_args()

    crm_dir = f"{a.state_dir}/crm"
    queue_file = f"{crm_dir}/companion_push.json"
    headers = _auth(a.state_dir)
    ok = True

    if a.phase == "before":
        # Device registers (authenticated) so push targeting is real
        st, reg = _req(a.port, "POST", "/companion/register", headers,
                       {"device_id": "persist_phone", "platform": "android"})
        g1 = st == 200
        print(f"G1 register device: {'PASS' if g1 else 'FAIL'} ({st})")
        ok &= g1

        # Approval-bearing message prepare → approval.created → phone push
        st, client = _req(a.port, "POST", "/clients", headers,
                          {"name": "PersistCo", "organization": "PersistCo"})
        gst = st in (200, 201, 409)
        print(f"   client record: {'PASS' if gst else 'FAIL'} ({st})")
        ok &= gst

        st, prep = _req(a.port, "POST", "/messages/prepare", headers, {
            "client_name": "PersistCo",
            "text": "restart persistence proof — deployment window confirmed",
        })
        g2 = st == 200 and bool(prep.get("approval_required"))
        print(f"G2 message prepared with approval: "
              f"{'PASS' if g2 else 'FAIL'} ({st})")
        ok &= g2

        st, notes = _req(a.port, "GET", "/companion/notifications", headers)
        items = _notes_list(notes)
        g2b = st == 200 and any(
            "needs approval" in (n.get("title") or "").lower() for n in items)
        print(f"G2b approval push queued + fetchable: "
              f"{'PASS' if g2b else 'FAIL'} ({st}, {len(items)} item(s))")
        ok &= g2b

        print("PHASE_BEFORE_OK" if ok else "PHASE_BEFORE_FAIL")
        return 0 if ok else 1

    # ── after restart ──────────────────────────────────────────────────
    import pathlib
    q = pathlib.Path(queue_file)
    raw = q.read_text(encoding="utf-8") if q.exists() else ""
    g3_disk = "needs approval" in raw and "approval_request" in raw
    print(f"G3a push queue file on disk with the approval push: "
          f"{'PASS' if g3_disk else 'FAIL'} ({queue_file})")

    st, notes = _req(a.port, "GET", "/companion/notifications", headers)
    items = _notes_list(notes)
    g3_api = st == 200 and any(
        "needs approval" in (n.get("title") or "").lower() for n in items)
    print(f"G3b notification SURVIVED restart via API: "
          f"{'PASS' if g3_api else 'FAIL'} ({st}, {len(items)} item(s))")
    ok &= g3_disk and g3_api

    # G4: a new push after restart works (queue reloaded, not corrupted)
    st, prep2 = _req(a.port, "POST", "/messages/prepare", headers, {
        "client_name": "PersistCo",
        "text": "post-restart approval flow still functions",
    })
    st2, notes2 = _req(a.port, "GET", "/companion/notifications", headers)
    items2 = _notes_list(notes2)
    g4 = st == 200 and st2 == 200 and len(items2) > len(items)
    print(f"G4 push after restart works: {'PASS' if g4 else 'FAIL'} "
          f"({st}/{st2}, {len(items)} -> {len(items2)} item(s))")
    ok &= g4

    # G4b: the registered device also survived the restart — the new
    # push above must show a real delivery target (spec #93 durability)
    g4b = bool(items2) and items2[0].get("targets", 0) >= 1
    print(f"G4b device registration survived restart "
          f"(targets on newest push): {'PASS' if g4b else 'FAIL'} "
          f"({items2[0].get('targets') if items2 else 'n/a'})")
    ok &= g4b

    # G5: EOD summary honest — no comms today → no fabricated counts
    st, eod = _req(a.port, "GET", "/summary/eod", headers)
    g5 = bool(st == 200 and eod.get("communications_today") == 0
          and isinstance(eod.get("text"), str) and eod["text"])
    print(f"G5 EOD summary honest after restart: "
          f"{'PASS' if g5 else 'FAIL'} ({st}) {json.dumps(eod)[:90]}")
    ok &= g5

    print("PHASE_AFTER_OK" if ok else "PHASE_AFTER_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
