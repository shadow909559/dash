"""Tests for the predictive device sampler (spec Part 8 integration).

Covers the lightweight background task that periodically records CPU / RAM /
disk samples so the predictive engine can build trend projections over time.
"""

from __future__ import annotations

import asyncio

import pytest

from dash_backend.predictive.history import SampleStore
from dash_backend.predictive.sampler import DeviceSampler, _collect_sample


# ── _collect_sample ────────────────────────────────────────────────


def test_collect_sample_returns_real_metrics():
    """The collector reads live psutil data on a real machine."""
    sample = _collect_sample()
    if sample is None:
        pytest.skip("psutil not installed")
    assert "ts" in sample
    assert isinstance(sample["ts"], float)
    assert "cpu_pct" in sample
    assert 0 <= sample["cpu_pct"] <= 100
    assert "ram_pct" in sample
    assert 0 <= sample["ram_pct"] <= 100


def test_collect_sample_has_disk_when_available():
    sample = _collect_sample()
    if sample is None:
        pytest.skip("psutil not installed")
    if "disk_pct" in sample:
        assert 0 <= sample["disk_pct"] <= 100
    if "disk_free_gb" in sample:
        assert sample["disk_free_gb"] >= 0


# ── DeviceSampler (unit tests with a temp store) ──────────────────


def test_sampler_tick_appends_sample(tmp_path):
    """A single tick writes exactly one sample to the store."""
    store = SampleStore(path=tmp_path / "sampler_test.json")
    sampler = DeviceSampler(interval_seconds=999, store=store)
    sampler._tick()
    samples = store.samples()
    assert len(samples) == 1
    assert "ts" in samples[0]


async def test_sampler_stop_breaks_loop(tmp_path):
    """Calling stop() exits the run loop promptly."""
    store = SampleStore(path=tmp_path / "sampler_stop.json")
    sampler = DeviceSampler(interval_seconds=300, store=store)
    task = asyncio.create_task(sampler.run())
    await asyncio.sleep(0.1)  # let the initial tick happen
    sampler.stop()
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.TimeoutError:
        pytest.fail("Sampler did not stop within 2 seconds")


async def test_sampler_accumulates_multiple_samples(tmp_path):
    """Multiple ticks produce multiple samples with increasing timestamps."""
    store = SampleStore(path=tmp_path / "sampler_multi.json")
    sampler = DeviceSampler(interval_seconds=0.1, store=store)

    task = asyncio.create_task(sampler.run())
    await asyncio.sleep(0.8)
    sampler.stop()
    await task

    samples = store.samples()
    # Initial tick + at least several interval ticks in 0.8s at 0.1s intervals
    assert len(samples) >= 3, f"Expected >= 3 samples, got {len(samples)}"
    timestamps = [s["ts"] for s in samples]
    assert timestamps == sorted(timestamps)  # monotonically increasing


async def test_sampler_stops_without_leaving_task_running(tmp_path):
    """After stop + await, the sampler task is fully done."""
    store = SampleStore(path=tmp_path / "sampler_clean.json")
    sampler = DeviceSampler(interval_seconds=300, store=store)
    task = asyncio.create_task(sampler.run())
    await asyncio.sleep(0.1)
    sampler.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()


# ── Integration: sampler feeds predictive engine ──────────────────


async def test_sampler_provides_history_for_predictions(tmp_path):
    """After several samples, the predictive engine can read them."""
    store = SampleStore(path=tmp_path / "sampler_integration.json")
    sampler = DeviceSampler(interval_seconds=0.05, store=store)

    task = asyncio.create_task(sampler.run())
    await asyncio.sleep(0.5)
    sampler.stop()
    await task

    samples = store.samples()
    # _collect_sample blocks ~0.1s (psutil), so effective cycle ~0.15s;
    # 0.5s window yields ~3-4 ticks + 1 initial.
    assert len(samples) >= 3
    # The predictive predictors should run without error on real data
    from dash_backend.predictive.predictors import predict_disk_fill, predict_ram_exhaustion

    ram_pred = predict_ram_exhaustion(samples)
    disk_pred = predict_disk_fill(samples)
    assert ram_pred is None or ram_pred.likelihood >= 0
    assert disk_pred is None or disk_pred.likelihood >= 0
