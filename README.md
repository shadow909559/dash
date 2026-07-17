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

## Production deployment (recommended starter steps)

These are minimal, safe deployment steps and guidelines to get Dash running in a production environment. They are intentionally conservative and avoid embedding secrets in the repository.

1) Prepare environment and secrets

- Copy the example env and populate secrets from a secrets manager or environment injection system (do NOT commit secrets):

  ```bash
  cp .env.example .env
  # Edit .env, set DATABASE_URL/JWT_SECRET/PROVIDER_* keys, POSTGRES_*, etc.
  ```

2) Run database migrations

- From the backend directory run Alembic to apply schema changes:

  ```bash
  cd apps/backend
  # activate your virtualenv first
  alembic upgrade head
  ```

3) Start production stack (compose template)

- A production compose template is provided at docker-compose.prod.yml (fill in env via env_file or a secrets manager). This is a starting point; adapt to your orchestration (Docker Swarm / Kubernetes / ECS):

  ```bash
  docker compose -f docker-compose.prod.yml up -d --build
  ```

4) Healthcheck

- Verify health endpoint: http://<host>:8000/api/v1/health

5) Backups (Postgres)

- Create regular backups with pg_dump. Example daily dump:

  ```bash
  PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h <db-host> -U $POSTGRES_USER -F c -b -v -f "dash_backup_$(date +%F).dump" $POSTGRES_DB
  ```

- Restore example:

  ```bash
  pg_restore -h <db-host> -U $POSTGRES_USER -d $POSTGRES_DB -v "dash_backup_2024-01-01.dump"
  ```

6) Notes & recommendations

- Do NOT run with DEBUG=True in production. Ensure JWT secrets and provider keys are securely injected.
- For rate limiting and distributed locking, use Redis or an API gateway- level rate limiter instead of process-local limits.
- For embedding-heavy workloads, consider offloading embedding generation to a background worker and a job queue.
- For multi-instance deployments, prefer a centralized database and Redis for shared state.

7) Run the CI-style checks locally

- Useful quick checks that CI should run (see .github/workflows if present):

  ```bash
  # from repo root
  python -m py_compile $(git ls-files "**/*.py") || true
  pytest -q
  docker build -t dash-backend:local apps/backend
  ```

If you use a different deployment strategy (k8s, cloud services, or a managed Postgres), adapt the deployment steps accordingly. These instructions are intentionally brief to avoid enforcing a single deployment approach.
