"""Enhanced memory: fuzzy search, tagging, relationships, analytics, consolidation, forgetting curve."""
from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MemoryTagManager:
    """Tag system for organizing memories."""

    def __init__(self) -> None:
        self._tags: dict[str, dict[str, Any]] = {}  # tag_name -> metadata
        self._memory_tags: dict[str, list[str]] = {}  # memory_id -> [tag_names]

    def create_tag(self, name: str, color: str = "#22c55e", description: str = "") -> dict:
        name_lower = name.lower().strip()
        if not name_lower:
            return {"ok": False, "reason": "Tag name cannot be empty"}
        self._tags[name_lower] = {"name": name_lower, "color": color, "description": description, "created_at": datetime.now(timezone.utc).isoformat()}
        return {"ok": True, "tag": self._tags[name_lower]}

    def delete_tag(self, name: str) -> dict:
        name_lower = name.lower().strip()
        if name_lower in self._tags:
            del self._tags[name_lower]
            for mem_id in list(self._memory_tags.keys()):
                self._memory_tags[mem_id] = [t for t in self._memory_tags[mem_id] if t != name_lower]
            return {"ok": True}
        return {"ok": False, "reason": "Tag not found"}

    def tag_memory(self, memory_id: str, tag_names: list[str]) -> dict:
        existing = set(self._memory_tags.get(memory_id, []))
        for name in tag_names:
            name_lower = name.lower().strip()
            if name_lower not in self._tags:
                self.create_tag(name_lower)
            existing.add(name_lower)
        self._memory_tags[memory_id] = list(existing)
        return {"ok": True, "tags": self._memory_tags[memory_id]}

    def untag_memory(self, memory_id: str, tag_names: list[str]) -> dict:
        existing = set(self._memory_tags.get(memory_id, []))
        for name in tag_names:
            existing.discard(name.lower().strip())
        self._memory_tags[memory_id] = list(existing)
        return {"ok": True, "tags": self._memory_tags[memory_id]}

    def get_memory_tags(self, memory_id: str) -> list[str]:
        return self._memory_tags.get(memory_id, [])

    def get_memories_by_tag(self, tag_name: str) -> list[str]:
        tag_lower = tag_name.lower().strip()
        return [mid for mid, tags in self._memory_tags.items() if tag_lower in tags]

    def get_all_tags(self) -> list[dict]:
        result = []
        for name, meta in self._tags.items():
            count = len(self.get_memories_by_tag(name))
            result.append({**meta, "memory_count": count})
        return sorted(result, key=lambda x: x["memory_count"], reverse=True)

    def get_tag_cloud(self) -> list[dict]:
        tags = self.get_all_tags()
        if not tags:
            return []
        max_count = max(t["memory_count"] for t in tags) or 1
        for tag in tags:
            tag["weight"] = round(tag["memory_count"] / max_count, 2)
        return tags


