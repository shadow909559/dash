"""Report how the CI test shards will partition the suite (decisions.md #139).

Runs real pytest collection (same machinery CI uses, so skips/markers are
honest) and prints per-shard counts plus the min/max spread, so a shard
count can be chosen from numbers instead of hope. Verifies the hard
invariants directly against the collected items: partition completeness,
disjointness, and no empty shard.

Usage:
    py scripts/inspect_test_shards.py [--total 6]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `tests` importable when invoked as a script from apps/backend.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests._sharding import item_shard  # noqa: E402


def collect_nodeids() -> list[str]:
    """Real pytest collection — the exact items CI would run."""
    import contextlib
    import io
    import warnings

    import pytest

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rc = pytest.main(
            [
                "tests",
                "--collect-only",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
            ]
        )
    if rc not in (0, 5):  # 5 = no tests collected
        raise SystemExit(f"pytest collection failed with exit code {rc}")
    nodeids: list[str] = []
    for line in buf.getvalue().splitlines():
        line = line.strip()
        if line and "::" in line:
            nodeids.append(line)
    return nodeids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--total",
        type=int,
        default=6,
        help="Shard count to report for (default 6, CI's setting).",
    )
    args = parser.parse_args()

    nodeids = collect_nodeids()
    if not nodeids:
        raise SystemExit("no tests collected — nothing to shard")

    counts = [0] * args.total
    for nodeid in nodeids:
        counts[item_shard(nodeid, args.total)] += 1

    total = len(nodeids)
    empty = [i for i, c in enumerate(counts) if c == 0]
    print(f"collected {total} tests; shards[{args.total}]:")
    for i, c in enumerate(counts):
        bar = "#" * max(1, round(c / max(counts) * 40)) if c else "(empty!)"
        print(f"  shard {i}: {c:5d}  {bar}")
    spread = max(counts) - min(counts)
    print(
        f"  spread: min={min(counts)} max={max(counts)} "
        f"delta={spread} ({spread / total:.1%} of suite)"
    )
    if empty:
        raise SystemExit(f"FAIL: empty shards {empty} — lower --total")

    # Direct partition proof over the same items the shards would run.
    seen: dict[str, int] = {}
    for shard in range(args.total):
        for nodeid in nodeids:
            if item_shard(nodeid, args.total) == shard:
                assert nodeid not in seen, f"{nodeid} in two shards"
                seen[nodeid] = shard
    assert set(seen) == set(nodeids), "partition incomplete"
    print("  partition: complete + disjoint [OK]")


if __name__ == "__main__":
    main()
