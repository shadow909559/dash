# TODO.md

## Phase 3 — Implement Persistent Memory

- [x] Gather repo understanding (models, service, routes, websocket integration).
- [ ] Add `search_memories()` to memory service (no embeddings; keep minimal).
- [ ] Enforce public API path `/api/v1/memory` by adjusting FastAPI router mounting / prefixes.
- [ ] Ensure no duplicate routes exist.
- [ ] Update/align new memory module structure only if required by spec (minimal wrappers if needed).
- [ ] Add/adjust compilation targets per verification.
- [ ] Run backend tests (at least `apps/backend/tests/test_memory.py`).

