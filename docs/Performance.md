# Performance Guide

## Overview

This guide covers performance optimization, benchmarking, and monitoring for the DASH backend and frontend.

## Backend Performance

### Database

- **Connection Pooling**: SQLAlchemy connection pool (default 5-20 connections)
- **Indexing**: All foreign keys and frequently queried columns indexed
- **Query Optimization**: Use `selectinload` for eager loading relationships
- **Batch Operations**: Use `bulk_insert_mappings` for large inserts

### LLM Calls

- **Connection Pooling**: HTTP connection reuse via `httpx`
- **Timeout**: Configurable per-provider (default: 60s)
- **Retry**: Exponential backoff with jitter (max: 3 retries)
- **Caching**: Optional Redis-backed response cache for embeddings

### Caching

- **In-Memory Cache**: `simple_cache.py` for process-local data (TTL-based)
- **Redis**: Optional Redis integration for distributed caching
- **Embedding Cache**: Avoid recomputing embeddings for frequent queries
- **Rate Limiting**: Token bucket algorithm (in-memory)

## Benchmarking

```bash
# Profile performance
python profile_performance.py

# Run with profiling
python -m cProfile -o profile.stats dash_backend/main.py
```

## Monitoring

- Health check: `GET /api/v1/health`
- Application metrics via Prometheus endpoint (optional)
- Structured JSON logging for log aggregation
- Request duration logging (slow queries flagged)

## Performance Bottlenecks

| Component | Bottleneck | Mitigation |
|-----------|-----------|------------|
| LLM Calls | Network latency | Streaming responses, connection pooling |
| Embeddings | Compute time | Cache results, batch requests |
| File I/O | Disk speed | Async operations, sandbox isolation |
| Voice | Audio processing | Async streaming, VAD optimization |
| Vision | OCR processing | Provider abstraction, caching |
