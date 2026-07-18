"""Repo-level pytest configuration.

This project uses async pytest fixtures (pytest-asyncio).
Some environments may not register the asyncio plugin early enough
for all subpackages, so we ensure it's registered here.
"""

from __future__ import annotations

import pytest_asyncio


def pytest_configure(config):
    try:
        config.pluginmanager.register(pytest_asyncio.plugin, "pytest_asyncio")
    except Exception:
        pass

