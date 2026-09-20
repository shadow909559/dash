"""Vision smoke test (decisions.md #70): catch live vision regressions automatically.

Boots an ISOLATED DASH backend (temp DB/state, Guardian off, watcher off)
with the REAL vision models copied to a temp dir — real YuNet + SFace +
YOLO run in-process, but enrollment writes land in a throwaway
known_faces.json, never the user's real store — then drives the full
pipeline through the real HTTP API the way #61/#68 did manually:

  G1  status honesty: /vision/status reports every model available
  G2  enrollment:     /enroll (zidane.jpg) -> ok, then /persons shows them
  G3  recognition:    /analyze (zidane.jpg AND a 15deg-tilted copy)
                      matches Zidane >= threshold with landmark_aligned
  G4  no false accept:/analyze (bus.jpg) -> faces found, matches all None,
                      honest "unknown person" status
  G5  objects:        /analyze (bus.jpg) -> YOLO sees a bus (conf >= 0.5)
  G6  camera honesty: /camera/analyze on a no-camera machine -> 503 whose
                      body names the capture cause (this machine has none;
                      on a camera machine this gate is skipped, not faked)
  G7  watcher route:  /watch/status responds 200 with a status dict
  G8  cleanup route:  DELETE /persons/{id} removes the enrollment

Exit 0 iff all applicable gates pass. Writes apps/tmp/vision_smoke_report.json.
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

SMOKE_PORT = 8017
BASE = f"http://127.0.0.1:{SMOKE_PORT}"


def _resolve_photo(name: str) -> Path:
    """Canonical location first, else the ultralytics asset it came from."""
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
    raise SystemExit(f"photo not found: {p} (install ultralytics or copy assets there)")


def _http(method: str, path: str, token: str, body: bytes | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(
        BASE + path,
        data=body,
        method=method,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def stop_port(port: int) -> None:
    """Kill anything already on the smoke port (leftovers from crashed runs)."""
    out = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True
    ).stdout
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line.upper():
            pid = line.split()[-1]
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
            time.sleep(0.5)


def prepare_models_dir(tmp: Path) -> Path:
    """Copy the REAL model files so the app runs them in isolation."""
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


def write_boot_script(state_dir: Path, models_dir: Path, token: str) -> Path:
    backend = BACKEND_DIR.as_posix()
    boot = state_dir / "_smoke_boot.py"
    boot.write_text(
        f'''"""Generated vision-smoke boot: isolated DASH backend on :{SMOKE_PORT}."""
import os, sys

STATE = r"{(state_dir / "state").as_posix()}"
os.environ["DASH_DATABASE_URL"] = "sqlite+aiosqlite:///" + STATE + "/dash.db"
os.environ["DASH_WORKFLOW_STATE"] = STATE + "/workflow_state.json"
os.environ["DASH_GUARDIAN_ENABLED"] = "0"
os.environ["DASH_VISION_WATCHER_ENABLED"] = "0"
os.environ["DASH_AUDIT_LOG_DIR"] = STATE + "/audit_logs"
os.environ["DASH_DEVICE_TOKEN"] = "{token}"
os.environ["DASH_VISION_MODELS"] = r"{models_dir.as_posix()}"
os.environ["DASH_CORS_ORIGINS_RAW"] = "http://localhost:5188,http://127.0.0.1:5188"
sys.path.insert(0, r"{backend}")
os.chdir(r"{backend}")

import uvicorn
from dash_backend.main import create_app
uvicorn.run(create_app(), host="127.0.0.1", port={SMOKE_PORT}, log_level="warning")
''',
        encoding="utf-8",
    )
    return boot


def tilt_15_jpeg(rgb) -> bytes:
    """15-degree roll: within YuNet's detection range (90deg is not)."""
    import cv2

    h, w = rgb.shape[:2]
    mat = cv2.getRotationMatrix2D((w / 2, h / 2), 15.0, 1.0)
    rotated = cv2.warpAffine(rgb, mat, (w, h))
    ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(rotated, cv2.COLOR_RGB2BGR))
    if not ok:
        raise SystemExit("probe encode failed")
    return jpg.tobytes()


