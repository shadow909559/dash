"""Pins for the CI test sharding (decisions.md #139).

The shard filter is what keeps CI coverage honest: the union of shards
must equal the whole suite, shards must be deterministic (a retry of one
shard runs the same tests), and a misconfigured shard must fail loudly
instead of reporting a vacuous green job. These tests pin all of that —
including a real pytest subprocess running under ``DASH_TEST_SHARD``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests._sharding import (
    SHARD_ENV_VARS,
    active_shard,
    item_shard,
    parse_shard_spec,
    should_run,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent


# ── spec parsing ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("0/6", (0, 6)),
        ("5/6", (5, 6)),
        ("1/2", (1, 2)),
        (" 1/4 ", (1, 4)),  # surrounding whitespace tolerated
    ],
)
def test_parse_shard_spec_valid(spec: str, expected: tuple[int, int]) -> None:
    assert parse_shard_spec(spec) == expected


@pytest.mark.parametrize(
    "spec",
    [
        "",
        None,
        "6/6",  # index == total → out of range
        "7/6",
        "-1/6",
        "abc/6",
        "2",
        "2/",
        "/6",
        "2/0",  # total 0 → division domain
        "2/-3",
        "1.5/6",
        "0/6 extra",
    ],
)
def test_parse_shard_spec_invalid_runs_full_suite(spec: str | None) -> None:
    assert parse_shard_spec(spec) is None


def test_active_shard_reads_env_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in SHARD_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    assert active_shard() is None  # unset → full suite

    monkeypatch.setenv("DASH_SHARD", "1/3")
    assert active_shard() == (1, 3)

    monkeypatch.setenv("DASH_TEST_SHARD", "0/3")
    # First listed env var wins.
    assert active_shard() == (0, 3)

    # A malformed value in the first var is authoritative None (full
    # suite), NOT a silent fall-through to the second var.
    monkeypatch.setenv("DASH_TEST_SHARD", "bogus")
    assert active_shard() is None


# ── assignment core: stable, complete, disjoint, balanced ─────────────


def _all_nodeids() -> list[str]:
    """Representative node ids without booting the whole app: the two
    765-item parametrized sweeps (54% of the suite) plus unique single
    tests, which is exactly the distribution the balancer must survive."""
    ids: list[str] = []
    for i in range(765):
        ids.append(f"tests/test_api_sweep.py::test_wire_base_a[{i}]")
        ids.append(f"tests/test_api_sweep.py::test_wire_base_b[{i}]")
    for f in range(1, 100):
        ids.append(f"tests/test_module_{f}.py::test_case_{f}")
    return ids


def test_item_shard_is_stable() -> None:
    ids = _all_nodeids()
    first = [item_shard(n, 6) for n in ids]
    again = [item_shard(n, 6) for n in ids]
    assert first == again
    # Also stable under a different shard count (same function, no state).
    assert [item_shard(n, 4) for n in ids] == [item_shard(n, 4) for n in ids]


def test_shard_partition_complete_and_disjoint() -> None:
    ids = _all_nodeids()
    seen: dict[str, int] = {}
    for shard in range(6):
        for nodeid in ids:
            if should_run(nodeid, (shard, 6)):
                # Disjoint: no item may appear in two shards.
                assert nodeid not in seen, f"{nodeid} in shards {seen[nodeid]} and {shard}"
                seen[nodeid] = shard
    # Complete: every item ran in exactly one shard.
    assert set(seen) == set(ids)


def test_shard_partition_is_reasonably_balanced() -> None:
    ids = _all_nodeids()
    counts = [sum(1 for n in ids if should_run(n, (s, 6))) for s in range(6)]
    total = len(ids)
    # Hash assignment on a mostly-parametrized population: every shard
    # must get its share within a generous tolerance (guaranteed for
    # n≥6 by the pigeonhole bound on ball-into-bins discrepancy).
    for count in counts:
        assert abs(count - total / 6) <= total * 0.05, counts


def test_item_shard_matches_should_run() -> None:
    nodeid = "tests/test_api_sweep.py::test_wire_base_a[123]"
    assert should_run(nodeid, (item_shard(nodeid, 6), 6))


# ── integration: a real pytest subprocess honors the env var ──────────


def test_subprocess_shard_filter(tmp_path: Path) -> None:
    """End-to-end: pytest under DASH_TEST_SHARD runs exactly the
    hash-selected subset of the probe file's real collection."""
    probe = Path(__file__).parent / "_shard_probe.py"
    probe_ids = f"tests/{probe.name}"
    collected_ids = [
        f"{probe_ids}::test_probe_word[{w}]"
        for w in ("alpha", "beta", "gamma", "delta", "omega", "zeta")
    ] + [f"{probe_ids}::test_probe_plain"]
    # Pick the smallest shard count whose every shard is provably
    # non-empty for these ids — an empty shard would make the pin vacuous
    # (nothing asserts anything) and an all-but-one-shard hash is a real
    # possibility for a 7-item population.
    total = next(
        n
        for n in (2, 3, 4, 5)
        if all(any(should_run(nid, (s, n)) for nid in collected_ids) for s in range(n))
    )
    for var in SHARD_ENV_VARS:
        os.environ.pop(var, None)
    try:
        for shard in range(total):
            expected = sorted(
                nid for nid in collected_ids if should_run(nid, (shard, total))
            )
            assert expected, "empty expected shard would make this pin vacuous"
            env = dict(os.environ, DASH_TEST_SHARD=f"{shard}/{total}")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(probe),
                    "-v",
                    "--no-header",
                    "-p",
                    "no:cacheprovider",
                ],
                cwd=BACKEND_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert proc.returncode == 0, proc.stdout + proc.stderr
            for nid in collected_ids:
                ran = f"{nid} PASSED" in proc.stdout
                if nid in expected:
                    assert ran, f"{nid} should run in shard {shard}:\n{proc.stdout}"
                else:
                    assert not ran, (
                        f"{nid} must NOT run in shard {shard}:\n{proc.stdout}"
                    )
    finally:
        for var in SHARD_ENV_VARS:
            os.environ.pop(var, None)


