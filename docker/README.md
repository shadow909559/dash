# DASH Docker configuration

This directory contains Dockerfiles and related configuration for containerized development and deployment.

## Files

| File | Description |
|------|-------------|
| `backend.Dockerfile` | Multi-stage build for the FastAPI backend |

## Usage

From the repository root:

```bash
docker compose up --build
```

Services:

- **backend** — FastAPI on port 8000
- **postgres** — PostgreSQL 16 on port 5432
- **redis** — Redis 7 on port 6379