def main() -> int:
    global BASE, SMOKE_PORT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=SMOKE_PORT)
    ap.add_argument("--keep", action="store_true", help="keep backend + temp dir for inspection")
    args = ap.parse_args()
    SMOKE_PORT = args.port
    BASE = f"http://127.0.0.1:{SMOKE_PORT}"

    zidane_path = _resolve_photo("zidane.jpg")
    bus_path = _resolve_photo("bus.jpg")
    zidane_bytes = zidane_path.read_bytes()
    bus_bytes = bus_path.read_bytes()

    tmp = Path(tempfile.mkdtemp(prefix="dash_vision_smoke_"))
    (tmp / "state").mkdir()
    models_dir = prepare_models_dir(tmp)
    token = "smoke-" + os.urandom(16).hex()
    boot = write_boot_script(tmp, models_dir, token)
    stop_port(SMOKE_PORT)

    proc = subprocess.Popen(
        [sys.executable, "-u", str(boot)],
        cwd=str(tmp),
        stdout=open(tmp / "boot.log", "wb"),
        stderr=subprocess.STDOUT,
    )
    gates: dict[str, bool] = {}
    report: dict[str, object] = {"gates": gates}
    try:
        # Wait for the backend, then verify the DB actually migrated (#64 lesson).
        deadline = time.time() + 60
        while time.time() < deadline:
            if proc.poll() is not None:
                raise SystemExit(f"backend died during boot; log: {tmp / 'boot.log'}")
            try:
                code, _ = _http("GET", "/api/v1/vision/status", token)
                if code == 200:
                    break
            except urllib.error.URLError:
                pass
            time.sleep(1.0)
        else:
            raise SystemExit(f"backend never became ready; log: {tmp / 'boot.log'}")

        # G1 — status honesty
        code, body = _http("GET", "/api/v1/vision/status", token)
        status = json.loads(body)
        models_ok = all(m["available"] for m in status.get("models", []))
        gates["G1_status"] = (
            code == 200
            and models_ok
            and status.get("face_recognition", {}).get("available") is True
            and status.get("object_detection", {}).get("available") is True
            and status.get("opencv_installed") is True
            and "locally" in status.get("privacy", "")
        )

        # G2 — enrollment through the real route
        code, body = _http("POST", "/api/v1/vision/enroll?name=Zidane", token, zidane_bytes)
        enroll = json.loads(body)
        code2, body2 = _http("GET", "/api/v1/vision/persons", token)
        persons = json.loads(body2).get("persons", [])
        gates["G2_enroll"] = (
            code == 200
            and enroll.get("ok") is True
            and any(p["name"] == "Zidane" for p in persons)
        )
        report["enroll"] = enroll

        def analyze(img: bytes) -> dict:
            c, b = _http("POST", "/api/v1/vision/analyze", token, img)
            assert c == 200, f"/analyze failed: HTTP {c}: {b[:200]}"
            return json.loads(b)

        # G3 — recognition, upright AND 15deg-tilted
        up = analyze(zidane_bytes)
        tilted = analyze(tilt_15_jpeg(rec.decode_to_rgb_array(zidane_bytes)))

        def zidane_match(res: dict):
            for f in res.get("faces", []):
                m = f.get("match")
                if m and m.get("name") == "Zidane" and m.get("similarity", 0) >= 0.5:
                    return m, f.get("landmark_aligned")
            return None, None

        m_up, aligned_up = zidane_match(up)
        m_tilt, _ = zidane_match(tilted)
        gates["G3_recognize"] = (
            m_up is not None
            and aligned_up is True
            and m_tilt is not None
        )
        report["match_upright"] = m_up
        report["match_tilted15"] = m_tilt

        # G4 — no false accept on strangers
        bus = analyze(bus_bytes)
        stranger_matches = [f.get("match") for f in bus.get("faces", [])]
        honest_unknown = all(
            f.get("match_status") == "unknown person"
            for f in bus.get("faces", [])
            if f.get("match") is None
        )
        gates["G4_no_false_accept"] = (
            len(bus.get("faces", [])) >= 1
            and all(m is None for m in stranger_matches)
            and honest_unknown
        )
        report["bus_matches"] = stranger_matches

        # G5 — real object detection
        bus_objects = bus.get("objects", [])
        gates["G5_objects"] = any(
            o.get("name") == "bus" and o.get("confidence", 0) >= 0.5 for o in bus_objects
        )
        report["bus_objects"] = bus_objects[:5]

        # G6 — camera honesty (skip, not fake, when a camera IS present)
        code, body = _http("POST", "/api/v1/vision/camera/analyze", token, b"")
        if code == 200:
            gates["G6_camera_honesty"] = True
            report["camera"] = "camera present — analyze succeeded (gate vacuous)"
        else:
            text = body.decode("utf-8", errors="replace")
            gates["G6_camera_honesty"] = (
                code == 503
                and "camera capture failed" in text
                and ("device" in text.lower() or "opencv" in text.lower() or "frame" in text.lower())
            )
            report["camera"] = {"code": code, "body": text[:200]}

        # G7 — watcher route answers honestly (watcher disabled in this boot)
        code, body = _http("GET", "/api/v1/vision/watch/status", token)
        gates["G7_watch_status"] = code == 200 and "available" in json.loads(body)

        # G8 — cleanup route removes the enrollment
        pid = next((p["person_id"] for p in persons if p["name"] == "Zidane"), None)
        code, _ = _http("DELETE", f"/api/v1/vision/persons/{pid}", token) if pid else (0, b"")
        code2, body2 = _http("GET", "/api/v1/vision/persons", token)
        gates["G8_delete_person"] = (
            pid is not None and code == 200 and not json.loads(body2).get("persons")
        )

        ok = all(gates.values())
        report["verdict"] = "PASS" if ok else "FAIL"
        out = REPO_ROOT / "tmp" / "vision_smoke_report.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        for name in sorted(gates):
            print(f"{name}: {'PASS' if gates[name] else 'FAIL'}")
        print("VERDICT:", "PASS" if ok else "FAIL")
        print("report:", out)
        return 0 if ok else 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"kept: {tmp}")


if __name__ == "__main__":
    raise SystemExit(main())
