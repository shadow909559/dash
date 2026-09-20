"""Minimal timed chat probe: N identical messages through the REAL WS path.

Used for the controlled before/after latency comparison (decisions.md #89)
when the full benchmark matrix is impractical (co-tenant Ollama contention
makes baseline generations run for minutes). Prints exact monotonic ms per
message: ttft_ms (first chat.token) and total_ms (chat.done).

Usage:
    python scripts/probe_chat_once.py --port 8017 --messages 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import websockets  # type: ignore[import-untyped]


def _device_token() -> str:
    from dash_backend.security.local_identity import get_identity

    return get_identity().device_token


PROMPT = "What is 2+2? Answer in one short sentence."


async def probe_once(ws, deadline_s: float = 240.0) -> tuple[float, float]:
    message_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    ttft: float | None = None
    await ws.send(
        json.dumps(
            {
                "type": "chat.send",
                "message_id": message_id,
                "content": PROMPT,
                "conversation_id": None,
                "voice_mode": False,
            }
        )
    )
    while True:
        remaining = deadline_s - (time.perf_counter() - t0)
        if remaining <= 0:
            return (ttft if ttft is not None else -3.0), -3.0
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        if etype == "chat.token" and event.get("message_id") == message_id and ttft is None:
            ttft = (time.perf_counter() - t0) * 1000
        elif etype == "chat.done" and event.get("message_id") == message_id:
            return (ttft if ttft is not None else -1.0), (time.perf_counter() - t0) * 1000
        elif etype == "chat.error" and event.get("message_id") in (None, message_id):
            print(f"    !! chat.error: {event}", flush=True)
            return -2.0, -2.0


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--messages", type=int, default=2)
    ap.add_argument("--deadline", type=float, default=240.0)
    args = ap.parse_args()

    uri = f"ws://127.0.0.1:{args.port}/api/v1/ws?token={_device_token()}"
    print(f"target: {uri.split('?')[0]}  messages={args.messages}", flush=True)
    rows: list[tuple[float, float]] = []
    async with websockets.connect(uri, max_size=2**24) as ws:
        for i in range(args.messages):
            t_start = time.perf_counter()
            try:
                ttft, total = await probe_once(ws, deadline_s=args.deadline)
            except asyncio.TimeoutError:
                print(f"  [{i + 1}] recv timeout — no completion frame", flush=True)
                ttft, total = -3.0, -3.0
            print(
                f"  [{i + 1}/{args.messages}] ttft={ttft:.0f}ms total={total:.0f}ms "
                f"(wall {time.perf_counter() - t_start:.1f}s)",
                flush=True,
            )
            rows.append((ttft, total))
            await asyncio.sleep(0.2)

    good_ttft = sorted(r[0] for r in rows if r[0] > 0)
    good_total = sorted(r[1] for r in rows if r[1] > 0)
    if good_ttft:
        print(f"ttft median: {good_ttft[len(good_ttft) // 2]:.0f}ms  samples={good_ttft}", flush=True)
    else:
        print("ttft: no successful completions", flush=True)
    if good_total:
        print(f"total median: {good_total[len(good_total) // 2]:.0f}ms  samples={good_total}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
