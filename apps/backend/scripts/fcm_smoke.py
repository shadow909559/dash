"""FCM transport smoke test (spec #96, decisions.md #103).

Verifies the real FCM HTTP v1 transport end to end when credentials are
configured, and reports honestly when they are not (exit 0 with a clear
SKIP — the queue path still works without credentials).

Checks:
  G1  credentials parse + an OAuth2 token can be minted (real exchange)
  G2  a device can be registered and listed
  G3  a real send against the device token — recorded per-device outcome
      (UNREGISTERED proves cleanup works; a 200 proves real delivery)
  G4  queue write + companion fetch path intact after the send

Usage:
  python scripts/fcm_smoke.py --state-dir "C:/.../state" [--port 8033]
  (boots its own isolated server unless --port is given with a running one)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
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
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--state-dir", required=True)
    args = ap.parse_args()

    if not os.getenv("DASH_FCM_SERVICE_ACCOUNT"):
        print("SKIP: DASH_FCM_SERVICE_ACCOUNT not set — the FCM transport "
              "is not configured on this machine.")
        print("The local queue path is exercised by the hermetic suite and "
              "assistant_hardening_live.py; set the env var with a Google "
              "service-account JSON to run real-delivery gates.")
        return 0

    proc = None
    port = args.port
    try:
        if not port:
            port = 8033
            env = dict(os.environ,
                       DASH_BENCH_STATE=args.state_dir,
                       DASH_CRM_DIR=f"{args.state_dir}/crm",
                       DASH_ASSISTANT_PROACTIVE="0")
            proc = subprocess.Popen(
                [sys.executable, os.path.join(os.path.dirname(__file__), "_bench_boot.py"),
                 str(port)], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.time() + 30
            while time.time() < deadline:
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                    break
                except Exception:
                    time.sleep(1)

        headers = _auth(args.state_dir)
        ok = True

        def gate(name: str, cond: bool, extra: str = "") -> None:
            nonlocal ok
            print(f"{name}: {'PASS' if cond else 'FAIL'} {extra}")
            ok &= bool(cond)

        # G1: token minting against Google's real OAuth endpoint
        from dash_backend.services.mobile_companion import PushNotificationService
        svc = PushNotificationService()
        if not svc._fcm_creds:
            print("SKIP: credentials present but unreadable — check the "
                  "service-account JSON (project_id/client_email/private_key).")
            return 0
        token = svc._fcm_access_token()
        gate("G1 oauth token minted", bool(token),
             f"({svc._fcm_last_error or 'ok'})")

        # G2: register a device
        st, reg = _req(port, "POST", "/companion/register", headers,
                       {"device_id": "fcm-smoke-dev", "platform": "android",
                        "token": os.getenv("DASH_FCM_SMOKE_DEVICE_TOKEN", "smoke-token"),
                        "user_id": "owner"})
        gate("G2 device registered", st in (200, 201), f"({st})")

        # G3: real send — whatever the provider says is the honest result
        st, pushed = _req(port, "POST", "/companion/push", headers,
                          {"title": "DASH FCM smoke", "body": "transport check"})
        if st == 404:
            # no direct push route in this build: drive the service directly
            out = svc.send_push("DASH FCM smoke", "transport check",
                                target_user="owner")
        else:
            out = pushed
        delivery = out.get("notification", {}).get("delivery", {})
        devices = delivery.get("devices", [])
        gate("G3 per-device outcomes recorded", len(devices) == 1,
             f"({devices})")
        if devices and devices[0].get("detail") == "UNREGISTERED":
            print("    note: token is not a live device token — transport "
                  "reachable, cleanup path proven (UNREGISTERED deactivated).")
            active = [d for d in svc.get_devices() if d.get("active")]
            gate("G3b UNREGISTERED cleanup", active == [], f"({active})")
        elif devices:
            gate("G3c real delivery", devices[0].get("ok") is True,
                 f"({devices[0].get('detail')})")

        # G4: queue + fetch path intact
        st, notif = _req(port, "GET", "/companion/notifications", headers)
        gate("G4 companion fetch path", st == 200 and
             isinstance(notif.get("notifications"), list), f"({st})")

        print()
        print("ALL GATES PASS" if ok else "SOME GATES FAILED")
        return 0 if ok else 1
    finally:
        if proc is not None:
            proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
