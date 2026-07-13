# Architecture

DASH is a monorepo AI assistant platform with three client applications and shared libraries.

## Components

| Layer | Technology | Purpose |
|-------|------------|---------|
| Desktop | Electron + React + Vite | Primary desktop experience |
| Mobile | Flutter | iOS and Android client |
| Backend | FastAPI + Uvicorn | API gateway and orchestration |
| Database | PostgreSQL | Persistent storage (future) |
| Cache | Redis | Sessions and pub/sub (future) |

## Package Boundaries

- **shared** — Cross-platform TypeScript types and constants
- **sdk** — HTTP/WebSocket client for backend communication
- **ai-core** — AI provider abstraction (future)
- **agents** — Agent orchestration (future)
- **automation** — Playwright browser automation (future)
- **memory** — Long-term memory (future)
- **prompts** — Prompt template management (future)
- **voice** — Speech-to-text and text-to-speech (future)

## Communication

```
Desktop/Mobile  ──HTTP/WS──▶  Backend  ──▶  PostgreSQL / Redis
                                    │
                                    └──▶  AI Providers (OpenAI, Ollama)
```

## Foundation Milestone Scope

This milestone establishes project structure, configuration, and minimal endpoints only:

- `GET /api/v1/health`
- `WS /api/v1/ws` (echo)

No authentication, database models, or AI logic is implemented yet.
