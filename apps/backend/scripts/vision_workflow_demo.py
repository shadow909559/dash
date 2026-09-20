"""Vision → workflow demo (decisions.md #72): the watcher fires a real workflow.

Boots an ISOLATED DASH backend (temp DB/state, Guardian off, standing
watcher loop off for determinism) with the REAL vision models copied to a
temp dir, sets DASH_VISION_STATIC_FRAME so the watcher's photon source is
a real photo (the photo-on-a-desk pattern) — detection, recognition, and
reporting stay the real pipeline — then, through the real HTTP API:

  G1  boot + /vision/status reports every model available
  G2  enroll Zidane via /enroll, listed by /persons
  G3  create "person seen demo" workflow via /workflows/create
      (trigger vision.person_seen → notification.send → audit.log)
      and attach the event trigger via PUT /event-trigger
  G4  negative control BEFORE firing: the workflow has zero executions
  G5  fire /watch/scan-now (real run_cycle: capture → decode → YuNet →
      SFace → emit vision.person_seen on the bus)
  G6  /workflows/executions shows exactly one source="event" run whose
      action_results contain BOTH a real toast (mechanism windows-toast)
      and a real audit-log write
  G7  cooldown honesty: an immediate second scan-now emits no duplicate
      event and creates no second execution

Exit 0 iff all gates pass. Writes apps/tmp/vision_workflow_demo_report.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dash_backend.vision import recognition as rec  # noqa: E402  (resolver only)

DEMO_PORT = 8018
BASE = f"http://127.0.0.1:{DEMO_PORT}"


def _resolve_photo(name: str) -> Path:
    p = REPO_ROOT / "tmp" / "vision_photos" / name
    if p.exists():
        return p
    try:
        import ultralytics

        alt = Path(ultralytics.__file__).parent / "assets" / name
        if alt.exists():
            return alt
    except ImportError:
        pass
    raise SystemExit(f"photo not found: {p}")


def _http(method: str, path: str, token: str, body: bytes | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(
        BASE + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def stop_port(port: int) -> None:
    out = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True
    ).stdout
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line.upper():
            pid = line.split()[-1]
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
            time.sleep(0.5)


def prepare_models_dir(tmp: Path) -> Path:
    src = rec.vision_models_dir()
    for fname in (
        rec.ModelFiles.DETECTOR,
        rec.ModelFiles.FACE_DET,
        rec.ModelFiles.FACE_EMB,
    ):
        f = src / fname
        if not f.exists():
            raise SystemExit(f"model missing: {f} (run scripts/fetch_vision_models.py)")
        shutil.copy2(f, tmp / fname)
    return tmp


def write_boot_script(state_dir: Path, models_dir: Path, token: str, frame: Path) -> Path:
    backend = BACKEND_DIR.as_posix()
    boot = state_dir / "_demo_boot.py"
    boot.write_text(
        f'''"""Generated vision-workflow demo boot: isolated DASH backend on :{DEMO_PORT}."""
import os, sys

STATE = r"{(state_dir / "state").as_posix()}"
os.environ["DASH_DATABASE_URL"] = "sqlite+aiosqlite:///" + STATE + "/dash.db"
os.environ["DASH_WORKFLOW_STATE"] = STATE + "/workflow_state.json"
os.environ["DASH_GUARDIAN_ENABLED"] = "0"
# The standing watcher loop stays off so the demo fires deterministically
# on scan-now; scan_now runs the same run_cycle the loop calls.
os.environ["DASH_VISION_WATCHER_ENABLED"] = "0"
# The demo seam: the watcher's photon source is a real photo — detection,
# recognition, and reporting remain the real pipeline.
os.environ["DASH_VISION_STATIC_FRAME"] = r"{frame.as_posix()}"
os.environ["DASH_AUDIT_LOG_DIR"] = STATE + "/audit_logs"
os.environ["DASH_DEVICE_TOKEN"] = "{token}"
os.environ["DASH_VISION_MODELS"] = r"{models_dir.as_posix()}"
os.environ["DASH_CORS_ORIGINS_RAW"] = "http://localhost:5188,http://127.0.0.1:5188"
sys.path.insert(0, r"{backend}")
os.chdir(r"{backend}")

import uvicorn
from dash_backend.main import create_app
uvicorn.run(create_app(), host="127.0.0.1", port={DEMO_PORT}, log_level="warning")
''',
        encoding="utf-8",
    )
    return boot


def main() -> int:
    global DEMO_PORT, BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEMO_PORT)
    ap.add_argument("--keep", action="store_true", help="keep temp dir for inspection")
    args = ap.parse_args()
    DEMO_PORT = args.port
    BASE = f"http://127.0.0.1:{DEMO_PORT}"

    token = "demo-" + os.urandom(16).hex()
    tmp = Path(tempfile.mkdtemp(prefix="vision_wf_demo_"))
    (tmp / "state" / "state").mkdir(parents=True, exist_ok=True)
    gates: list[tuple[str, bool, str]] = []
    report: dict = {"gates": gates, "port": DEMO_PORT}

    def gate(name: str, ok: bool, detail: str = "") -> None:
        gates.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    zidane = _resolve_photo("zidane.jpg")
    models_dir = prepare_models_dir(tmp)
    boot = write_boot_script(tmp / "state", models_dir, token, zidane)

    proc = subprocess.Popen(
        [sys.executable, "-u", str(boot)],
        stdout=open(tmp / "backend.log", "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        cwd=str(BACKEND_DIR),
    )
    try:
        # ── wait for readiness ───────────────────────────────────────
        code = 0
        for _ in range(60):
            try:
                code, _ = _http("GET", "/api/v1/vision/status", token)
                if code == 200:
                    break
            except Exception:
                pass
            time.sleep(1.0)
        if code != 200:
            gate("G1 boot+status", False, f"last status {code}; see {tmp / 'backend.log'}")
            return _finish(gates, tmp, proc, args.keep)

        _, body = _http("GET", "/api/v1/vision/status", token)
        status = json.loads(body)
        # model_status() reports availability as a list of descriptor
        # strings ("...: available"); face_recognition.object_detection
        # carry the authoritative booleans.
        models_ok = (
            status.get("face_recognition", {}).get("available") is True
            and status.get("object_detection", {}).get("available") is True
        )
        gate("G1 boot+status", bool(models_ok),
             f"faces={status.get('face_recognition', {}).get('available')} "
             f"objects={status.get('object_detection', {}).get('available')}")

        # ── G2: enroll ────────────────────────────────────────────────
        code, body = _http("POST", "/api/v1/vision/enroll?name=Zidane", token, zidane.read_bytes())
        gate("G2 enroll", code == 200 and json.loads(body).get("ok") is True, f"HTTP {code}")
        _, body = _http("GET", "/api/v1/vision/persons", token)
        persons = json.loads(body).get("persons", [])
        gate("G2b persons listed", any(p.get("name") == "Zidane" for p in persons),
             f"{len(persons)} person(s)")

        # ── G3: create the demo workflow through the real API ────────
        wf = {
            "name": "person seen demo",
            "description": "Toast + audit when the watcher recognizes Zidane",
            "nodes": [
                {"id": "n1", "type": "trigger", "config": {"event": "vision.person_seen"}},
                {"id": "n2", "type": "action",
                 "config": {"tool": "notification.send", "title": "Zidane is here",
                            "message": "The watcher recognized Zidane — workflow fired."}},
                {"id": "n3", "type": "action",
                 "config": {"tool": "audit.log", "event_type": "vision.workflow.demo",
                            "message": "person_seen workflow ran"}},
            ],
            "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
        }
        code, body = _http("POST", "/api/v1/enhanced/workflows/create", token,
                           json.dumps(wf).encode())
        created = json.loads(body)
        wf_id = (created.get("workflow") or {}).get("id", "")
        gate("G3 create workflow", code == 200 and created.get("ok") is True and bool(wf_id),
             f"HTTP {code} {body[:220]!r}")

        code, body = _http(
            "PUT", f"/api/v1/enhanced/workflows/{wf_id}/event-trigger", token,
            json.dumps({"event": "vision.person_seen"}).encode(),
        )
        trig_ok = code == 200 and json.loads(body).get("ok") is True
        gate("G3b event-trigger attached", trig_ok, f"HTTP {code}")

        # ── G4: negative control before firing ───────────────────────
        _, body = _http("GET", "/api/v1/enhanced/workflows/executions?limit=200", token)
        execs = [e for e in json.loads(body).get("executions", [])
                 if e.get("workflow_id") == wf_id]
        gate("G4 zero executions before firing", len(execs) == 0, f"{len(execs)} found")

        # ── G5: fire the watcher through the real scan-now route ─────
        code, body = _http("POST", "/api/v1/vision/watch/scan-now", token, b"")
        cycle = json.loads(body) if code == 200 else {}
        saw = "Zidane" in (cycle.get("persons") or [])
        bus_ok = bool((cycle.get("events") or [{}])[0].get("delivered", {}).get("bus")) \
            if cycle.get("events") else False
        gate("G5 scan-now recognized+published", code == 200 and saw and bus_ok,
             f"HTTP {code} persons={cycle.get('persons')} delivered={bus_ok}")

        # ── G6: the workflow actually ran, with real action results ──
        _, body = _http("GET", "/api/v1/enhanced/workflows/executions?limit=200", token)
        execs = [e for e in json.loads(body).get("executions", [])
                 if e.get("workflow_id") == wf_id and e.get("source") == "event"]
        ok_g6 = False
        detail = f"{len(execs)} event run(s)"
        if len(execs) == 1:
            ar = execs[0].get("action_results") or {}
            toast = ar.get("n2") or {}
            audit = ar.get("n3") or {}
            toast_real = toast.get("status") == "ok" and \
                (toast.get("result") or {}).get("mechanism") == "windows-toast"
            audit_real = audit.get("status") == "ok" and \
                (audit.get("result") or {}).get("logged") is True
            ok_g6 = toast_real and audit_real
            detail = (f"toast={toast.get('status')}/{(toast.get('result') or {}).get('mechanism')} "
                      f"audit={audit.get('status')}")
        gate("G6 event-sourced run with real actions", ok_g6, detail)
        report["execution"] = execs[0] if execs else None

        # ── G7: cooldown honesty — no duplicate fire ──────────────────
        code, body = _http("POST", "/api/v1/vision/watch/scan-now", token, b"")
        cycle2 = json.loads(body) if code == 200 else {}
        _, body = _http("GET", "/api/v1/enhanced/workflows/executions?limit=200", token)
        execs2 = [e for e in json.loads(body).get("executions", [])
                  if e.get("workflow_id") == wf_id and e.get("source") == "event"]
        kinds2 = [e.get("kind") for e in (cycle2.get("events") or []) if e]
        gate("G7 cooldown: no duplicate execution", len(execs2) == 1,
             f"events2={kinds2} execs={len(execs2)}")

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        stop_port(DEMO_PORT)
        if args.keep:
            print(f"temp kept: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    return _finish(gates, tmp, None, keep=True)


def _finish(gates, tmp, proc, keep) -> int:
    passed = sum(1 for _, ok, _ in gates if ok)
    verdict = "PASS" if passed == len(gates) else "FAIL"
    print(f"\nVERDICT: {verdict} ({passed}/{len(gates)} gates)")
    try:
        REPO_ROOT.joinpath("apps/tmp").mkdir(parents=True, exist_ok=True)
        (REPO_ROOT / "apps/tmp/vision_workflow_demo_report.json").write_text(
            json.dumps({"verdict": verdict, "gates": gates}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
