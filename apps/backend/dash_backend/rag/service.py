"""RAG service: document ingestion, chunking, embedding, and search."""

from __future__ import annotations

import uuid
import math
from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.logging_config import get_logger
from dash_backend.db.session import get_db_session
from dash_backend.rag.chunking import split_text_into_chunks
from dash_backend.rag.embeddings import create_embedding
from dash_backend.rag import models

logger = get_logger(__name__)


async def create_document(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    content: str,
    filename: str | None = None,
    metadata: dict | None = None,
) -> models.Document:
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    doc = models.Document(user_id=uid, filename=filename, content=content, metadata=metadata)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


async def process_document(session: AsyncSession, document_id: uuid.UUID | str) -> List[models.DocumentChunk]:
    """Chunk a document, create DocumentChunk rows, and compute embeddings if available."""
    did = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
    doc = await session.get(models.Document, did)
    if doc is None:
        raise ValueError("Document not found")

    chunks_text = split_text_into_chunks(doc.content)
    created_chunks: List[models.DocumentChunk] = []

    for idx, text in enumerate(chunks_text):
        chunk = models.DocumentChunk(document_id=doc.id, chunk_text=text, chunk_index=idx)
        session.add(chunk)
        created_chunks.append(chunk)

    await session.commit()

    # refresh to populate ids
    for chunk in created_chunks:
        await session.refresh(chunk)

    # compute embeddings per-chunk (best-effort)
    for chunk in created_chunks:
        try:
            emb = await create_embedding(chunk.chunk_text)
            if emb:
                # assign and persist
                chunk.embedding = emb
                session.add(chunk)
        except Exception as exc:
            logger.warning("Failed to create embedding for chunk %s: %s", chunk.id, exc)

    await session.commit()
    return created_chunks


def _cosine_sim(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return -1.0
    # ensure same length
    if len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return -1.0
    return dot / (na * nb)


async def search_documents(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    query: str,
    top_k: int = 5,
    candidate_limit: int = 200,
) -> List[Tuple[models.DocumentChunk, float]]:
    """Search for relevant document chunks to the query.

    If embeddings are available for chunks and a provider is configured, perform
    embedding-based similarity search (in Python). Otherwise fallback to text
    substring search.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    query_emb = await create_embedding(query)

    # If embeddings available, fetch candidate chunks with embeddings
    if query_emb is not None:
        stmt = (
            select(models.DocumentChunk, models.Document.filename)
            .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
            .where(models.Document.user_id == uid, models.DocumentChunk.embedding.isnot(None))
            .order_by(models.DocumentChunk.created_at.desc())
            .limit(candidate_limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

        scored: List[Tuple[models.DocumentChunk, float]] = []
        for row in rows:
            chunk = row[0]
            try:
                score = _cosine_sim(query_emb, chunk.embedding or [])
            except Exception:
                score = -1.0
            scored.append((chunk, score))

        # sort by descending score
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # Fallback: case-insensitive substring search on chunk_text
    like = f"%{query}%"
    stmt = (
        select(models.DocumentChunk, models.Document.filename)
        .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
        .where(models.Document.user_id == uid, models.DocumentChunk.chunk_text.ilike(like))
        .order_by(models.DocumentChunk.created_at.desc())
        .limit(top_k)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [(row[0], None) for row in rows]


async def retrieve_context(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    query: str | None = None,
    max_chunks: int = 5,
) -> str:
    """Retrieve a short context string composed of top matching chunks.

    If `query` is None, return most important recent chunks (by created_at).
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    if query:
        results = await search_documents(session, uid, query, top_k=max_chunks)
    else:
        # return most recent chunks for the user
        stmt = (
            select(models.DocumentChunk, models.Document.filename)
            .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
            .where(models.Document.user_id == uid)
            .order_by(models.DocumentChunk.created_at.desc())
            .limit(max_chunks)
        )
        res = await session.execute(stmt)
        results = [(row[0], None) for row in res.all()]

    if not results:
        return ""

    lines: List[str] = ["[RELEVANT DOCUMENTS]"]
    for chunk, score in results:
        # attempt to include filename if available
        filename = None
        try:
            # chunk.document may be lazy; prefer to fetch filename via relationship if present
            filename = getattr(chunk, "document", None) and getattr(chunk.document, "filename", None)
        except Exception:
            filename = None
        header = f"- {filename or 'document'} (chunk {chunk.chunk_index})"
        if score is not None:
            header += f" score={score:.4f}"
        lines.append(header)
        snippet = chunk.chunk_text.replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        lines.append(snippet)
    return "\n".join(lines)
