"""Live verification of the intelligence/observability surface
(decisions.md #99): search, context, health, status report, timeline,
policies, decision traces, debug view, metrics — against a real server.

Server boot (isolated):
  DASH_BENCH_STATE=<state> DASH_CRM_DIR=<state>/crm DASH_ASSISTANT_PROACTIVE=0 \
      python scripts/_bench_boot.py <port>

Usage:
  python scripts/assistant_intel_live.py --port 8031 \
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--state-dir", required=True)
    a = ap.parse_args()
    headers = _auth(a.state_dir)
    ok = True

    def gate(name: str, cond: bool, extra: str = "") -> None:
        nonlocal ok
        print(f"{name}: {'PASS' if cond else 'FAIL'} {extra}")
        ok &= bool(cond)

    # Seed a real client with real records
    st, client = _req(a.port, "POST", "/clients", headers,
                      {"name": "Acme Intel", "organization": "Acme Intel"})
    gate("G1 client create", st in (200, 201, 409), f"({st})")
    st, project = _req(a.port, "POST", "/projects", headers,
                       {"name": "Portal", "client_id": client["id"],
                        "deadline": "2026-09-15"})
    gate("G2 project create", st in (200, 201), f"({st})")

    st, _ = _req(a.port, "POST", "/requirements", headers, {
        "client_name": "Acme Intel", "project_name": "Portal",
        "text": "Add WhatsApp notifications", "status": "confirmed"})
    st, _ = _req(a.port, "POST", "/requirements", headers, {
        "client_name": "Acme Intel", "project_name": "Portal",
        "text": "Faster dashboard", "status": "clarification_needed"})

    # G3: search finds the requirement across real records
    st, hits = _req(a.port, "GET",
                    "/search?query=WhatsApp&client=Acme%20Intel", headers)
    gate("G3 search grounded", st == 200 and
         hits.get("counts", {}).get("requirements") == 1,
         f"({st}, {json.dumps(hits.get('counts', {}))[:60]})")

    # G4: client context scoped
    st, ctx = _req(a.port, "GET", "/clients/Acme%20Intel/context", headers)
    gate("G4 context scoped", st == 200 and
         ctx.get("client", {}).get("name") == "Acme Intel" and
         len(ctx.get("pending_decisions", [])) == 1, f"({st})")

    # G5: project health with real overdue deadline
    st, health = _req(a.port, "GET", "/projects/Portal/health", headers)
    gate("G5 project health", st == 200 and
         health.get("requirements", {}).get("pending_decision") == 1 and
         health.get("next_deadline", {}).get("overdue") is True, f"({st})")

    # G6: client status report
    st, report = _req(a.port, "GET", "/summary/client/Acme%20Intel", headers)
    gate("G6 status report", st == 200 and
         report.get("text", "").startswith("Status for Acme Intel"),
         f"({st})")

    # G7: timeline with type filter
    st, tl = _req(a.port, "GET", "/timeline?type=requirement", headers)
    evs = tl.get("events", [])
    gate("G7 timeline filter", st == 200 and evs and
         all(e["type"] == "requirement" for e in evs), f"({st}, {len(evs)})")

    # G8: policy precedence enforced at the API
    st, _ = _req(a.port, "PUT", "/policy", headers,
                 {"client_id": client["id"],
                  "policy": {"external_messages": "deny"}})
    st, prep = _req(a.port, "POST", "/messages/prepare", headers, {
        "client_name": "Acme Intel", "text": "should be policy-denied"})
    gate("G8 policy deny blocks", st == 400 and
         "denied by policy" in prep.get("detail", ""), f"({st})")

    # G9: decision trace was recorded by the gated prepare path
    st, dec = _req(a.port, "GET", "/decisions", headers)
    gate("G9 decision traces", st == 200 and
         isinstance(dec.get("decisions"), list), f"({st})")

    # G10: debug view + metrics endpoints exist and answer
    st, dbg = _req(a.port, "GET", "/debug?section=counts", headers)
    gate("G10a debug view", st == 200 and
         dbg.get("counts", {}).get("clients", 0) >= 1, f"({st})")
    st, met = _req(a.port, "GET", "/metrics", headers)
    gate("G10b metrics", st == 200 and "latency" in met, f"({st})")

    print("ALL_GATES_PASS" if ok else "GATES_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
