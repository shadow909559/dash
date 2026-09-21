"""Deterministic item-level test sharding (decisions.md #139).

CI's backend job takes ~13 min. Sharding cuts wall-clock by running N
pytest processes in parallel — but file-level sharding cannot balance this
suite: ``test_api_sweep.py`` alone holds 54% of all tests. So the shard
assignment happens at the *item* level, keyed on a **stable hash of the
node id**:

    shard(item) = blake2b(nodeid, digest_size=8) % total

Deterministic properties (each pinned by tests/test_sharding.py):

- **Stable** — the same node id maps to the same shard forever, so a
  retry/re-run of one shard on a different machine sees the same tests.
- **Complete + disjoint** — every item lands in exactly one shard; the
  union of shards equals the full suite, so coverage cannot silently
  shrink when CI changes shard count.
- **Balanced enough** — hash assignment spreads the two 765-item
  parametrized sweeps evenly instead of shipping them as one lump.

New tests need no manifest: they hash into shards automatically.

Env / CLI (CI uses the env var):

    DASH_TEST_SHARD="2/6" pytest tests        # env var form
    pytest tests --shard=2/6                  # CLI form

Semantics, chosen deliberately:

- **Env malformed/out-of-range → FULL suite.** Tolerant on purpose: a
  typo'd CI export degrades to longer-but-complete runs (and the shard
  banner + per-shard counts in the log make it obvious), never to
  silently dropped coverage.
- **CLI malformed/out-of-range → hard error.** An explicit ``--shard``
  argument is deliberate intent; silently ignoring it would mislead.
- **Valid spec selecting 0 tests → hard error.** A shard that runs
  nothing must never report green.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

_SHARD_RE = re.compile(r"^(\d+)/(\d+)$")

# Environment variables consulted for the shard spec, in order. A list (not
# one var) lets CI export one form while developers can locally override the
# other for a one-off run without editing the workflow.
SHARD_ENV_VARS = ("DASH_TEST_SHARD", "DASH_SHARD")


def parse_shard_spec(spec: str | None) -> tuple[int, int] | None:
    """Parse ``"i/n"`` into a validated 0-based ``(index, total)``.

    Returns None for anything that is not a well-formed, in-range spec —
    malformed or out-of-range input deliberately runs the FULL suite rather
    than silently dropping coverage.
    """
    if not spec:
        return None
    m = _SHARD_RE.match(spec.strip())
    if not m:
        return None
    index, total = int(m.group(1)), int(m.group(2))
    if total < 1 or not (0 <= index < total):
        return None
    return index, total


def active_shard() -> tuple[int, int] | None:
    """Current shard from the environment, or None to run everything."""
    for var in SHARD_ENV_VARS:
        raw = os.environ.get(var)
        if raw:
            return parse_shard_spec(raw)
    return None


def item_shard(nodeid: str, total: int) -> int:
    """Stable shard assignment for one test item.

    blake2b-128 of the *full* node id (``path::class::param``), read as a
    big-endian integer modulo ``total``. Deterministic across machines,
    Python versions and pytest invocations — the only input is the node id
    string itself, never collection order or set iteration order.
    """
    digest = hashlib.blake2b(nodeid.encode("utf-8"), digest_size=16).digest()
    return int.from_bytes(digest, "big") % total


def should_run(nodeid: str, shard: tuple[int, int]) -> bool:
    index, total = shard
    return item_shard(nodeid, total) == index


def describe(cli_spec: str | None = None) -> str:
    """Human-readable shard banner for the CI log."""
    shard = parse_shard_spec(cli_spec) or active_shard()
    if shard is None:
        return "FULL SUITE (no shard requested)"
    return f"{shard[0] + 1}/{shard[1]}"


__all__ = [
    "SHARD_ENV_VARS",
    "active_shard",
    "describe",
    "item_shard",
    "parse_shard_spec",
    "should_run",
]
