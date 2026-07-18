import asyncio
import pytest

from dash_backend.executive.planner import Planner


@pytest.mark.asyncio
async def test_planner_decompose_fallback():
    # When no LLM is configured or call fails, planner should return at least one item
    items = await Planner.decompose("Test Goal", "Do A. Do B.")
    assert isinstance(items, list)
    assert len(items) >= 1
    assert "name" in items[0]


@pytest.mark.asyncio
async def test_planner_decompose_parsing():
    # Basic JSON parsing: simulate by calling planner with a description that is a JSON array
    json_desc = "[ {\"name\": \"Task 1\", \"description\": \"First\"}, {\"name\": \"Task 2\", \"description\": \"Second\"} ]"
    items = await Planner.decompose("Goal", json_desc)
    assert isinstance(items, list)
    assert items[0]["name"] == "Task 1"