class MemoryRelationshipManager:
    """Link related memories together."""

    RELATIONSHIP_TYPES = [
        "causes", "follows_from", "contradicts", "supports",
        "related_to", "part_of", "example_of", "opposite_of",
        "depends_on", "derived_from", "supersedes", "references",
    ]

    def __init__(self) -> None:
        self._relationships: list[dict] = []

    def add_relationship(self, source_id: str, target_id: str, rel_type: str, strength: float = 1.0) -> dict:
        if rel_type not in self.RELATIONSHIP_TYPES:
            return {"ok": False, "reason": f"Invalid type. Use one of: {self.RELATIONSHIP_TYPES}"}
        rel = {
            "source": source_id,
            "target": target_id,
            "type": rel_type,
            "strength": max(0.0, min(1.0, strength)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._relationships.append(rel)
        return {"ok": True, "relationship": rel}

    def remove_relationship(self, source_id: str, target_id: str, rel_type: Optional[str] = None) -> dict:
        before = len(self._relationships)
        self._relationships = [
            r for r in self._relationships
            if not (r["source"] == source_id and r["target"] == target_id and (rel_type is None or r["type"] == rel_type))
        ]
        removed = before - len(self._relationships)
        return {"ok": True, "removed": removed}

    def get_related(self, memory_id: str) -> list[dict]:
        related = [r for r in self._relationships if r["source"] == memory_id or r["target"] == memory_id]
        return sorted(related, key=lambda x: x["strength"], reverse=True)

    def get_contradictions(self) -> list[dict]:
        return [r for r in self._relationships if r["type"] == "contradicts"]

    def get_all(self) -> list[dict]:
        return list(self._relationships)

    def get_graph(self) -> dict:
        nodes = set()
        edges = []
        for r in self._relationships:
            nodes.add(r["source"])
            nodes.add(r["target"])
            edges.append({"from": r["source"], "to": r["target"], "type": r["type"], "strength": r["strength"]})
        return {"nodes": list(nodes), "edges": edges}


class MemoryAnalytics:
    """Analytics for memory usage and health."""

    def __init__(self) -> None:
        self._creation_times: dict[str, datetime] = {}
        self._access_counts: dict[str, int] = defaultdict(int)
        self._last_accessed: dict[str, datetime] = {}

    def record_creation(self, memory_id: str) -> None:
        self._creation_times[memory_id] = datetime.now(timezone.utc)

    def record_access(self, memory_id: str) -> None:
        self._access_counts[memory_id] += 1
        self._last_accessed[memory_id] = datetime.now(timezone.utc)

    def get_stats(self, memories: list[dict]) -> dict:
        total = len(memories)
        type_counts: dict[str, int] = defaultdict(int)
        importance_sum = 0.0
        for m in memories:
            type_counts[m.get("type", "unknown")] += 1
            importance_sum += m.get("importance", 0)

        return {
            "total_memories": total,
            "by_type": dict(type_counts),
            "avg_importance": round(importance_sum / total, 2) if total else 0,
            "most_accessed": sorted(
                [{"id": k, "count": v} for k, v in self._access_counts.items()],
                key=lambda x: x["count"], reverse=True,
            )[:10],
        }

    def get_growth_rate(self, memories: list[dict]) -> list[dict]:
        daily: dict[str, int] = defaultdict(int)
        for m in memories:
            created = m.get("created_at", "")
            if created:
                day = created[:10]
                daily[day] += 1
        result = []
        cumulative = 0
        for day in sorted(daily.keys()):
            cumulative += daily[day]
            result.append({"date": day, "new": daily[day], "total": cumulative})
        return result[-30:]


class MemoryConsolidation:
    """Consolidate and manage memory lifecycle."""

    def __init__(self) -> None:
        self._consolidation_log: list[dict] = []

    def find_duplicates(self, memories: list[dict], threshold: float = 0.85) -> list[dict]:
        """Find potential duplicate memories using fuzzy matching."""
        duplicates = []
        seen: set[tuple[str, str]] = set()
        for i, m1 in enumerate(memories):
            for j, m2 in enumerate(memories):
                if i >= j:
                    continue
                key = (m1.get("id", ""), m2.get("id", ""))
                if key in seen:
                    continue
                c1 = m1.get("content", "")
                c2 = m2.get("content", "")
                if not c1 or not c2:
                    continue
                similarity = SequenceMatcher(None, c1[:500], c2[:500]).ratio()
                if similarity >= threshold:
                    duplicates.append({
                        "memory_1": m1.get("id"),
                        "memory_2": m2.get("id"),
                        "similarity": round(similarity, 3),
                        "content_1_preview": c1[:100],
                        "content_2_preview": c2[:100],
                    })
                    seen.add(key)
        return duplicates

    def calculate_forgetting_curve(self, memory: dict) -> dict:
        """Calculate memory retention based on age and access frequency."""
        now = datetime.now(timezone.utc)
        created = memory.get("created_at", "")
        last_accessed = memory.get("last_accessed", created)

        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_days = (now - created_dt).days
        except (ValueError, TypeError):
            age_days = 0

        try:
            access_dt = datetime.fromisoformat(last_accessed.replace("Z", "+00:00"))
            days_since_access = (now - access_dt).days
        except (ValueError, TypeError):
            days_since_access = age_days

        importance = memory.get("importance", 0.5)
        base_retention = math.exp(-0.1 * days_since_access)
        importance_boost = importance * 0.3
        retention = min(1.0, base_retention + importance_boost)

        return {
            "memory_id": memory.get("id"),
            "age_days": age_days,
            "days_since_access": days_since_access,
            "retention_score": round(retention, 3),
            "recommendation": "keep" if retention > 0.3 else ("consolidate" if retention > 0.1 else "forget"),
        }

    def get_consolidation_candidates(self, memories: list[dict], threshold: float = 0.2) -> list[dict]:
        candidates = []
        for m in memories:
            curve = self.calculate_forgetting_curve(m)
            if curve["retention_score"] <= threshold:
                candidates.append({
                    **curve,
                    "content_preview": m.get("content", "")[:100],
                    "type": m.get("type"),
                    "importance": m.get("importance", 0),
                })
        return sorted(candidates, key=lambda x: x["retention_score"])

    def merge_memories(self, memories: list[dict]) -> dict:
        """Merge multiple related memories into a single summary."""
        if len(memories) < 2:
            return {"ok": False, "reason": "Need at least 2 memories to merge"}
        contents = [m.get("content", "") for m in memories]
        types = list(set(m.get("type", "unknown") for m in memories))
        max_importance = max(m.get("importance", 0) for m in memories)
        merged_content = " | ".join(c[:200] for c in contents if c)
        self._consolidation_log.append({
            "merged_ids": [m.get("id") for m in memories],
            "result_preview": merged_content[:100],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "ok": True,
            "merged_content": merged_content,
            "type": types[0] if len(types) == 1 else "mixed",
            "importance": max_importance,
            "source_count": len(memories),
        }

    def get_consolidation_log(self) -> list[dict]:
        return list(self._consolidation_log)


# Singletons
tag_manager = MemoryTagManager()
relationship_manager = MemoryRelationshipManager()
memory_analytics = MemoryAnalytics()
memory_consolidation = MemoryConsolidation()
