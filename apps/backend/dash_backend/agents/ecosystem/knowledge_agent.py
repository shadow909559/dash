"""Knowledge Agent.

Provides RAG, embeddings, documentation lookup, project understanding and
local search. It wraps the existing ``rag`` and ``memory`` services as a
first-class agent so the orchestrator can pull grounded knowledge on demand.
"""

from __future__ import annotations

from typing import Any, Dict, List

from dash_backend.agents.ecosystem.base import (
    AgentDependency,
    AgentPriority,
    AgentSpec,
    BaseAgent,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def knowledge_agent_spec() -> AgentSpec:
    """The declarative spec for the Knowledge Agent."""
    return AgentSpec(
        key="knowledge",
        name="Knowledge Agent",
        description=(
            "Uses RAG, embeddings, documentation, project understanding and "
            "local search to provide grounded knowledge."
        ),
        capabilities=[
            "retrieval_augmented_generation",
            "embeddings",
            "documentation_lookup",
            "project_understanding",
            "local_search",
        ],
        priority=AgentPriority.HIGH,
        permissions=["read_documents", "read_memory"],
        dependencies=[
            AgentDependency(name="rag", kind="service", required=False),
            AgentDependency(name="memory", kind="agent", required=False),
        ],
        tools=["rag_retrieve", "embed_query", "search_local", "lookup_doc"],
        memory_access="read",
        execution_api="async",
        category="core",
        system_prompt=(
            "You are DASH's Knowledge Agent. You retrieve grounded information "
            "from documents and memory to answer questions accurately."
        ),
    )


class KnowledgeAgent(BaseAgent):
    """Runtime for the Knowledge Agent."""

    def __init__(self) -> None:
        super().__init__(knowledge_agent_spec())

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "retrieve")
        logger.info("Knowledge Agent action=%s", action)

        if action == "retrieve":
            return await self._rag_retrieve(payload)
        if action == "embed":
            return await self._embed(payload)
        if action == "search":
            return await self._local_search(payload)
        return {"status": "ok", "agent": "knowledge"}

    async def _rag_retrieve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve grounded context via the real RAG service.

        A genuine no-matches result is reported honestly as ``source:
        "rag-empty"``; infrastructure failures raise so the agent health
        reflects reality instead of silently degrading.
        """
        from dash_backend.rag.service import retrieve_context
        from dash_backend.db.session import AsyncSessionLocal

        query = str(payload.get("query") or "")
        user_id = payload.get("user_id") or ""
        if not user_id:
            raise ValueError("retrieve requires user_id")
        async with AsyncSessionLocal() as session:
            context = await retrieve_context(
                session,
                user_id,
                query=query or None,
                max_chunks=int(payload.get("max_chunks", 5)),
                client_id=payload.get("client_id"),
            )
        if not context:
            return {"context": "", "query": query, "source": "rag-empty"}
        return {"context": context, "query": query, "source": "rag"}

    async def _embed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Embed via the real embedding service.

        Empty-vector failures were previously swallowed into ``vector: []``
        (indistinguishable from a legit empty embedding); now they raise.
        """
        from dash_backend.rag.embeddings import create_embedding

        text = str(payload.get("text") or "")
        if not text:
            raise ValueError("embed requires text")
        vector = await create_embedding(text)
        if not vector:
            raise ValueError("embedding service returned no vector")
        return {"vector": vector, "dims": len(vector), "text": text}

    async def _local_search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Search the real local KnowledgeBase (semantic, embeddings-backed).

        The old implementation returned a hardcoded ``[]`` while the spec
        claimed ``local_search`` as a capability.
        """
        from dash_backend.intelligence.knowledge_base import get_knowledge_base

        query = str(payload.get("query") or "")
        if not query:
            raise ValueError("search requires a query")
        kb = get_knowledge_base()
        results = await kb.search(query, top_k=int(payload.get("top_k", 5)))
        stats = kb.get_stats()
        return {
            "results": [
                {
                    "doc_path": r.chunk.doc_path,
                    "content": r.chunk.content,
                    "score": r.score,
                }
                for r in results
            ],
            "query": query,
            "indexed_documents": stats["total_documents"],
            "total_chunks": stats["total_chunks"],
        }


_knowledge_agent: KnowledgeAgent | None = None


def get_knowledge_agent() -> KnowledgeAgent:
    """Return the Knowledge Agent singleton."""
    global _knowledge_agent
    if _knowledge_agent is None:
        _knowledge_agent = KnowledgeAgent()
    return _knowledge_agent
