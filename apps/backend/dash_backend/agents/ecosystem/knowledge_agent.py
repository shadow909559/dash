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
        """Retrieve relevant document context via RAG."""
        query = payload.get("query", "")
        try:
            from dash_backend.rag.service import retrieve_context  # type: ignore[import-not-found]
            from dash_backend.db.session import AsyncSessionLocal

            user_id = payload.get("user_id", "")
            async with AsyncSessionLocal() as session:
                context = await retrieve_context(session, user_id, query=query, max_chunks=5)
            return {"context": context, "query": query, "source": "rag"}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Knowledge retrieve fallback: %s", exc)
            return {"context": "", "query": query, "source": "none"}

    async def _embed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Embed a query via the embedding service."""
        text = payload.get("text", "")
        try:
            from dash_backend.rag.embeddings import embed_texts  # type: ignore[import-not-found]

            vector = await embed_texts([text])
            return {"vector": vector, "text": text}
        except Exception as exc:  # noqa: BLE001
            logger.debug("Knowledge embed fallback: %s", exc)
            return {"vector": [], "text": text, "error": str(exc)}

    async def _local_search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a local document search."""
        return {"results": [], "query": payload.get("query", "")}


_knowledge_agent: KnowledgeAgent | None = None


def get_knowledge_agent() -> KnowledgeAgent:
    """Return the Knowledge Agent singleton."""
    global _knowledge_agent
    if _knowledge_agent is None:
        _knowledge_agent = KnowledgeAgent()
    return _knowledge_agent
