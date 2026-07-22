# DASH Architecture

## System Overview

DASH is built on a client-server architecture with a Python/FastAPI backend and a Flutter cross-platform frontend.

```
Frontend (Flutter) -> WebSocket + REST -> Backend (FastAPI) -> PostgreSQL
```

## Core Packages

| Package | Responsibility |
|---------|---------------|
| `api/` | REST and WebSocket endpoints |
| `auth/` | JWT, PBKDF2, refresh tokens |
| `chat/` | Conversation management |
| `llm/` | LLM provider abstraction |
| `memory/` | Semantic memory with importance scoring |
| `executive/` | Planner and goal decomposition |
| `rag/` | Document ingestion, chunking, embedding, search |
| `tools/` | Tool framework, registry, executor |
| `security/` | Input sanitization, rate limiting |
| `voice_system/` | STT, TTS, wake word, VAD, streaming |
| `vision/` | OCR, screenshot, UI detection |
| `plugins/` | Plugin SDK, sandbox, permissions |
| `automation/` | Scheduled automation tasks |
| `sync/` | Multi-device synchronization |
| `db/` | SQLAlchemy models, session management |

## Request Lifecycle

1. HTTP request arrives at FastAPI router
2. Authentication middleware validates JWT
3. Rate limiter checks token bucket
4. Input sanitizer cleans content
5. Service logic processes the request
6. LLM calls routed through provider abstraction
7. Tool execution passes through permission checks
8. Response returned to client

## Frontend Architecture

- **State Management**: Riverpod
- **Routing**: GoRouter with ShellRoute
- **Sync**: WebSocket with offline queue
| [Architecture](docs/Architecture.md) | System architecture and design |
| [Setup](docs/Setup.md) | Installation and configuration |
| [Developer Guide](docs/DeveloperGuide.md) | Development workflow |
| [User Guide](docs/UserGuide.md) | End-user documentation |
| [API Reference](docs/API.md) | REST and WebSocket API |
| [Security](docs/Security.md) | Security architecture |
| [Testing](docs/Testing.md) | Testing guidelines |
| [Deployment](docs/Deployment.md) | Production deployment |
| [Memory System](docs/MemorySystem.md) | Memory architecture |
| [Planner](docs/Planner.md) | Planning system |
| [RAG](docs/RAG.md) | RAG system |
| [Voice](docs/Voice.md) | Voice subsystem |
| [Plugin SDK](docs/PluginSDK.md) | Plugin development |
| [Changelog](docs/Changelog.md) | Release history |

## License

MIT License
