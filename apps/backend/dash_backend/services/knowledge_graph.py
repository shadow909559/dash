"""Knowledge graph, chain-of-thought visualization, hallucination detection, source verification."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Auto-extract entities and relationships from content into a graph."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}
        self._edges: list[dict] = []
        self._entity_types = ["person", "project", "technology", "concept", "location", "organization", "date", "file"]
        self._load_state()

    # ── Persistence (custom entities/edges survive restarts) ───────

    @staticmethod
    def _state_path() -> Any:
        """Graph state file. Override with DASH_KG_STATE for tests."""
        from pathlib import Path as _Path

        override = os.environ.get("DASH_KG_STATE")
        if override:
            return _Path(override)
        base = os.environ.get("LOCALAPPDATA") or str(_Path.home() / "AppData" / "Local")
        return _Path(base) / "DASH" / "knowledge_graph_state.json"

    def _load_state(self) -> None:
        try:
            path = self._state_path()
            if path.exists():
                import json as _json

                data = _json.loads(path.read_text(encoding="utf-8"))
                self._nodes = data.get("nodes", {})
                self._edges = data.get("edges", [])
        except Exception:
            logger.debug("Knowledge graph state load failed", exc_info=True)

    def _save_state(self) -> None:
        try:
            import json as _json

            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                _json.dumps(
                    {"version": 1, "nodes": self._nodes, "edges": self._edges},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("Knowledge graph state save failed", exc_info=True)

    # ── Memory seeding ─────────────────────────────────────────────

    def build_graph_from_memories(self, memories: list[dict]) -> dict:
        """Seed the graph from memory dicts (keys: content/title/tags/type).

        Extracts entities per memory, links co-occurring entities with a
        'co_mentioned' edge and tags as 'tagged' edges. Idempotent:
        repeated mentions bump mention_count instead of duplicating nodes.
        Returns extraction stats.
        """
        extracted = 0
        links = 0
        memories_scanned = 0
        for mem in memories:
            text = " ".join(
                str(part) for part in (mem.get("title"), mem.get("content")) if part
            )
            if not text.strip():
                continue
            memories_scanned += 1
            found = self.extract_entities(text)
            extracted += len(found)
            ids: list[str] = []
            for ent in found:
                node_id = f"ent_{ent['name'].lower().replace(' ', '_')}"
                if node_id in self._nodes:
                    ids.append(node_id)
            # Tag nodes (typed per memory type when tags exist)
            for tag in mem.get("tags") or []:
                tag_name = str(tag).strip()
                if not tag_name:
                    continue
                tag_id = f"tag_{tag_name.lower().replace(' ', '_')}"
                if tag_id not in self._nodes:
                    self._nodes[tag_id] = {
                        "id": tag_id,
                        "name": tag_name,
                        "type": "tag",
                        "properties": {},
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "mention_count": 0,
                    }
                self._nodes[tag_id]["mention_count"] = self._nodes[tag_id].get("mention_count", 0) + 1
                ids.append(tag_id)
            # Link every co-occurring entity pair
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    if a != b and not self._has_edge(a, b):
                        self._edges.append({
                            "source": a,
                            "target": b,
                            "relationship": "co_mentioned",
                            "weight": 1.0,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        })
                        links += 1
        self._save_state()
        return {
            "ok": True,
            "memories_scanned": memories_scanned,
            "entities_extracted": extracted,
            "edges_created": links,
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
        }

    def _has_edge(self, source_id: str, target_id: str) -> bool:
        return any(
            (e["source"] == source_id and e["target"] == target_id)
            or (e["source"] == target_id and e["target"] == source_id)
            for e in self._edges
        )

    def add_entity(self, name: str, entity_type: str, properties: dict | None = None) -> dict:
        if entity_type not in self._entity_types:
            return {"ok": False, "reason": f"Invalid type. Use: {self._entity_types}"}
        node_id = f"ent_{name.lower().replace(' ', '_')}"
        node = {
            "id": node_id,
            "name": name,
            "type": entity_type,
            "properties": properties or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mention_count": 1,
        }
        if node_id in self._nodes:
            self._nodes[node_id]["mention_count"] += 1
            if properties:
                self._nodes[node_id]["properties"].update(properties)
        else:
            self._nodes[node_id] = node
        return {"ok": True, "node": self._nodes[node_id]}

    def add_edge(self, source_id: str, target_id: str, relationship: str, weight: float = 1.0) -> dict:
        edge = {
            "source": source_id,
            "target": target_id,
            "relationship": relationship,
            "weight": weight,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._edges.append(edge)
        return {"ok": True, "edge": edge}

    def extract_entities(self, text: str) -> list[dict]:
        """Extract entities from text using simple NLP heuristics."""
        entities = []
        # Extract capitalized phrases (simple NER)
        capitalized = re.findall(r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b', text)
        seen = set()
        for name in capitalized:
            if name.lower() not in seen and len(name) > 2:
                seen.add(name.lower())
                entities.append({"name": name, "type": "concept"})

        # Extract dates
        dates = re.findall(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', text)
        for d in dates:
            entities.append({"name": d, "type": "date"})

        # Extract tech terms
        tech_terms = re.findall(r'\b(Python|JavaScript|TypeScript|Rust|Go|React|Vue|Node\.js|FastAPI|Django|PostgreSQL|SQLite|Redis|Docker|Kubernetes|AWS|GCP|Azure|Git|Linux|Windows|macOS)\b', text)
        for term in set(tech_terms):
            entities.append({"name": term, "type": "technology"})

        # Store extracted entities
        for ent in entities:
            self.add_entity(ent["name"], ent["type"])

        return entities

    def get_node(self, node_id: str) -> Optional[dict]:
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> dict:
        incoming = [e for e in self._edges if e["target"] == node_id]
        outgoing = [e for e in self._edges if e["source"] == node_id]
        neighbor_ids = set(e["source"] for e in incoming) | set(e["target"] for e in outgoing)
        neighbors = [self._nodes.get(nid) for nid in neighbor_ids if nid in self._nodes]
        return {"incoming": incoming, "outgoing": outgoing, "neighbors": neighbors}

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [n for n in self._nodes.values() if q in n["name"].lower() or q in n.get("type", "")]

    def get_graph(self, max_nodes: int = 100) -> dict:
        nodes = list(self._nodes.values())[:max_nodes]
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in self._edges if e["source"] in node_ids and e["target"] in node_ids]
        return {"nodes": nodes, "edges": edges, "total_nodes": len(self._nodes), "total_edges": len(self._edges)}

    def get_stats(self) -> dict:
        type_counts = {}
        for n in self._nodes.values():
            t = n.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "by_type": type_counts,
            "most_mentioned": sorted(
                self._nodes.values(), key=lambda x: x.get("mention_count", 0), reverse=True
            )[:10],
        }

    def clear(self) -> dict:
        count = len(self._nodes)
        self._nodes.clear()
        self._edges.clear()
        self._save_state()
        return {"ok": True, "cleared_nodes": count}


class ChainOfThoughtVisualizer:
    """Structured reasoning visualization."""

    def __init__(self) -> None:
        self._chains: list[dict] = []

    def create_chain(self, question: str) -> dict:
        chain_id = f"cot_{len(self._chains)}"
        chain = {
            "id": chain_id,
            "question": question,
            "steps": [],
            "conclusion": None,
            "confidence": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._chains.append(chain)
        return chain

    def add_step(self, chain_id: str, reasoning: str, evidence: str = "", confidence: float = 0.5) -> dict:
        chain = next((c for c in self._chains if c["id"] == chain_id), None)
        if not chain:
            return {"ok": False, "reason": "Chain not found"}
        step = {
            "step": len(chain["steps"]) + 1,
            "reasoning": reasoning,
            "evidence": evidence,
            "confidence": confidence,
        }
        chain["steps"].append(step)
        # Recalculate chain confidence
        if chain["steps"]:
            chain["confidence"] = round(
                sum(s["confidence"] for s in chain["steps"]) / len(chain["steps"]), 3
            )
        return {"ok": True, "step": step, "chain_confidence": chain["confidence"]}

    def set_conclusion(self, chain_id: str, conclusion: str) -> dict:
        chain = next((c for c in self._chains if c["id"] == chain_id), None)
        if not chain:
            return {"ok": False, "reason": "Chain not found"}
        chain["conclusion"] = conclusion
        return {"ok": True}

    def get_chain(self, chain_id: str) -> Optional[dict]:
        return next((c for c in self._chains if c["id"] == chain_id), None)

    def get_all_chains(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._chains[-limit:]))

    def to_tree(self, chain_id: str) -> dict:
        chain = self.get_chain(chain_id)
        if not chain:
            return {"ok": False, "reason": "Chain not found"}
        return {
            "id": chain["id"],
            "question": chain["question"],
            "children": [
                {"label": f"Step {s['step']}", "content": s["reasoning"],
                 "evidence": s["evidence"], "confidence": s["confidence"]}
                for s in chain["steps"]
            ],
            "conclusion": chain["conclusion"],
            "total_confidence": chain["confidence"],
        }


class HallucinationDetector:
    """Detect potential hallucinations by cross-referencing claims against known facts."""

    def __init__(self) -> None:
        self._known_facts: list[dict] = []
        self._checks: list[dict] = []

    def add_fact(self, content: str, source: str = "user", metadata: dict | None = None) -> dict:
        fact = {
            "id": f"fact_{len(self._known_facts)}",
            "content": content,
            "source": source,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._known_facts.append(fact)
        return {"ok": True, "fact": fact}

    def check_response(self, response: str, context: list[str] | None = None) -> dict:
        """Check a response for potential hallucinations."""
        warnings = []
        claims = re.split(r'[.!?]+', response)
        claims = [c.strip() for c in claims if len(c.strip()) > 10]

        for claim in claims:
            # Check against known facts
            for fact in self._known_facts:
                similarity = self._text_similarity(claim.lower(), fact["content"].lower())
                if 0.3 < similarity < 0.7:
                    warnings.append({
                        "claim": claim[:200],
                        "conflicts_with": fact["content"][:200],
                        "similarity": round(similarity, 3),
                        "warning_type": "partial_mismatch",
                    })
                elif similarity > 0.7:
                    # Likely consistent
                    pass

            # Check for common hallucination patterns
            self_hallucination_patterns = [
                r"I (?:know|found|read|saw) that (.{10,})",
                r"(?:studies|research) (?:show|prove|indicate) that (.{10,})",
                r"(?:according to|per) (?:the|a) (?:study|report) (.{10,})",
            ]
            for pattern in self_hallucination_patterns:
                match = re.search(pattern, claim, re.IGNORECASE)
                if match:
                    warnings.append({
                        "claim": claim[:200],
                        "warning_type": "unsupported_claim",
                        "note": "This claim references external sources that may not be verified",
                    })

        result = {
            "response_length": len(response),
            "claims_checked": len(claims),
            "warnings": warnings,
            "risk_level": "high" if len(warnings) > 3 else ("medium" if warnings else "low"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._checks.append(result)
        return result

    def get_facts(self) -> list[dict]:
        return list(self._known_facts)

    def get_checks(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._checks[-limit:]))

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a[:500], b[:500]).ratio()


class SourceVerifier:
    """Cross-reference AI claims against known sources."""

    def __init__(self) -> None:
        self._sources: list[dict] = []
        self._verifications: list[dict] = []

    def add_source(self, url: str, title: str, content_summary: str, last_verified: str = "") -> dict:
        source = {
            "id": f"src_{len(self._sources)}",
            "url": url,
            "title": title,
            "content_summary": content_summary,
            "last_verified": last_verified or datetime.now(timezone.utc).isoformat(),
            "trust_score": 0.5,
        }
        self._sources.append(source)
        return {"ok": True, "source": source}

    def verify_claim(self, claim: str, cited_url: str | None = None) -> dict:
        matching_sources = []
        if cited_url:
            matching_sources = [s for s in self._sources if s["url"] == cited_url]

        if not matching_sources:
            # Fuzzy match against all sources
            for source in self._sources:
                similarity = self._text_similarity(claim.lower(), source["content_summary"].lower())
                if similarity > 0.3:
                    matching_sources.append({**source, "match_score": similarity})

        result = {
            "claim": claim[:200],
            "sources_found": len(matching_sources),
            "sources": matching_sources[:5],
            "verified": len(matching_sources) > 0,
            "trust_level": self._calculate_trust(matching_sources),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._verifications.append(result)
        return result

    def get_sources(self) -> list[dict]:
        return list(self._sources)

    def get_verifications(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._verifications[-limit:]))

    def update_trust(self, source_id: str, trust_score: float) -> dict:
        for s in self._sources:
            if s["id"] == source_id:
                s["trust_score"] = max(0.0, min(1.0, trust_score))
                return {"ok": True}
        return {"ok": False, "reason": "Source not found"}

    @staticmethod
    def _calculate_trust(sources: list[dict]) -> str:
        if not sources:
            return "unverified"
        avg = sum(s.get("trust_score", 0.5) for s in sources) / len(sources)
        return "high" if avg >= 0.7 else ("medium" if avg >= 0.4 else "low")

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a[:500], b[:500]).ratio()


# Singletons
knowledge_graph = KnowledgeGraph()
chain_visualizer = ChainOfThoughtVisualizer()
hallucination_detector = HallucinationDetector()
source_verifier = SourceVerifier()