def test_subprocess_out_of_range_env_runs_full_suite(tmp_path: Path) -> None:
    """Env form is tolerant: an out-of-range spec degrades to the FULL
    suite (complete coverage, longer run) — never to dropped tests."""
    probe = Path(__file__).parent / "_shard_probe.py"
    env = dict(os.environ, DASH_TEST_SHARD="6/3")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(probe),
            "-v",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    # All 7 probe tests ran (full suite, not a shard).
    for w in ("alpha", "beta", "gamma", "delta", "omega", "zeta"):
        assert f"test_probe_word[{w}] PASSED" in proc.stdout
    assert "test_probe_plain PASSED" in proc.stdout


def test_subprocess_out_of_range_cli_fails_loudly(tmp_path: Path) -> None:
    """CLI form is strict: an explicit --shard=6/3 is deliberate intent,
    so it must abort collection instead of guessing."""
    probe = Path(__file__).parent / "_shard_probe.py"
    for var in SHARD_ENV_VARS:
        os.environ.pop(var, None)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(probe),
            "--shard=6/3",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "not a valid I/N spec" in combined


def test_subprocess_empty_shard_fails_loudly(tmp_path: Path) -> None:
    """A valid spec selecting 0 tests must refuse to report green."""
    probe = Path(__file__).parent / "_shard_probe.py"
    # Find a total so large that shard 0 is provably empty for this file.
    total = 2
    from tests._sharding import item_shard as _is

    while True:
        nodeids = [f"tests/{probe.name}::test_probe_word[{w}]" for w in
                   ("alpha", "beta", "gamma", "delta", "omega", "zeta")]
        nodeids.append(f"tests/{probe.name}::test_probe_plain")
        if all(_is(nid, total) != 0 for nid in nodeids):
            break
        total *= 2
    for var in SHARD_ENV_VARS:
        os.environ.pop(var, None)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(probe),
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_ROOT,
        env=dict(os.environ, DASH_TEST_SHARD=f"0/{total}"),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "selected 0 tests" in combined
