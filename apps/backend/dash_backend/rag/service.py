"""RAG service: document ingestion, chunking, embedding, search, and citation support."""

from __future__ import annotations

import uuid
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.logging_config import get_logger
from dash_backend.rag.chunking import split_text_into_chunks
from dash_backend.rag.embeddings import create_embedding
from dash_backend.rag import models

logger = get_logger(__name__)

# Supported file extensions for source code indexing
SOURCE_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".swift",
    ".go", ".rs", ".rb", ".php", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".fs", ".scala", ".clj", ".ex", ".exs",
    ".html", ".css", ".scss", ".less",
    ".json", ".yaml", ".yml", ".toml", ".xml",
    ".md", ".rst", ".txt",
    ".sql", ".graphql", ".proto",
    ".sh", ".bash", ".zsh", ".ps1",
    ".dockerfile", ".makefile",
}

# File extensions to skip
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib",
    ".exe", ".msi", ".deb", ".rpm",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".ttf", ".otf", ".woff", ".woff2",
    ".o", ".obj", ".lib", ".a",
}


async def create_document(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    content: str,
    filename: str | None = None,
    metadata: dict | None = None,
) -> models.Document:
    """Create a new document and process it into chunks."""
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    doc = models.Document(
        user_id=uid,
        filename=filename,
        content=content,
        metadata_=metadata or {},
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # Automatically process into chunks
    try:
        await process_document(session, doc.id)
    except Exception:
        logger.exception("Failed to process document %s", doc.id)

    return doc


async def ingest_file(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    file_path: str | Path,
    *,
    filename: str | None = None,
) -> models.Document | None:
    """Ingest a file from the filesystem into the RAG system.

    Supports source code files, markdown, and text files.
    Returns None if the file type is not supported.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in SKIP_EXTENSIONS:
        logger.debug("Skipping unsupported file type: %s", ext)
        return None

    if not path.exists():
        logger.warning("File not found: %s", path)
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Failed to read file %s: %s", path, exc)
        return None

    doc_name = filename or path.name
    metadata = {
        "source_path": str(path.absolute()),
        "file_extension": ext,
        "file_size_bytes": path.stat().st_size,
        "is_source_code": ext in SOURCE_CODE_EXTENSIONS,
    }

    return await create_document(session, user_id, content, filename=doc_name, metadata=metadata)


async def ingest_directory(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    directory_path: str | Path,
    *,
    recursive: bool = True,
    max_files: int = 100,
) -> List[models.Document]:
    """Ingest all supported files from a directory."""
    path = Path(directory_path)
    if not path.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")

    documents: List[models.Document] = []
    pattern = "**/*" if recursive else "*"

    for file_path in path.glob(pattern):
        if not file_path.is_file():
            continue
        if len(documents) >= max_files:
            break

        doc = await ingest_file(session, user_id, file_path)
        if doc:
            documents.append(doc)

    logger.info("Ingested %d documents from %s", len(documents), directory_path)
    return documents


async def process_document(
    session: AsyncSession,
    document_id: uuid.UUID | str,
) -> List[models.DocumentChunk]:
    """Chunk a document, create DocumentChunk rows, and compute embeddings if available."""
    did = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
    doc = await session.get(models.Document, did)
    if doc is None:
        raise ValueError("Document not found")

    chunks_text = split_text_into_chunks(doc.content)
    created_chunks: List[models.DocumentChunk] = []

    for idx, text in enumerate(chunks_text):
        chunk = models.DocumentChunk(
            document_id=doc.id,
            chunk_text=text,
            chunk_index=idx,
        )
        session.add(chunk)
        created_chunks.append(chunk)

    await session.commit()

    for chunk in created_chunks:
        await session.refresh(chunk)

    # Compute embeddings per-chunk (best-effort)
    for chunk in created_chunks:
        try:
            emb = await create_embedding(chunk.chunk_text)
            if emb:
                chunk.embedding = emb
                session.add(chunk)
        except Exception as exc:
            logger.warning("Failed to create embedding for chunk %s: %s", chunk.id, exc)

    await session.commit()
    return created_chunks


def _cosine_sim(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return -1.0
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
    file_extension: str | None = None,
) -> List[Tuple[models.DocumentChunk, float]]:
    """Search for relevant document chunks to the query.

    If embeddings are available for chunks and a provider is configured, perform
    embedding-based similarity search (in Python). Otherwise fallback to text
    substring search.

    Supports filtering by file extension for source code search.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    query_emb = await create_embedding(query)

    # If embeddings available, fetch candidate chunks with embeddings
    if query_emb is not None:
        stmt = (
            select(models.DocumentChunk, models.Document.filename, models.Document.metadata_)
            .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
            .where(models.Document.user_id == uid, models.DocumentChunk.embedding.isnot(None))
        )

        if file_extension:
            stmt = stmt.where(models.Document.metadata_["file_extension"].as_string() == file_extension)

        stmt = stmt.order_by(models.DocumentChunk.created_at.desc()).limit(candidate_limit)

        result = await session.execute(stmt)
        rows = result.all()

        scored: List[Tuple[models.DocumentChunk, float]] = []
        now = datetime.now(timezone.utc)
        seen_texts = set()
        for row in rows:
            chunk = row[0]
            norm = (chunk.chunk_text or "").strip()[:200].lower()
            if norm in seen_texts:
                continue
            seen_texts.add(norm)

            try:
                sim = _cosine_sim(query_emb, chunk.embedding or [])
            except Exception:
                sim = -1.0

            # Recency factor
            recency_score = 0.0
            try:
                if getattr(chunk, "created_at", None):
                    age_seconds = (now - chunk.created_at).total_seconds()
                    age_days = age_seconds / 86400.0
                    recency_score = math.exp(-age_days / 30.0)
            except Exception:
                recency_score = 0.0

            # Lexical boost for exact matches
            lexical_boost = 0.0
            if query.lower() in (chunk.chunk_text or "").lower():
                lexical_boost = 0.2

            final_score = 0.75 * sim + 0.25 * recency_score + lexical_boost
            scored.append((chunk, final_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # Fallback: case-insensitive substring search
    like = f"%{query}%"
    stmt = (
        select(models.DocumentChunk, models.Document.filename, models.Document.metadata_)
        .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
        .where(models.Document.user_id == uid, models.DocumentChunk.chunk_text.ilike(like))
    )

    if file_extension:
        stmt = stmt.where(models.Document.metadata_["file_extension"].as_string() == file_extension)

    stmt = stmt.order_by(models.DocumentChunk.created_at.desc()).limit(top_k)
    result = await session.execute(stmt)
    rows = result.all()
    return [(row[0], 0.0) for row in rows]


async def retrieve_context(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    query: str | None = None,
    max_chunks: int = 5,
    file_extension: str | None = None,
) -> str:
    """Retrieve a context string composed of top matching chunks with citations.

    If `query` is None, return most important recent chunks (by created_at).
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    if query:
        results = await search_documents(
            session, uid, query,
            top_k=max_chunks,
            file_extension=file_extension,
        )
    else:
        stmt = (
            select(models.DocumentChunk, models.Document.filename, models.Document.metadata_)
            .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
            .where(models.Document.user_id == uid)
            .order_by(models.DocumentChunk.created_at.desc())
            .limit(max_chunks)
        )
        res = await session.execute(stmt)
        results = [(row[0], 0.0) for row in res.all()]

    if not results:
        return ""

    lines: List[str] = ["[RELEVANT DOCUMENTS]"]
    for idx, (chunk, score) in enumerate(results, 1):
        filename = None
        try:
            doc = await session.get(models.Document, chunk.document_id)
            filename = doc.filename if doc else None
        except Exception:
            filename = None

        header = f"[{idx}] {filename or 'document'} (chunk {chunk.chunk_index})"
        if score is not None and score > 0:
            header += f" relevance={score:.4f}"
        lines.append(header)

        snippet = chunk.chunk_text.replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        lines.append(f"  {snippet}")

    lines.append("[/RELEVANT DOCUMENTS]")
    return "\n".join(lines)


async def delete_document(
    session: AsyncSession,
    document_id: uuid.UUID | str,
) -> bool:
    """Delete a document and all its chunks."""
    did = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
    doc = await session.get(models.Document, did)
    if doc is None:
        return False
    await session.delete(doc)
    await session.commit()
    return True


async def get_user_documents(
    session: AsyncSession,
    user_id: uuid.UUID | str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[models.Document], int]:
    """List all documents for a user."""
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    count_q = select(func.count(models.Document.id)).where(models.Document.user_id == uid)
    total = await session.scalar(count_q) or 0

    query = (
        select(models.Document)
        .where(models.Document.user_id == uid)
        .order_by(models.Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all()), total