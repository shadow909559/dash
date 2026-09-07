#!/usr/bin/env python3
"""
DASH Performance Benchmark — Phase 12

Measures key performance metrics before and after optimizations.

Usage:
    python -m dash_backend.benchmark_performance

Output:
    console report + optional JSON export to benchmark_results.json
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.system import SystemMonitor

logger = get_logger(__name__)


async def _measure_collection_time(
    monitor: SystemMonitor,
    iterations: int = 10,
) -> dict[str, float]:
    """Measure snapshot collection latency over N iterations."""
    latencies: list[float] = []
    sizes: list[int] = []
    delta_sizes: list[int] = []

    # Warmup
    await monitor.collect()

    for i in range(iterations):
        start = time.perf_counter()
        snapshot = await monitor.collect()
        elapsed = (time.perf_counter() - start) * 1000  # ms
        latencies.append(elapsed)

        import json as json_mod
        payload = json_mod.dumps(snapshot, default=str)
        sizes.append(len(payload))

        # Measure delta size after first full snapshot
        if i > 0:
            delta = await monitor.get_delta_snapshot()
            delta_payload = json_mod.dumps(delta, default=str)
            delta_sizes.append(len(delta_payload))

    return {
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
        "min_latency_ms": round(min(latencies), 2),
        "max_latency_ms": round(max(latencies), 2),
        "iterations": iterations,
        "avg_payload_bytes": round(sum(sizes) / len(sizes), 0) if sizes else 0,
        "avg_delta_bytes": round(sum(delta_sizes) / len(delta_sizes), 0) if delta_sizes else 0,
        "delta_reduction_pct": round(
            (1 - (sum(delta_sizes) / len(delta_sizes)) / (sum(sizes) / len(sizes))) * 100,
            1,
        )
        if delta_sizes and sizes
        else 0.0,
    }


async def _measure_memory() -> dict[str, Any]:
    """Measure Python process memory usage."""
    import os
    import psutil

    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return {
        "rss_mb": round(mem_info.rss / (1024 * 1024), 1),
        "vms_mb": round(mem_info.vms / (1024 * 1024), 1),
        "cpu_percent": process.cpu_percent(interval=0.5),
    }


async def _measure_ws_compression(payload_size: int = 10000) -> dict[str, Any]:
    """Measure WebSocket compression effectiveness."""
    import zlib
    import base64

    # Generate sample payload
    sample = json.dumps({
        "type": "system",
        "data": {
            "cpu": {"percentage": 45.2, "cores_physical": 8, "cores_logical": 16},
            "ram": {"percent": 62.1, "total_gb": 31.9, "used_gb": 19.8},
            "gpu": [{"name": "NVIDIA RTX 3060", "usage_percent": 23.0}],
            "storage": {"total_gb": 475, "used_gb": 320},
            "network": {"download_speed_mbps": 450.5, "upload_speed_mbps": 22.3},
        },
        "timestamp": time.time(),
    })
    sample = sample * max(1, payload_size // len(sample))

    raw_bytes = sample.encode("utf-8")
    compressed = zlib.compress(raw_bytes, level=6)
    b64_compressed = base64.b64encode(compressed).decode("ascii")

    return {
        "raw_bytes": len(raw_bytes),
        "compressed_bytes": len(compressed),
        "b64_compressed_bytes": len(b64_compressed),
        "compression_ratio": round(len(raw_bytes) / max(1, len(compressed)), 2),
        "savings_pct": round((1 - len(compressed) / len(raw_bytes)) * 100, 1),
    }


async def run_benchmarks() -> dict[str, Any]:
    """Run all benchmarks and return results."""
    results: dict[str, Any] = {
        "timestamp": time.time(),
        "system": {},
    }

    # System info
    import platform
    results["system"] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
    }

    # Memory baseline
    logger.info("Measuring baseline memory...")
    results["memory"] = await _measure_memory()

    # Collection latency
    logger.info("Measuring collection latency (10 iterations)...")
    monitor = SystemMonitor()
    await monitor.start_background_collection()

    # Give background collection time to warm up
    await asyncio.sleep(2)

    # Get latest snapshot
    logger.info("Measuring get_latest_snapshot() latency...")
    start = time.perf_counter()
    for _ in range(10):
        await monitor.get_latest_snapshot()
    latest_avg_ms = (time.perf_counter() - start) / 10 * 1000

    # Full collect benchmark
    collect_results = await _measure_collection_time(monitor, iterations=10)
    results["collection"] = collect_results
    results["collection"]["latest_snapshot_avg_ms"] = round(latest_avg_ms, 2)

    # Delta compression effectiveness
    logger.info("Measuring delta compression...")
    results["delta"] = {
        "avg_payload_bytes": collect_results.get("avg_payload_bytes", 0),
        "avg_delta_bytes": collect_results.get("avg_delta_bytes", 0),
        "reduction_pct": collect_results.get("delta_reduction_pct", 0),
    }

    # WS compression
    logger.info("Measuring WebSocket compression...")
    results["compression"] = await _measure_ws_compression(50000)

    # Cache hit rate (simulate)
    logger.info("Measuring cache effectiveness...")
    cache_hits = 0
    cache_misses = 0
    start = time.time()
    while time.time() - start < 3:
        snap = await monitor.get_latest_snapshot()
        if snap:
            cache_hits += 1
        else:
            cache_misses += 1
        await asyncio.sleep(0.1)

    results["cache"] = {
        "calls_in_3s": cache_hits + cache_misses,
        "estimated_hit_rate_pct": round(cache_hits / (cache_hits + cache_misses) * 100, 1)
        if (cache_hits + cache_misses) > 0
        else 0,
    }

    # Memory after
    logger.info("Measuring memory after operations...")
    results["memory_after"] = await _measure_memory()

    # Summary
    total_time_pre = time.perf_counter()
    results["summary"] = {
        "collection_latency_ms": collect_results.get("avg_latency_ms", 0),
        "delta_reduction_pct": collect_results.get("delta_reduction_pct", 0),
        "compression_savings_pct": results["compression"]["savings_pct"],
        "memory_rss_mb": results["memory"].get("rss_mb", 0),
        "memory_after_mb": results["memory_after"].get("rss_mb", 0),
        "cache_hit_rate_pct": results["cache"]["estimated_hit_rate_pct"],
    }

    return results


def print_report(results: dict[str, Any]) -> None:
    """Print a formatted benchmark report."""
    print("=" * 70)
    print("  DASH Performance Benchmark Report — Phase 12")
    print("=" * 70)
    print(f"\n  System: {results['system']['platform']}")
    print(f"  Python: {results['system']['python']}")
    print(f"  Processor: {results['system']['processor']}")

    print(f"\n{'─' * 70}")
    print("  1. MEMORY USAGE")
    print(f"{'─' * 70}")
    mem = results.get("memory", {})
    mem2 = results.get("memory_after", {})
    print(f"     RSS Memory (before): {mem.get('rss_mb', '?')} MB")
    print(f"     RSS Memory (after):  {mem2.get('rss_mb', '?')} MB")

    print(f"\n{'─' * 70}")
    print("  2. SNAPSHOT COLLECTION LATENCY")
    print(f"{'─' * 70}")
    col = results.get("collection", {})
    print(f"     Average:   {col.get('avg_latency_ms', '?')} ms")
    print(f"     Min:       {col.get('min_latency_ms', '?')} ms")
    print(f"     Max:       {col.get('max_latency_ms', '?')} ms")
    print(f"     Latest:    {col.get('latest_snapshot_avg_ms', '?')} ms (from cache)")

    print(f"\n{'─' * 70}")
    print("  3. DELTA OPTIMIZATION")
    print(f"{'─' * 70}")
    delta = results.get("delta", {})
    print(f"     Full payload:   {delta.get('avg_payload_bytes', '?')} bytes")
    print(f"     Delta payload:  {delta.get('avg_delta_bytes', '?')} bytes")
    print(f"     Reduction:      {delta.get('reduction_pct', '?')}%")

    print(f"\n{'─' * 70}")
    print("  4. WEBSOCKET COMPRESSION (zlib)")
    print(f"{'─' * 70}")
    comp = results.get("compression", {})
    print(f"     Raw:           {comp.get('raw_bytes', '?')} bytes")
    print(f"     Compressed:    {comp.get('compressed_bytes', '?')} bytes")
    print(f"     Ratio:         {comp.get('compression_ratio', '?')}x")
    print(f"     Savings:       {comp.get('savings_pct', '?')}%")

    print(f"\n{'─' * 70}")
    print("  5. CACHE PERFORMANCE")
    print(f"{'─' * 70}")
    cache = results.get("cache", {})
    print(f"     Calls in 3s:  {cache.get('calls_in_3s', '?')}")
    print(f"     Hit rate:     {cache.get('estimated_hit_rate_pct', '?')}%")

    print(f"\n{'─' * 70}")
    print("  SUMMARY")
    print(f"{'─' * 70}")
    summary = results.get("summary", {})
    print(f"     Collection latency:    {summary.get('collection_latency_ms', '?')} ms")
    print(f"     Delta reduction:       {summary.get('delta_reduction_pct', '?')}%")
    print(f"     Compression savings:   {summary.get('compression_savings_pct', '?')}%")
    print(f"     Memory (RSS):          {summary.get('memory_rss_mb', '?')} MB")
    print(f"     Cache hit rate:        {summary.get('cache_hit_rate_pct', '?')}%")
    print("=" * 70)

    verdict = "PASS" if summary.get("collection_latency_ms", 100) < 50 else "NEEDS_TUNING"
    print(f"\n  Verdict: {verdict}")
    print()


async def main() -> None:
    """Run benchmarks and print/save results."""
    results = await run_benchmarks()
    print_report(results)

    # Save to JSON
    output_path = "benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Results saved to: {output_path}")
    print()


if __name__ == "__main__":
    asyncio.run(main())

