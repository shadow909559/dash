"""Performance profiling script for DASH backend.

Profiles:
- Memory retrieval
- Planner
- Embeddings
- RAG
- WebSocket
- Startup
"""

import asyncio
import time
import uuid
from typing import Dict, List
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.session import AsyncSessionLocal
from dash_backend.memory.service import build_memory_context, search_memories, save_memory
from dash_backend.executive.planner import Planner
from dash_backend.rag.service import search_documents, create_document
from dash_backend.rag.embeddings import create_embedding


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    duration_ms: float
    iterations: int
    avg_ms: float
    min_ms: float
    max_ms: float


class Profiler:
    """Performance profiler for DASH components."""
    
    def __init__(self):
        self.results: List[BenchmarkResult] = []
    
    async def benchmark(self, name: str, func, iterations: int = 5) -> BenchmarkResult:
        """Run a function multiple times and collect timing statistics."""
        durations = []
        
        for _ in range(iterations):
            start = time.perf_counter()
            await func()
            duration = (time.perf_counter() - start) * 1000  # Convert to ms
            durations.append(duration)
        
        result = BenchmarkResult(
            name=name,
            duration_ms=sum(durations),
            iterations=iterations,
            avg_ms=sum(durations) / len(durations),
            min_ms=min(durations),
            max_ms=max(durations),
        )
        self.results.append(result)
        return result
    
    def print_results(self):
        """Print benchmark results."""
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)
        
        for result in self.results:
            print(f"\n{result.name}:")
            print(f"  Total: {result.duration_ms:.2f}ms")
            print(f"  Avg:   {result.avg_ms:.2f}ms")
            print(f"  Min:   {result.min_ms:.2f}ms")
            print(f"  Max:   {result.max_ms:.2f}ms")
            print(f"  Iters: {result.iterations}")
        
        print("\n" + "=" * 80)


async def profile_memory_retrieval(profiler: Profiler, user_id: uuid.UUID):
    """Profile memory retrieval performance."""
    print("\n[Profiling Memory Retrieval]")
    print("  Skipping database-dependent profiling (schema mismatch)")
    print("  Will profile after schema fix")


async def profile_planner(profiler: Profiler):
    """Profile planner performance."""
    print("\n[Profiling Planner]")
    
    async def decompose():
        await Planner.decompose(
            goal_name="Build a web application",
            goal_description="Create a full-stack web app with authentication",
            max_tasks=5,
        )
    
    result = await profiler.benchmark("Planner Decompose", decompose, iterations=5)
    print(f"  Planner decompose: {result.avg_ms:.2f}ms avg")


async def profile_embeddings(profiler: Profiler):
    """Profile embedding generation performance."""
    print("\n[Profiling Embeddings]")
    
    test_texts = [
        "The quick brown fox jumps over the lazy dog",
        "Machine learning is a subset of artificial intelligence",
        "Python is a popular programming language",
        "Databases store and retrieve data efficiently",
        "Web applications run in browsers",
    ]
    
    async def single_embedding():
        await create_embedding(test_texts[0])
    
    result = await profiler.benchmark("Single Embedding", single_embedding, iterations=10)
    print(f"  Single embedding: {result.avg_ms:.2f}ms avg")
    
    async def batch_embeddings():
        tasks = [create_embedding(text) for text in test_texts]
        await asyncio.gather(*tasks)
    
    result = await profiler.benchmark("Batch Embeddings (5)", batch_embeddings, iterations=5)
    print(f"  Batch embeddings (5): {result.avg_ms:.2f}ms avg")


async def profile_rag(profiler: Profiler, user_id: uuid.UUID):
    """Profile RAG performance."""
    print("\n[Profiling RAG]")
    print("  Skipping database-dependent profiling (schema mismatch)")
    print("  Will profile after schema fix")


async def profile_startup():
    """Profile backend startup time."""
    print("\n[Profiling Startup]")
    
    start = time.perf_counter()
    
    # Import main module (simulates startup)
    from dash_backend.main import app
    
    duration = (time.perf_counter() - start) * 1000
    print(f"  Startup time: {duration:.2f}ms")
    
    return duration


async def main():
    """Run all performance profiles."""
    print("=" * 80)
    print("DASH PERFORMANCE PROFILING")
    print("=" * 80)
    
    profiler = Profiler()
    test_user_id = uuid.uuid4()
    
    # Profile startup
    await profile_startup()
    
    # Profile memory retrieval
    await profile_memory_retrieval(profiler, test_user_id)
    
    # Profile planner
    await profile_planner(profiler)
    
    # Profile embeddings
    await profile_embeddings(profiler)
    
    # Profile RAG
    await profile_rag(profiler, test_user_id)
    
    # Print results
    profiler.print_results()
    
    # Save results to file
    with open("benchmark_results.json", "w") as f:
        import json
        results_data = [
            {
                "name": r.name,
                "duration_ms": r.duration_ms,
                "iterations": r.iterations,
                "avg_ms": r.avg_ms,
                "min_ms": r.min_ms,
                "max_ms": r.max_ms,
            }
            for r in profiler.results
        ]
        json.dump(results_data, f, indent=2)
    
    print("\nResults saved to benchmark_results.json")


if __name__ == "__main__":
    asyncio.run(main())
