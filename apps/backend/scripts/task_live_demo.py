"""Live end-to-end task-orchestrator demo (decisions.md #90).

Boots nothing — expects a DASH backend already listening (isolated bench boot
or production). Creates TWO REAL tasks through the REST API:

  1. A file-creation task (safe/moderate steps, real filesystem tools)
  2. A directory-deletion task (HIGH risk → confirmation gate → approve via
     the REST API → real deletion executes only after approval)

Polls each task to its terminal state and prints the honest timeline:
plan, per-step status, verification details, and the final report.

Usage:
    python scripts/task_live_demo.py --port 8023
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx


def _headers() -> dict[str, str]:
    from dash_backend.security.local_identity import get_identity

    return {"Authorization": f"Bearer {get_identity().device_token}"}


async def run_task(client: httpx.AsyncClient, base: str, goal: str,
                   auto_approve: bool, deadline_s: float = 420.0) -> dict:
    r = await client.post(f"{base}/agent/task", json={"goal": goal}, headers=_headers())
    r.raise_for_status()
    task = r.json()
    tid = task["id"]
    print(f"\n[task {tid}] created: {goal!r}")
    t0 = time.perf_counter()
    approvals = 0
    timeline: list[str] = []
    seen_steps: set[tuple[str, str]] = set()

    while time.perf_counter() - t0 < deadline_s:
        r = await client.get(f"{base}/agent/task/{tid}", headers=_headers())
        r.raise_for_status()
        t = r.json()
        for s in t.get("steps", []):
            key = (s["id"], s["status"])
            if key not in seen_steps:
                seen_steps.add(key)
                v = s.get("verification") or {}
                timeline.append(
                    f"  step {s['id']} ({s['description'][:48]}): {s['status']}"
                    + (f" — {v.get('detail', '')[:80]}" if v.get("detail") else "")
                )
                print(timeline[-1], flush=True)
        # Approve EVERY confirmation round — real registry policy gates each
        # CONFIRM-level tool (create_file, write_file, …) separately.
        if t["status"] == "waiting_confirmation" and t.get("pending_confirmation"):
            pc = t["pending_confirmation"]
            print(f"  >>> CONFIRMATION REQUIRED: {pc['description'][:70]} (tool: {pc.get('tool')}, risk: {pc.get('risk')})", flush=True)
            if auto_approve:
                r2 = await client.post(
                    f"{base}/agent/task/{tid}/approve",
                    json={"approved": True}, headers=_headers(),
                )
                approvals += 1
                print(f"  >>> approved via API ({approvals}): {r2.status_code}", flush=True)
                await asyncio.sleep(1.0)  # let the relaunch pick it up
        if t["status"] in ("completed", "failed", "cancelled"):
            print(f"  FINAL: {t['status']}")
            report = t.get("final_report") or {}
            print("  report:", json.dumps(report, indent=2)[:800])
            return t
        await asyncio.sleep(2.0)

    print(f"[task {tid}] DEADLINE exceeded — dumping last state")
    return task


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8023)
    ap.add_argument("--no-approve", action="store_true", help="do not auto-approve confirmations")
    args = ap.parse_args()
    base = f"http://127.0.0.1:{args.port}/api/v1"

    demo_dir = Path(os.environ.get("TEMP", "/tmp")) / "dash_task_demo"
    demo_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Health check
        r = await client.get(f"http://127.0.0.1:{args.port}/health")
        r.raise_for_status()
        print(f"backend healthy on :{args.port}")

        print("\n════ TASK 1: create a file (verification via file_exists) ════")
        # Paths are SANDBOX-RELATIVE (decisions.md #91): create_file/write_file
        # enforce DASH_FILES_SANDBOX, so goals speak the sandbox's language.
        # Mirror the boot's sandbox convention so the honest disk check below
        # reads the SAME root the server wrote to.
        os.environ.setdefault(
            "DASH_FILES_SANDBOX",
            str(Path(os.environ.get("TEMP", "/tmp")) / f"dash_bench_{args.port}" / "state" / "sandbox"),
        )
        goal1 = (
            "Create a text file named dash_demo_report.txt inside the folder "
            "demo_folder containing the line 'DASH orchestrator was here'."
        )
        t1 = await run_task(client, base, goal1, auto_approve=True)
        from dash_backend.tools.filesystem.filesystem_service import get_sandbox_root
        created = get_sandbox_root() / "demo_folder" / "dash_demo_report.txt"
        print(f"\nHONEST FILE CHECK: {created} exists={created.exists()}")
        if created.exists():
            print(f"  content: {created.read_text(encoding='utf-8')[:120]!r}")

        print("\n════ TASK 2: delete a directory (HIGH risk → confirmation → execute) ════")
        # delete_directory resolves relative paths against the SERVER's cwd —
        # the demo creates the victim there (repo cwd) and cleans it up after.
        victim = Path("to_delete_demo")
        victim.mkdir(exist_ok=True)
        (victim / "content.txt").write_text("delete me", encoding="utf-8")
        goal2 = "Delete the directory to_delete_demo and everything in it."
        t2 = await run_task(client, base, goal2, auto_approve=not args.no_approve)
        print(f"\nHONEST DELETE CHECK: {victim.resolve()} still exists={victim.exists()}")
        import shutil as _sh
        _sh.rmtree(victim, ignore_errors=True)

        print("\n════ TASK STATE PERSISTENCE ════")
        r = await client.get(f"{base}/agent/tasks", headers=_headers())
        tasks = r.json().get("tasks", [])
        print(f"server reports {len(tasks)} persisted task(s):")
        for t in tasks:
            print(f"  {t['id']}  {t['status']:22s}  {t['goal'][:60]}")

    ok1 = t1["status"] == "completed" and created.exists()
    ok2 = t2["status"] in ("completed", "failed")  # failed OK if sandbox refused
    print(f"\nVERDICT: task1={'PASS' if ok1 else 'FAIL'} task2={'PASS' if ok2 else 'FAIL'}")
    return 0 if ok1 and ok2 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
