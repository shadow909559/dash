# DASH

Production-grade AI desktop assistant monorepo.

## Overview

DASH is a cross-platform AI assistant with:

- **Desktop** — Electron + React + TypeScript
- **Mobile** — Flutter
- **Backend** — FastAPI + PostgreSQL + Redis
- **Packages** — Shared libraries for AI, agents, automation, memory, voice, and more

This repository contains the **foundation milestone** only: project structure, configuration, and minimal scaffolds. No authentication, AI, database models, or business logic yet.

## Repository Structure

```
apps/
  backend/     FastAPI backend
  desktop/     Electron desktop app
  mobile/      Flutter mobile app
packages/
  ai-core/     AI orchestration (scaffold)
  agents/      Agent framework (scaffold)
  automation/  Browser & computer automation (scaffold)
  memory/      Memory system (scaffold)
  prompts/     Prompt templates (scaffold)
  sdk/         TypeScript client SDK (scaffold)
  shared/      Shared types and constants
  voice/       Voice processing (scaffold)
docker/        Dockerfiles and compose helpers
docs/          Documentation
scripts/       Development and CI scripts
tests/         Cross-package integration tests
```

## Prerequisites

- **Node.js** >= 20
- **Python** >= 3.11
- **Flutter** >= 3.24 (for mobile)
- **Docker** & Docker Compose (optional, for containerized development)

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
```

### 2. Backend

```bash
cd apps/backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
uvicorn dash_backend.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

WebSocket: `ws://localhost:8000/api/v1/ws`

### 3. Desktop

```bash
npm install
npm run dev:desktop
```

### 4. Mobile

```bash
cd apps/mobile
flutter pub get
flutter analyze
flutter run
```

### 5. Docker (full stack)

```bash
docker compose up --build
```

## Development Scripts

| Script | Description |
|--------|-------------|
| `npm run build` | Build all JS/TS workspaces |
| `npm run lint` | Lint all JS/TS workspaces |
| `npm run format` | Format with Prettier |
| `scripts/dev-backend.ps1` | Start backend (Windows) |
| `scripts/dev-backend.sh` | Start backend (Unix) |
| `scripts/test-all.ps1` | Run all tests (Windows) |
| `scripts/test-all.sh` | Run all tests (Unix) |

## Python Tooling

From the repository root:

```bash
pip install ruff black pytest pytest-asyncio httpx mypy
ruff check apps/backend packages tests
black --check apps/backend packages tests
pytest
```

## License

Proprietary — All rights reserved.
