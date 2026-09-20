"""Continuous-schedule soak test: prove an every-minute workflow keeps
firing across a mid-run backend restart, and account for every minute.

Boots an ISOLATED backend (temp DB / temp workflow state / Guardian off /
audit dir temp), creates one `* * * * *` workflow through the real API,
soaks for N minutes (default 10), restarts the whole process mid-run
(default after 5), harvests the real execution history
(source == "scheduled"), and prints a timeline of fires vs. local minute
boundaries:

    minute  :00  :01  :02 ... with OK / MISS / X2 marks and a final verdict

Exit code 0 only when the verdict starts with CLEAN.

Honest accounting rules (see analyze_soak):
- A minute whose boundary elapsed while the backend was DOWN is EXPECTED_DOWN
  — the scheduler cannot evaluate cron while dead, and the restart contract
  (decisions.md #53) only promises no double-fire, not firing while stopped.
- MISS_HARD: the backend was up across a boundary and nothing fired.
- MISS_GRACE: nothing fired, but the boundary was within GRACE_S of the
  process becoming ready (poll phase alignment) — reported separately so a
  first-tick lag is visible without failing the run.
- DOUBLE: more than one scheduled fire landed in one boundary minute —
  the one bug this soak exists to catch.

Usage:
    python scripts/soak_schedule.py [--minutes 10] [--restart-after 5]
                                    [--port 8015] [--keep]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# scripts/soak_schedule.py → parents: [0]=scripts, [1]=backend, [2]=apps, [3]=repo
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "apps" / "backend"

GRACE_S = 5.0          # boundary within this of ready-time → miss is "grace"
HISTORY_LIMIT = 200    # executions harvest limit (the route's own max)

Status = str  # OK | X2 | MISS_HARD | MISS_GRACE | EXPECTED_DOWN


# ── Analysis core (pure; hermetically tested) ─────────────────────────────


def _boundary_key(started_at_utc: str, local_tz) -> str:
    """Map an execution's started_at (ISO, UTC) to its LOCAL boundary minute
    (YYYY-MM-DD HH:MM). Fires within the same local minute share a key."""
    dt = datetime.fromisoformat(started_at_utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(local_tz)
    return local.strftime("%Y-%m-%d %H:%M")


def analyze_soak(
    fires: list[dict],
    down_windows: list[tuple[datetime, datetime]],
    first_ready: datetime,
    local_tz=None,
) -> dict:
    """Bucket real scheduled fires into local boundary minutes and classify
    every minute of the soak.

    fires: [{"started_at": iso-utc, "id": str}, ...] — ONLY source=scheduled
    down_windows: [(start, end)] when no backend was alive (inclusive of the
      boundary minute the gap covers)
    first_ready: local datetime the FIRST boot became ready (grace anchor).
      TZ-aware values are normalized to naive local — boundary keys parse
      naive, and mixing aware/naive would raise at analysis time.
    """
    from collections import Counter

    local_tz = local_tz or datetime.now().astimezone().tzinfo
    if first_ready is not None and first_ready.tzinfo is not None:
        first_ready = first_ready.astimezone(local_tz).replace(tzinfo=None)
    down_windows = [
        (s.astimezone(local_tz).replace(tzinfo=None) if s.tzinfo is not None else s,
         e.astimezone(local_tz).replace(tzinfo=None) if e.tzinfo is not None else e)
        for s, e in down_windows
    ]

    counts: Counter[str] = Counter()
    exec_ids: dict[str, list[str]] = {}
    for f in fires:
        key = _boundary_key(f["started_at"], local_tz)
        counts[key] += 1
        exec_ids.setdefault(key, []).append(str(f.get("id", "?")))

    if not counts:
        return {
            "verdict": "NO_FIRES",
            "minutes": [],
            "counts": {},
            "summary": {"ok": 0, "double": 0, "miss_hard": 0, "miss_grace": 0, "expected_down": 0},
        }

    # The soak spans from the first fired boundary to the last (the soak's
    # real observed window — wall-clock soak length ≠ cron window).
    keys = sorted(counts)
    first_dt = datetime.strptime(keys[0], "%Y-%m-%d %H:%M")
    last_dt = datetime.strptime(keys[-1], "%Y-%m-%d %H:%M")

    def in_down_window(dt: datetime) -> bool:
        for start, end in down_windows:
            if start <= dt <= end:
                return True
        return False

    minutes: list[dict] = []
    summary = {"ok": 0, "double": 0, "miss_hard": 0, "miss_grace": 0, "expected_down": 0}
    cur = first_dt
    while cur <= last_dt:
        key = cur.strftime("%Y-%m-%d %H:%M")
        n = counts.get(key, 0)
        boundary_end = cur + timedelta(minutes=1)
        if n == 1:
            status: Status = "OK"
        elif n > 1:
            status = "X2"
        elif in_down_window(cur) or in_down_window(boundary_end - timedelta(seconds=1)):
            status = "EXPECTED_DOWN"
        elif (cur - first_ready).total_seconds() < GRACE_S:
            status = "MISS_GRACE"
        elif any(
            0 <= (cur - end).total_seconds() < GRACE_S
            for _, end in down_windows
        ):
            # Right after a restart the new poll phase may consume this
            # boundary's first tick — visible, but not a broken contract.
            status = "MISS_GRACE"
        else:
            status = "MISS_HARD"
        summary[
            {"OK": "ok", "X2": "double", "MISS_HARD": "miss_hard",
             "MISS_GRACE": "miss_grace", "EXPECTED_DOWN": "expected_down"}[status]
        ] += 1
        minutes.append({
            "minute": key,
            "fires": n,
            "status": status,
            "exec_ids": exec_ids.get(key, []),
        })
        cur += timedelta(minutes=1)

    verdict = "CLEAN"
    if summary["double"] or summary["miss_hard"]:
        verdict = "FAILED"
    elif summary["miss_grace"]:
        verdict = "CLEAN_WITH_GRACE_MISS"
    return {"verdict": verdict, "minutes": minutes, "counts": dict(counts), "summary": summary}


def render_timeline(report: dict) -> str:
    """Human timeline: one line per boundary minute with a mark.
    ASCII-only so Windows cp1252 consoles never choke on rendering."""
    lines: list[str] = []
    total = len(report["minutes"])
    lines.append(f"Timeline — {total} boundary minutes observed")
    lines.append("")
    for m in report["minutes"]:
        hhmm = m["minute"][-5:]
        if m["status"] == "OK":
            mark, extra = "OK ", ""
        elif m["status"] == "X2":
            mark, extra = "X2 ", "  <-- DOUBLE FIRE ({}x)".format(m["fires"])
        elif m["status"] == "MISS_HARD":
            mark, extra = "!! ", "  <-- expected a fire, backend was UP, none came"
        elif m["status"] == "MISS_GRACE":
            mark, extra = "~! ", "  <-- no fire within startup grace (first poll phase)"
        else:
            mark, extra = "-- ", "  <-- backend down (restart window)"
        lines.append("  {}  {} fires={}{}".format(hhmm, mark, m["fires"], extra))
    lines.append("")
    s = report["summary"]
    lines.append(
        f"Summary: {s['ok']} OK · {s['expected_down']} expected-down · "
        f"{s['miss_grace']} grace-miss · {s['miss_hard']} hard-miss · {s['double']} double"
    )
    lines.append(f"Verdict: {report['verdict']}")
    return "\n".join(lines)


# ── Live runner (process + HTTP) ──────────────────────────────────────────


def _http_json(base: str, path: str, method: str = "GET", token: str | None = None,
               body: dict | None = None, timeout: float = 10) -> tuple[int, dict]:
    req = urllib.request.Request(f"{base}{path}", method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")

    def _parse(raw: bytes) -> dict:
        """Error bodies may be empty or plain text (tracebacks) — never let
        response parsing mask the status code we are about to report."""
        try:
            return json.loads(raw.decode() or "{}")
        except ValueError:
            return {"_nonjson": raw.decode(errors="replace")[:500]}

    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
            return resp.status, _parse(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read())


def wait_ready(port: int, deadline_s: float = 60) -> bool:
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def stop_port(pid_hint: int | None = None, port: int | None = None) -> None:
    """Kill the process listening on `port` (or the pid) via netstat/taskkill."""
    if pid_hint:
        subprocess.run(["taskkill", "/F", "/PID", str(pid_hint)],
                       capture_output=True, check=False)
        return
    if not port:
        return
    out = subprocess.run(
        f'netstat -ano | findstr ":{port}" | findstr LISTENING',
        shell=True, capture_output=True, text=True, check=False,
    ).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            subprocess.run(["taskkill", "/F", "/PID", parts[-1]],
                           capture_output=True, check=False)
            return


def write_boot_script(state_dir: Path, port: int, token: str) -> Path:
    """Generated boot for an isolated backend generation.

    DASH_DEVICE_TOKEN is pinned so BOTH generations accept the same bearer
    token — the identity file's location is machine-global and must not be
    part of what a restart can change.
    """
    state = (state_dir / "state").as_posix()
    backend = (REPO_ROOT / "apps" / "backend").as_posix()
    boot = state_dir / "_soak_boot.py"
    boot.write_text(
        f'''"""Generated soak boot: isolated DASH backend on :{port}."""
import os, sys

STATE = r"{state}"
os.environ["DASH_DATABASE_URL"] = "sqlite+aiosqlite:///" + STATE + "/dash.db"
os.environ["DASH_WORKFLOW_STATE"] = STATE + "/workflow_state.json"
os.environ["DASH_GUARDIAN_ENABLED"] = "0"
os.environ["DASH_VISION_WATCHER_ENABLED"] = "0"
os.environ["DASH_AUDIT_LOG_DIR"] = STATE + "/audit_logs"
os.environ["DASH_DEVICE_TOKEN"] = "{token}"
os.environ["DASH_CORS_ORIGINS_RAW"] = "http://localhost:5188,http://127.0.0.1:5188"
sys.path.insert(0, r"{backend}")
os.chdir(r"{backend}")

import uvicorn
from dash_backend.main import create_app
uvicorn.run(create_app(), host="127.0.0.1", port={port}, log_level="warning")
''',
        encoding="utf-8",
    )
    return boot


def harvest(port: int, token: str, wf_id: str) -> list[dict]:
    status, body = _http_json(
        f"http://127.0.0.1:{port}",
        f"/api/v1/enhanced/workflows/{wf_id}/executions?limit={HISTORY_LIMIT}",
        token=token,
    )
    if status != 200:
        raise RuntimeError(f"executions harvest failed: HTTP {status}: {body}")
    return [
        {"id": e["id"], "started_at": e["started_at"], "source": e.get("source", "?")}
        for e in body.get("executions", [])
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--minutes", type=int, default=10, help="soak length in minutes")
    ap.add_argument("--restart-after", type=int, default=5, help="restart this many minutes in")
    ap.add_argument("--port", type=int, default=8015)
    ap.add_argument("--keep", action="store_true", help="leave backend running after the run")
    args = ap.parse_args()

    if args.minutes < 3 or args.restart_after < 1 or args.restart_after >= args.minutes:
        print("need minutes >= 3 and 1 <= restart-after < minutes", file=sys.stderr)
        return 2

    state_dir = Path(os.environ.get("DASH_SOAK_DIR") or
                     Path(os.environ.get("TEMP", "/tmp")) / "dash_soak_run")
    state_dir.mkdir(parents=True, exist_ok=True)
    # The boot script writes the DB into state/ — alembic opens it before
    # anything else creates the directory ("unable to open database file"
    # otherwise, and create_app only LOGS that failure and boots anyway).
    (state_dir / "state").mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{args.port}"
    down_windows: list[tuple[datetime, datetime]] = []

    # Fixed bearer token for every generation of this run (see write_boot_script).
    token = "soak-" + os.urandom(16).hex()

    def launch() -> subprocess.Popen:
        boot = write_boot_script(state_dir, args.port, token)
        return subprocess.Popen(
            [sys.executable, str(boot)],
            stdout=open(state_dir / "backend.log", "ab"),
            stderr=subprocess.STDOUT,
            cwd=str(BACKEND_DIR),
        )

    print(f"=== Soak: every-minute schedule, {args.minutes} min, restart at {args.restart_after} ===", flush=True)
    print(f"state: {state_dir}  port: {args.port}", flush=True)

    stop_port(port=args.port)  # never soak against a stale process
    proc = launch()
    if not wait_ready(args.port):
        print("backend did not become ready", file=sys.stderr)
        return 2

    def _db_ok() -> tuple[bool, str]:
        """wait_ready only proves HTTP is up; migrations may have failed
        silently and the first write would then hit a missing table. Probe
        a read that touches the real schema and name the cause on failure."""
        code, body = _http_json(base, "/api/v1/enhanced/workflows?limit=1", token=token)
        if code == 200:
            return True, ""
        return False, f"DB probe failed (HTTP {code}): {body}"

    for gen in (1, 2):
        ok, why = _db_ok()
        if ok:
            break
        if gen == 2:
            print(f"backend up but database unusable: {why}", file=sys.stderr)
            stop_port(pid_hint=proc.pid)
            return 2
        # one clean retry: kill, wipe, boot again (first-boot-only failure)
        print(f"database probe failed ({why}) — retrying once with a clean state", file=sys.stderr)
        stop_port(pid_hint=proc.pid)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pass
        (state_dir / "state" / "dash.db").unlink(missing_ok=True)
        proc = launch()
        if not wait_ready(args.port):
            print("backend did not become ready on retry", file=sys.stderr)
            return 2

    first_ready = datetime.now().astimezone()
    print(f"boot 1 ready at {first_ready:%H:%M:%S}", flush=True)

    _s, tok_body = _http_json(base, "/api/v1/devtools/device-token")
    dev_token = tok_body.get("token") or token
    _s, wf_body = _http_json(
        base, "/api/v1/enhanced/workflows/create", "POST", dev_token,
        {"name": "Soak Every Minute", "nodes": [], "edges": []},
    )
    wf_id = wf_body["workflow"]["id"]
    _s, sched = _http_json(
        base, f"/api/v1/enhanced/workflows/{wf_id}/schedule", "POST", dev_token,
        {"cron": "* * * * *", "timezone": "UTC"},
    )
    if not sched.get("ok"):
        print(f"schedule rejected: {sched}", file=sys.stderr)
        return 2
    created = datetime.now().astimezone()
    print(f"workflow {wf_id} scheduled (* * * * *) at {created:%H:%M:%S} — soaking…", flush=True)

    restart_at = time.monotonic() + args.restart_after * 60
    end_at = time.monotonic() + args.minutes * 60
    restarted = False
    while time.monotonic() < end_at:
        time.sleep(5)
        if not restarted and time.monotonic() >= restart_at:
            print(f"[{datetime.now():%H:%M:%S}] RESTART: killing backend mid-soak…", flush=True)
            down_from = datetime.now().astimezone()
            stop_port(pid_hint=proc.pid)
            proc.wait(timeout=15)
            time.sleep(2)
            proc = launch()
            if not wait_ready(args.port):
                print("backend did not come back after restart", file=sys.stderr)
                return 2
            ok, why = _db_ok()
            if not ok:
                print(f"backend came back but database unusable: {why}", file=sys.stderr)
                stop_port(pid_hint=proc.pid)
                return 2
            ready = datetime.now().astimezone()
            down_windows.append((down_from, ready))
            print(f"[{ready:%H:%M:%S}] restart ready (down {(ready - down_from).total_seconds():.0f}s)", flush=True)
            restarted = True

    harvest_from = datetime.now().astimezone()
    all_fires = harvest(args.port, dev_token, wf_id)
    scheduled = [f for f in all_fires if f["source"] == "scheduled"]
    others = [f for f in all_fires if f["source"] != "scheduled"]

    stop_port(pid_hint=proc.pid)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        pass

    report = analyze_soak(scheduled, down_windows, first_ready)
    print()
    print(render_timeline(report))
    print()
    print(f"runs harvested: {len(all_fires)} total, {len(scheduled)} scheduled, "
          f"{len(others)} other-source", flush=True)
    if others:
        bad = sorted({f['source'] for f in others})
        print(f"  non-scheduled sources present: {bad} — investigate (schedule "
              f"fires must never come from another path)", flush=True)
    out = state_dir / "soak_report.json"
    out.write_text(json.dumps({
        "wf_id": wf_id,
        "created_at": created.isoformat(),
        "harvested_at": harvest_from.isoformat(),
        "down_windows": [[a.isoformat(), b.isoformat()] for a, b in down_windows],
        "first_ready": first_ready.isoformat(),
        "report": report,
        "fires": scheduled,
    }, indent=2), encoding="utf-8")
    print(f"full report: {out}", flush=True)

    if args.keep:
        proc = launch()
        wait_ready(args.port)
        print(f"backend left running on :{args.port} (--keep)", flush=True)

    return 0 if report["verdict"].startswith("CLEAN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
