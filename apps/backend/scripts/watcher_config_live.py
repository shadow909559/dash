"""Live verification of the user-configurable watcher (decisions.md #73).

Boots an ISOLATED backend (temp DB, temp config, real models, watcher
ENABLED with the static-frame photon source) and drives the new API over
real HTTP:

  G1  GET  /vision/watch/config      → defaults + limits + file path
  G2  PUT  /vision/watch/config      → applied live + persisted to disk
  G3  invalid interval → 422, nothing changed (all-or-nothing)
  G4  invalid camera_id → 422
  G5  restart → config survives (re-applied at boot from the JSON file)
  G6  per-person notify: opt-out persists, unknown person 404s
  G7  the running loop obeys the configured interval (cycle count grows
      over ~2 configured intervals with the static frame)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parents[1]
PORT = 8022
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "cfglive-" + os.urandom(12).hex()

_passed = 0
_failed = 0


def _gate(name: str, ok: bool, detail: str = "") -> None:
    global _passed, _failed
    tag = "PASS" if ok else "FAIL"
    if ok:
        _passed += 1
    else:
        _failed += 1
    print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""))


def _http(method: str, path: str, body: bytes | None = None, json_body: dict | None = None):
    data = None
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif body is not None:
        data = body
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def stop_port(port: int) -> None:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess"],
        capture_output=True, text=True,
    )
    for line in out.stdout.split():
        if line.strip().isdigit():
            subprocess.run(["taskkill", "/F", "/PID", line.strip()], capture_output=True)


def write_boot(state_dir: Path, models_dir: Path) -> Path:
    boot = state_dir / "_cfg_boot.py"
    boot.write_text(
        f'''"""Generated watcher-config live boot: isolated DASH backend on :{PORT}."""
import os, sys

STATE = r"{(state_dir / "state").as_posix()}"
os.environ["DASH_DATABASE_URL"] = "sqlite+aiosqlite:///" + STATE + "/dash.db"
os.environ["DASH_WORKFLOW_STATE"] = STATE + "/workflow_state.json"
os.environ["DASH_GUARDIAN_ENABLED"] = "0"
os.environ["DASH_VISION_WATCHER_ENABLED"] = "1"
os.environ["DASH_VISION_STATIC_FRAME"] = r"{(state_dir / "frame.jpg").as_posix()}"
os.environ["DASH_WATCHER_CONFIG"] = STATE + "/watcher_config.json"
os.environ["DASH_AUDIT_LOG_DIR"] = STATE + "/audit_logs"
os.environ["DASH_DEVICE_TOKEN"] = "{TOKEN}"
os.environ["DASH_VISION_MODELS"] = r"{models_dir.as_posix()}"
os.environ["DASH_CORS_ORIGINS_RAW"] = "http://localhost:5188"
sys.path.insert(0, r"{BACKEND_DIR.as_posix()}")
os.chdir(r"{BACKEND_DIR.as_posix()}")

import uvicorn
from dash_backend.main import create_app
uvicorn.run(create_app(), host="127.0.0.1", port={PORT}, log_level="warning")
''',
        encoding="utf-8",
    )
    return boot


def wait_ready(proc: subprocess.Popen, log: Path, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            print(log.read_text(encoding="utf-8", errors="replace")[-2000:])
            raise SystemExit("backend died during boot")
        try:
            code, _ = _http("GET", "/api/v1/vision/watch/config")
            if code == 200:
                return
        except urllib.error.URLError:
            pass
        time.sleep(1.0)
    raise SystemExit("backend never became ready")


def _resolve_photo(name: str) -> Path:
    """Same resolution as the vision smoke test (canonical dir, then the
    ultralytics asset the photos came from)."""
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
    raise SystemExit(f"photo not found: {name}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="dash_cfg_live_"))
    (tmp / "state").mkdir()
    # Real models, isolated enrollment: the smoke test's proven copier
    # (resolves the canonical models dir + exact file names).
    sys.path.insert(0, str(BACKEND_DIR / "scripts"))
    from vision_smoke_test import prepare_models_dir

    models_dir = tmp / "models"
    models_dir.mkdir()
    models_dir = prepare_models_dir(models_dir)
    # The static-frame photon source: a real enrolled photo.
    photo = _resolve_photo("zidane.jpg")
    (tmp / "frame.jpg").write_bytes(photo.read_bytes())

    boot = write_boot(tmp, models_dir)
    stop_port(PORT)
    proc = subprocess.Popen(
        [sys.executable, "-u", str(boot)],
        cwd=str(tmp),
        stdout=open(tmp / "boot.log", "wb"),
        stderr=subprocess.STDOUT,
    )
    try:
        wait_ready(proc, tmp / "boot.log")

        # G1 — defaults + limits
        code, body = _http("GET", "/api/v1/vision/watch/config")
        cfg = json.loads(body)
        _gate(
            "G1 config defaults+limits",
            code == 200
            and cfg["interval_seconds"] == 30.0
            and cfg["repeat_cooldown_s"] == 600.0
            and cfg["camera_id"] == 0
            and cfg["limits"]["interval_seconds_min"] == 5.0
            and "config_file" in cfg,
            f"interval={cfg.get('interval_seconds')}",
        )

        # G2 — valid PUT: applied + persisted
        code, body = _http(
            "PUT", "/api/v1/vision/watch/config",
            json_body={"interval_seconds": 6.0, "repeat_cooldown_s": 15.0},
        )
        applied = json.loads(body) if code == 200 else {}
        on_disk = json.loads((tmp / "state" / "watcher_config.json").read_text())
        _gate(
            "G2 valid PUT applied+persisted",
            code == 200
            and applied.get("interval_seconds") == 6.0
            and on_disk["watcher"]["interval_seconds"] == 6.0
            and on_disk["watcher"]["repeat_cooldown_s"] == 15.0,
        )

        # G3 — invalid interval: 422, nothing changed
        code, body = _http(
            "PUT", "/api/v1/vision/watch/config",
            json_body={"interval_seconds": 0.1, "camera_id": 1},
        )
        cfg_now = json.loads(_http("GET", "/api/v1/vision/watch/config")[1])
        _gate(
            "G3 invalid interval 422 + all-or-nothing",
            code == 422 and cfg_now["camera_id"] == 0 and cfg_now["interval_seconds"] == 6.0,
            f"http={code} detail={body[:80]!r}",
        )

        # G4 — invalid camera_id
        code, _ = _http("PUT", "/api/v1/vision/watch/config", json_body={"camera_id": 999})
        _gate("G4 invalid camera_id 422", code == 422)

        # G5 — persistence across a real restart
        proc.kill()
        proc.wait(timeout=10)
        time.sleep(1.0)
        proc = subprocess.Popen(
            [sys.executable, "-u", str(boot)],
            cwd=str(tmp),
            stdout=open(tmp / "boot2.log", "wb"),
            stderr=subprocess.STDOUT,
        )
        wait_ready(proc, tmp / "boot2.log")
        cfg_after = json.loads(_http("GET", "/api/v1/vision/watch/config")[1])
        _gate(
            "G5 config survives restart",
            cfg_after["interval_seconds"] == 6.0
            and cfg_after["repeat_cooldown_s"] == 15.0
            and cfg_after["camera_id"] == 0,
        )

        # G6 — per-person notify prefs over the real API
        code, body = _http(
            "POST", "/api/v1/vision/enroll?name=Zidane", body=photo.read_bytes()
        )
        enroll = json.loads(body) if body else {}
        if code != 200:
            print(f"    enroll debug: http={code} body={body[:300]!r}")
        pid = enroll.get("person_id", "")
        ok_enroll = code == 200 and bool(pid)
        code, _ = _http("PUT", f"/api/v1/vision/persons/{pid}/notify", json_body={"notify": False})
        persons = json.loads(_http("GET", "/api/v1/vision/persons")[1])["persons"]
        flagged = [p for p in persons if p["person_id"] == pid]
        code404, _ = _http("PUT", "/api/v1/vision/persons/ghost/notify", json_body={"notify": True})
        _gate(
            "G6 per-person notify pref",
            ok_enroll
            and code == 200
            and flagged and flagged[0]["notify"] is False
            and code404 == 404,
            f"enroll={code} persons={len(persons)}",
        )

        # G7 — the running loop obeys the configured interval
        st1 = json.loads(_http("GET", "/api/v1/vision/watch/status")[1])
        time.sleep(13.0)  # ~2 configured intervals (6s) + cycle time
        st2 = json.loads(_http("GET", "/api/v1/vision/watch/status")[1])
        cycles_grew = st2["cycles"] > st1["cycles"] and st2["running"] is True
        person_seen = any(
            e.get("kind") == "person_seen" for e in st2.get("recent_events", [])
        )
        _gate(
            "G7 live loop uses configured interval",
            cycles_grew,
            f"cycles {st1['cycles']}→{st2['cycles']} person_seen={person_seen}",
        )

        # G8 — desktop toast: opt-in via API, real toast on a real sighting.
        # Re-enroll with per-sample growth; enroll appends a sample.
        code, body = _http(
            "PUT", "/api/v1/vision/watch/config",
            json_body={
                "notify_known_persons": True,
                "notify_cooldown_s": 0,
                "repeat_cooldown_s": 0,
            },
        )
        assert code == 200, body[:200]
        # G6 opted Zidane out to test per-person prefs — that suppression
        # (correctly) outranks the global toast switch. Re-enable him:
        code, _ = _http(
            "PUT", f"/api/v1/vision/persons/{pid}/notify", json_body={"notify": True}
        )
        assert code == 200
        code, body = _http("POST", "/api/v1/vision/watch/scan-now")
        cycle = json.loads(body)
        person_events = [e for e in cycle.get("events", []) if e.get("kind") == "person_seen"]
        toast_ok = any(
            e.get("delivered", {}).get("toast") is True for e in person_events
        )
        st = json.loads(_http("GET", "/api/v1/vision/watch/status")[1])
        _gate(
            "G8 opt-in fires a real desktop toast",
            code == 200 and person_events != [] and toast_ok
            and (st.get("last_toast") or {}).get("status") == "ok"
            and st.get("notify_known_persons") is True,
            f"person_events={len(person_events)} "
            f"cycle_kinds={[e.get('kind') for e in cycle.get('events', [])]} "
            f"last_cycle={cycle.get('persons')} cap_err={cycle.get('capture_error')} "
            f"analyze={cycle.get('analyze_reason')} "
            f"last_toast={(st.get('last_toast') or {}).get('status')}",
        )

        # G9 — a string "yes" is NOT a bool at the public boundary.
        code, body = _http(
            "PUT", "/api/v1/vision/watch/config",
            json_body={"notify_known_persons": "yes"},
        )
        _gate("G9 string 'yes' rejected 422 (strict bool)", code == 422)

        # G10 — opt back out: person events keep flowing, toast key gone.
        code, _ = _http(
            "PUT", "/api/v1/vision/watch/config",
            json_body={"notify_known_persons": False},
        )
        code2, body2 = _http("POST", "/api/v1/vision/watch/scan-now")
        cycle2 = json.loads(body2)
        pe2 = [e for e in cycle2.get("events", []) if e.get("kind") == "person_seen"]
        _gate(
            "G10 opt-out removes the toast key",
            code == 200 and pe2 != []
            and all("toast" not in e.get("delivered", {}) for e in pe2),
            f"person_events={len(pe2)}",
        )
    finally:
        stop_port(PORT)
        try:
            proc.kill()
        except Exception:
            pass

    print(f"\nVERDICT: {'PASS' if _failed == 0 else 'FAIL'} ({_passed} passed, {_failed} failed)")
    print(f"(temp dir: {tmp} — delete freely)")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
