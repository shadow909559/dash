# RAG System

## Overview

Retrieval-Augmented Generation (RAG) allows DASH to ingest, index, and search documents for context-aware responses.

## Architecture

```
Documents -> Ingestion -> Chunking -> Embedding -> Vector Store
                                                    |
User Query -> Embed Query -> Hybrid Search -> Rank -> LLM Context
```

## Ingestion

- File extension whitelist: .py, .js, .ts, .md, .txt, .json, .yaml, .csv
- Binary file detection and skip
- Max file size: 1MB
- UTF-8 encoding with error replacement

## Chunking

- Size: 500 tokens per chunk
- Overlap: 50 tokens
- Recursive character split on natural boundaries

## Search

- **Vector Search**: Cosine similarity on embeddings
- **Keyword Search**: TF-IDF term matching
- **Hybrid Search**: 0.7 vector + 0.3 keyword weight

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/rag/ingest` | Ingest a document |
| GET | `/api/v1/rag/search` | Search documents |
| GET | `/api/v1/rag/documents` | List documents |
| DELETE | `/api/v1/rag/documents/{id}` | Delete document |

## Configuration

```python
RAG_CHUNK_SIZE = 500        # tokens
RAG_CHUNK_OVERLAP = 50      # tokens
RAG_MAX_FILE_SIZE = 1048576  # 1MB
RAG_HYBRID_WEIGHT = 0.7      # vector vs keyword
RAG_MAX_RESULTS = 10
