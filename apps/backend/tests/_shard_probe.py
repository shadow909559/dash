"""Trivial probe tests for the sharding subprocess pins (test_sharding.py).

The leading-underscore filename deliberately does NOT match pytest's
default ``test_*.py`` collection pattern, so this file is never part of
the production shard — it exists only so the integration pin can launch a
real pytest subprocess with ``DASH_TEST_SHARD`` set and verify the filter
selects exactly the hash-predicted subset of a *real* collection.
"""

import pytest


@pytest.mark.parametrize("word", ["alpha", "beta", "gamma", "delta", "omega", "zeta"])
def test_probe_word(word: str) -> None:
    assert word.isalpha()


def test_probe_plain() -> None:
    assert True
