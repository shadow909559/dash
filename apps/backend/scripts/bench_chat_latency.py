"""Chat latency benchmark: drives the REAL websocket chat path (decisions.md #89).

Connects to a running DASH backend as an authenticated device, sends a fixed
set of representative messages N times each, and measures with monotonic
timers:

    ttft_ms  — send → first chat.token (Time To First Token, the metric that
               dominates perceived responsiveness)
    total_ms — send → chat.done

Every value is printed; medians and p95 are computed over the runs. No
synthetic delays, no fabricated numbers — whatever the pipeline does is what
gets measured.

Usage:
    python scripts/bench_chat_latency.py --port 8000 --runs 5 [--warmup 1]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import websockets  # type: ignore[import-untyped]

SCENARIOS: dict[str, str] = {
    # Short factual exchange — the purest TTFT signal.
    "simple": "What is 2+2? Answer in one short sentence.",
    # Forces the memory-retrieval stage to matter.
    "memory": "What do you remember about me? Answer briefly.",
    # Forces RAG retrieval + a slightly longer answer.
    "rag": "Briefly summarize what you know from my documents.",
    # Exercises the tool-call loop (LLM → tool → LLM).
    "tool": "What time is it right now? Use a tool if you have one.",
    # Voice mode: shorter system prompt, the path the wake loop uses.
    "voice_simple": "What is 2+2? Answer in one short sentence.",
}


def _device_token() -> str:
    from dash_backend.security.local_identity import get_identity

    return get_identity().device_token


async def run_one(ws, content: str, *, voice_mode: bool = False, debug: bool = False, deadline_s: float = 240.0) -> tuple[float, float, dict]:
    """Send one chat.send; return (ttft_ms, total_ms, stage_ms) via monotonic clocks.

    A per-message wall deadline (checked between frames) prevents server push
    frames (system status, notifications) from resetting recv timeouts and
    masking a genuinely hung path — the failure mode that hid the baseline's
    30-90s CPU-only generations.
    """
    message_id = str(uuid.uuid4())
    frame = {
        "type": "chat.send",
        "message_id": message_id,
        "content": content,
        "conversation_id": None,
        "voice_mode": voice_mode,
    }
    t0 = time.perf_counter()
    ttft: float | None = None
    stages: dict = {}
    while True:
        remaining = deadline_s - (time.perf_counter() - t0)
        if remaining <= 0:
            # Deadline hit: still report TTFT if we got one — a streamed first
            # token is real signal even when total generation ran past the wall.
            return (ttft if ttft is not None else -3.0), -3.0, {"deadline_exceeded_s": deadline_s}
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        if etype == "chat.token" and event.get("message_id") == message_id and ttft is None:
            ttft = (time.perf_counter() - t0) * 1000
        elif etype == "chat.debug" and event.get("message_id") == message_id:
            stages = {k: v for k, v in event.items() if k.endswith("_ms")}
        elif etype == "chat.done" and event.get("message_id") == message_id:
            total = (time.perf_counter() - t0) * 1000
            return ttft if ttft is not None else -1.0, total, stages
        elif etype == "chat.error":
            # Errors MUST surface — a server-side rejection is not silence.
            if event.get("message_id") in (None, message_id):
                print(f"    !! chat.error: {event}", flush=True)
                if event.get("message_id") == message_id:
                    return -2.0, (time.perf_counter() - t0) * 1000, stages
        elif debug:
            print(f"    .. {etype}: {str(raw)[:100]}", flush=True)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--debug", action="store_true", help="print every non-matching frame")
    args = ap.parse_args()

    token = _device_token()
    uri = f"ws://127.0.0.1:{args.port}/api/v1/ws?token={token}"
    print(f"target: {uri.split('?')[0]}  runs={args.runs}")

    async with websockets.connect(uri, max_size=2**24) as ws:
        # Warmup: load the model into RAM so steady-state numbers are honest.
        # RETRIES until the path actually completes — a cold-start message can
        # hang/die while provider init races it (known baseline defect); we must
        # not let that poison or silently skip the measurement protocol.
        for attempt in range(max(args.warmup, 3)):
            try:
                await run_one(ws, SCENARIOS["simple"], debug=args.debug)
                print("    warmup complete", flush=True)
                break
            except Exception as exc:
                print(f"    !! warmup attempt {attempt + 1} failed: {type(exc).__name__}: {exc}", flush=True)

        results: dict[str, list[tuple[float, float]]] = {}
        for name, content in SCENARIOS.items():
            voice = name.startswith("voice")
            rows: list[tuple[float, float]] = []
            for i in range(args.runs):
                t_start = time.perf_counter()
                try:
                    rows.append(await run_one(ws, content, voice_mode=voice, debug=args.debug))
                except asyncio.TimeoutError:
                    print("    !! recv timeout — no completion frame", flush=True)
                    rows.append((-3.0, -3.0, {}))
                tt, tot, stages = rows[-1]
                stage_str = " ".join(f"{k.removesuffix('_ms')}={v:.0f}" for k, v in sorted(stages.items())) if stages else ""
                print(
                    f"  [{name} {i + 1}/{args.runs}] ttft={tt:.0f}ms total={tot:.0f}ms "
                    f"(wall {time.perf_counter() - t_start:.1f}s) {stage_str}",
                    flush=True,
                )
                await asyncio.sleep(0.2)
            results[name] = rows

    print("\n== results (ms, monotonic) ==")
    print(f"{'scenario':<14}{'ttft median':>12}{'ttft p95':>10}{'total median':>14}{'total p95':>11}   samples")
    for name, rows in results.items():
        ttfts = sorted(r[0] for r in rows if r[0] > 0)
        totals = sorted(r[1] for r in rows if r[1] > 0)
        ttft_med = statistics.median(ttfts) if ttfts else float("nan")
        ttft_p95 = ttfts[int(0.95 * (len(ttfts) - 1))] if ttfts else float("nan")
        total_med = statistics.median(totals) if totals else float("nan")
        total_p95 = totals[int(0.95 * (len(totals) - 1))] if totals else float("nan")
        samples = " ".join(f"{r[0]:.0f}/{r[1]:.0f}" for r in rows)
        print(f"{name:<14}{ttft_med:>12.1f}{ttft_p95:>10.1f}{total_med:>14.1f}{total_p95:>11.1f}   {samples}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
