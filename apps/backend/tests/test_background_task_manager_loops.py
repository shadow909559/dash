"""BackgroundTaskManager loop-parity regressions (CI run 35547162155).

The singleton BackgroundTaskManager is reused across ASGI lifespans — tests
boot several apps in one process, each on its own event loop. Three defects
combined to hang ubuntu CI inside ``TestClient.wait_startup``:

1. the worker's asyncio.Queue was created in ``__init__`` and stayed bound to
   the first loop; every later ``start()`` raised "bound to a different event
   loop" inside the worker;
2. the worker's generic except path had no sleep — a hot loop that starved
   the portal loop so startup futures never ran (2.5M "Worker error" log
   lines in the CI faulthandler dump);
3. ``stop()`` was never called from app shutdown and, once called, was
   unbounded.

These tests pin the honest semantics: reuse across sequential loops works,
an erroring worker keeps yielding, and shutdown completes even with a task
simulating a hung coroutine.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from dash_backend.autonomous.background_task_manager import (
    BackgroundTaskManager,
    get_background_task_manager,
)


@pytest.mark.asyncio
async def test_reuse_across_sequential_event_loops():
    """start() on a fresh loop after a previous lifespan must not raise the
    'bound to a different event loop' RuntimeError the CI hang came from."""
    mgr = BackgroundTaskManager()
    await mgr.start()
    await mgr.stop()

    # A brand-new loop (as each TestClient lifespan gets) must start cleanly.
    await mgr.start()
    got: list[str] = []

    async def work():
        got.append("ran")

    await mgr.submit("x", work())
    for _ in range(50):
        if got:
            break
        await asyncio.sleep(0.05)
    assert got == ["ran"], "task submitted on the second lifespan never ran"

    await mgr.stop()


@pytest.mark.asyncio
async def test_worker_error_path_yields_and_survives(caplog):
    """An erroring worker must yield (bounded error rate) and recover."""
    import logging

    from dash_backend.autonomous import background_task_manager as btm_mod

    mgr = BackgroundTaskManager()
    await mgr.start()
    try:
        done: list[str] = []

        async def good():
            done.append("ok")

        await mgr.submit("good", good())
        for _ in range(40):
            if done:
                break
            await asyncio.sleep(0.05)
        assert done == ["ok"], "healthy path never ran the submitted task"

        # Corrupt internal state to force the worker's generic except path
        # (same class of failure as the loop-bound-queue bug), then count
        # error records over a window: with no sleep this path hot-loops
        # (thousands of records/sec, as in the CI faulthandler dump).
        with caplog.at_level(logging.ERROR, logger=btm_mod.logger.name):
            caplog.clear()
            mgr._queue = None
            await asyncio.sleep(1.3)
            errors = [r for r in caplog.records if "Worker error" in r.getMessage()]
            assert 0 < len(errors) <= 5, (
                f"error path yielded {len(errors)} times in 1.3s — "
                "unbounded without the sleep, dead if it never fired"
            )

        # Repair (what a later start() does) and prove recovery.
        mgr._queue = asyncio.Queue()
        done2: list[str] = []

        async def good2():
            done2.append("recovered")

        await mgr.submit("good2", good2())
        for _ in range(60):
            if done2:
                break
            await asyncio.sleep(0.05)
        assert done2 == ["recovered"], "worker never recovered after an internal error"
    finally:
        await mgr.stop()


@pytest.mark.asyncio
async def test_stop_is_bounded_with_hung_task():
    """stop() must complete even when a running task hangs forever."""
    mgr = BackgroundTaskManager()
    await mgr.start()
    try:
        started = asyncio.Event()

        async def hang():
            started.set()
            await asyncio.sleep(3600)

        await mgr.submit("hang", hang())
        for _ in range(40):
            if started.is_set():
                break
            await asyncio.sleep(0.05)
        assert started.is_set()

        t0 = time.monotonic()
        await asyncio.wait_for(mgr.stop(timeout=0.5), timeout=5.0)
        assert time.monotonic() - t0 < 4.0, "stop() hung on a stuck task"
    finally:
        # Idempotent safety; if the assertions passed this is a no-op.
        try:
            await asyncio.wait_for(mgr.stop(), timeout=2.0)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_singleton_exists_for_lifespan_wiring():
    """Lifespan uses the singleton; ensure the accessor keeps working."""
    assert get_background_task_manager() is get_background_task_manager()
