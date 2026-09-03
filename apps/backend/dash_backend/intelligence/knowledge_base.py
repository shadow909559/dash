"""Knowledge Base — RAG system for local documents and code.

Indexes:
- Text files (.md, .txt, .py, .js, .ts, .json, .yaml, .toml, .csv)
- Obsidian vault notes
- Code repositories
- Configuration files

Uses nomic-embed-text for 768-dim semantic search vectors.
Chunks documents into 512-token segments with overlap for context.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Chunking config
CHUNK_SIZE = 512  # characters per chunk
CHUNK_OVERLAP = 64  # overlap between chunks
MAX_INDEX_SIZE = 10000  # max chunks in memory

# File extensions to index
INDEXABLE_EXTENSIONS = {
    ".md", ".txt", ".py", ".js", ".ts", ".jsx", ".tsx", ".json",
    ".yaml", ".yml", ".toml", ".csv", ".xml", ".html", ".css",
    ".sql", ".sh", ".bat", ".ps1", ".go", ".rs", ".java", ".kt",
    ".swift", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".lua",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", ".venv", "venv", "env",
    "dist", "build", ".idea", ".vscode", "target", ".next", ".nuxt",
    "coverage", ".pytest_cache", ".mypy_cache", ".tox",
}


@dataclass
class DocumentChunk:
    """A chunk of text from an indexed document."""
    doc_path: str
    chunk_index: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    doc_hash: str = ""  # for deduplication


@dataclass
class SearchResult:
    """A search result with relevance score."""
    chunk: DocumentChunk
    score: float  # cosine similarity


class KnowledgeBase:
    """Local knowledge base with semantic search.

    Indexes text files and code, chunks them, generates embeddings,
    and provides cosine similarity search.
    """

    def __init__(self):
        self._chunks: list[DocumentChunk] = []
        self._indexed_paths: set[str] = set()
        self._last_index_time: float = 0.0
        self._index_lock = False

    async def index_directory(self, directory: str | Path, max_files: int = 500) -> int:
        """Index all text files in a directory recursively.

        Returns the number of new chunks added.
        """
        if self._index_lock:
            return 0
        self._index_lock = True

        try:
            dir_path = Path(directory)
            if not dir_path.is_dir():
                logger.warning("Directory not found: %s", directory)
                return 0

            files_indexed = 0
            chunks_added = 0

            for root, dirs, files in os.walk(dir_path):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

                for filename in files:
                    if files_indexed >= max_files:
                        break

                    filepath = Path(root) / filename
                    ext = filepath.suffix.lower()

                    if ext not in INDEXABLE_EXTENSIONS:
                        continue
                    if filepath.stat().st_size > 1_000_000:  # skip files > 1MB
                        continue

                    file_hash = self._file_hash(filepath)
                    rel_path = str(filepath.relative_to(dir_path))

                    if rel_path in self._indexed_paths:
                        # Check if file changed
                        existing = [c for c in self._chunks if c.doc_path == rel_path]
                        if existing and existing[0].doc_hash == file_hash:
                            continue  # unchanged

                    try:
                        content = filepath.read_text(encoding="utf-8", errors="replace")
                        if not content.strip():
                            continue

                        chunks = self._chunk_text(content, rel_path, file_hash)

                        # Remove old chunks for this file
                        self._chunks = [c for c in self._chunks if c.doc_path != rel_path]

                        # Add new chunks
                        for chunk in chunks:
                            chunk.embedding = await self._embed(chunk.content)
                            self._chunks.append(chunk)

                        self._indexed_paths.add(rel_path)
                        files_indexed += 1
                        chunks_added += len(chunks)
                    except Exception as exc:
                        logger.debug("Failed to index %s: %s", filepath, exc)
                        continue

            self._last_index_time = time.time()
            logger.info(
                "Indexed %d files, %d chunks total in %s",
                files_indexed, len(self._chunks), directory,
            )
            return chunks_added
        finally:
            self._index_lock = False

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Semantic search over indexed documents."""
        if not self._chunks:
            return []

        query_embedding = await self._embed(query)
        if not query_embedding or not any(query_embedding):
            return []

        # Score all chunks by cosine similarity
        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in self._chunks:
            if chunk.embedding and any(chunk.embedding):
                sim = self._cosine_similarity(query_embedding, chunk.embedding)
                scored.append((sim, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate by document path (keep best chunk per doc)
        seen_docs: set[str] = set()
        results: list[SearchResult] = []
        for score, chunk in scored:
            if chunk.doc_path not in seen_docs or len(results) < top_k:
                results.append(SearchResult(chunk=chunk, score=score))
                seen_docs.add(chunk.doc_path)
                if len(results) >= top_k:
                    break

        return results

    async def search_multi(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search and return multiple chunks per document for better context."""
        if not self._chunks:
            return []

        query_embedding = await self._embed(query)
        if not query_embedding or not any(query_embedding):
            return []

        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in self._chunks:
            if chunk.embedding and any(chunk.embedding):
                sim = self._cosine_similarity(query_embedding, chunk.embedding)
                scored.append((sim, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [SearchResult(chunk=c, score=s) for s, c in scored[:top_k]]

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        docs = set(c.doc_path for c in self._chunks)
        return {
            "total_chunks": len(self._chunks),
            "total_documents": len(docs),
            "indexed_paths": len(self._indexed_paths),
            "last_index_time": self._last_index_time,
        }

    # ── Internal methods ──────────────────────────────────────────

    def _chunk_text(self, text: str, doc_path: str, doc_hash: str) -> list[DocumentChunk]:
        """Split text into overlapping chunks."""
        chunks = []
        if len(text) <= CHUNK_SIZE:
            chunks.append(DocumentChunk(
                doc_path=doc_path,
                chunk_index=0,
                content=text,
                doc_hash=doc_hash,
                metadata={"total_chunks": 1},
            ))
            return chunks

        start = 0
        idx = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunk_text = text[start:end]
            chunks.append(DocumentChunk(
                doc_path=doc_path,
                chunk_index=idx,
                content=chunk_text,
                doc_hash=doc_hash,
                metadata={"start": start, "end": end},
            ))
            start += CHUNK_SIZE - CHUNK_OVERLAP
            idx += 1

        # Update total_chunks metadata
        for c in chunks:
            c.metadata["total_chunks"] = len(chunks)

        return chunks

    def _file_hash(self, path: Path) -> str:
        """Fast file hash for change detection."""
        try:
            stat = path.stat()
            return hashlib.md5(f"{path}:{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()
        except Exception:
            return ""

    async def _embed(self, text: str) -> list[float]:
        """Generate embedding using Ollama nomic-embed-text."""
        try:
            from dash_backend.intelligence.memory_service import MemoryService
            svc = MemoryService()
            return await svc._generate_embedding(text[:2000])
        except Exception:
            return []

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            min_len = min(len(a), len(b))
            a, b = a[:min_len], b[:min_len]
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# Singleton
_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
