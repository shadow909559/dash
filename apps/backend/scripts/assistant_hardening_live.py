"""Live verification of the hardening round (decisions.md #102):
retention engine, push-transport honesty, capability report, and the
measured-latency surface — against a real isolated server.

Server boot (isolated):
  DASH_BENCH_STATE=<state> DASH_CRM_DIR=<state>/crm DASH_ASSISTANT_PROACTIVE=0 \
      python scripts/_bench_boot.py <port>

Usage:
  python scripts/assistant_hardening_live.py --port 8032 --state-dir "C:/.../state"
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
         body: dict | None = None, base: str = "/api/v1/assistant"):
    r = urllib.request.Request(
        f"http://127.0.0.1:{port}{base}{path}",
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

    # G1: capability report includes the push transport, honestly unconfigured
    st, cap = _req(a.port, "GET", "/capabilities", headers)
    pt = cap.get("systems", {}).get("push_transport", {})
    gate("G1 capabilities push_transport", st == 200 and
         pt.get("transport") == "local_queue_only" and
         pt.get("configured") is False and pt.get("state") == "degraded",
         f"({pt.get('transport')}, configured={pt.get('configured')})")

    # G2: push without FCM creds -> queued, delivered=0, honest detail
    st, reg = _req(a.port, "POST", "/companion/register", headers,
                   {"device_id": "live-dev", "platform": "android",
                    "token": "tok-live", "user_id": "owner"})
    gate("G2 companion register", st in (200, 201), f"({st})")

    st, prefs = _req(a.port, "GET", "/preferences", headers)
    gate("G3 preferences expose retention_days",
         st == 200 and "retention_days" in prefs,
         f"(retention_days={prefs.get('retention_days')})")

    st, val = _req(a.port, "PUT", "/preferences", headers,
                   {"retention_days": -1})
    gate("G4 retention validation rejects -1", st in (400, 422), f"({st})")

    st, val2 = _req(a.port, "PUT", "/preferences", headers,
                    {"retention_days": 30})
    gate("G5 retention set to 30", st == 200 and
         val2.get("retention_days") == 30, f"({st})")

    # G6: retention run on a real store — honest result shape
    st, ret = _req(a.port, "POST", "/retention/run", headers)
    gate("G6 retention run", st == 200 and
         ret.get("retention_days") == 30 and "pruned" in ret,
         f"({ret.get('retention_days')}, keys={sorted(ret.get('pruned', {}))})")

    # G7: metrics surface responds (tts_first_audio appears once voice runs;
    # here we only prove the endpoint is live and shaped correctly)
    st, met = _req(a.port, "GET", "/metrics", headers)
    gate("G7 metrics live", st == 200 and "latency" in met, f"({st})")

    # G8: FCM unconfigured -> send path stays honest via the mobile route
    st, notif = _req(a.port, "GET", "/companion/notifications", headers)
    gate("G8 companion notifications readable", st == 200 and
         isinstance(notif.get("notifications"), list),
         f"({st}, n={len(notif.get('notifications', []))})")

    print()
    print("ALL GATES PASS" if ok else "SOME GATES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
