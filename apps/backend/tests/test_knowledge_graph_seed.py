"""Knowledge graph seeding: entities/edges extracted from memories.

The desktop Knowledge page renders /enhanced/knowledge-graph as an
interactive node graph; entities must come from stored memories
(build_graph_from_memories) and persist across engine restarts so the
graph survives backend restarts.
"""

from __future__ import annotations

import os

import pytest

from dash_backend.services.knowledge_graph import KnowledgeGraph


@pytest.fixture()
def kg(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_KG_STATE", str(tmp_path / "kg_state.json"))
    return KnowledgeGraph()


def test_rebuild_extracts_entities_and_links(kg):
    result = kg.build_graph_from_memories(
        [
            {
                "title": "Stack decision",
                "content": "DASH uses Python FastAPI with PostgreSQL for storage.",
                "tags": ["architecture"],
                "type": "decision",
            },
            {
                "title": "Meeting notes",
                "content": "PostgreSQL migration planned with the backend team.",
                "tags": ["meeting"],
                "type": "experience",
            },
        ]
    )
    assert result["ok"] is True
    assert result["memories_scanned"] == 2
    assert result["entities_extracted"] > 0
    names = {n["name"] for n in kg._nodes.values()}
    assert "PostgreSQL" in names
    # PostgreSQL mentioned in both memories -> tag + concept links exist
    assert result["edges_created"] > 0
    # Tag nodes created from memory tags
    assert "tag_architecture" in kg._nodes


def test_rebuild_is_idempotent_on_mentions(kg):
    mem = [{"title": "t", "content": "Docker and Kubernetes deployed", "tags": [], "type": "knowledge"}]
    kg.build_graph_from_memories(mem)
    before = len(kg._nodes)
    kg.build_graph_from_memories(mem)
    assert len(kg._nodes) == before  # no duplicate nodes
    # co-mention edges not duplicated
    docker_k8s = sum(
        1
        for e in kg._edges
        if {e["source"], e["target"]} == {"ent_docker", "ent_kubernetes"}
    )
    assert docker_k8s == 1


def test_graph_persists_across_restart(kg, tmp_path):
    kg.build_graph_from_memories(
        [{"title": "t", "content": "Rust rewrite proposal", "tags": ["perf"], "type": "idea"}]
    )
    # New instance = simulated restart, same state file
    kg2 = KnowledgeGraph()
    assert len(kg2._nodes) == len(kg._nodes)
    assert len(kg2._edges) == len(kg._edges)
    assert "ent_rust" in kg2._nodes


def test_clear_persists_empty_state(kg):
    kg.build_graph_from_memories(
        [{"title": "t", "content": "Redis cache layer", "tags": [], "type": "knowledge"}]
    )
    assert len(kg._nodes) > 0
    kg.clear()
    kg2 = KnowledgeGraph()
    assert len(kg2._nodes) == 0
