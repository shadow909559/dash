# DASH RC1 — Release Checklist

## Pre-Release Verification

- [x] **All features implemented** (Phases 1-13 complete)
- [x] **Security audit passed** (39/39 findings resolved)
- [x] **Performance benchmarks collected** (Phase 12)

## 1. Remove Debug Code

- [x] Backend `main.py`: Docs/redoc/openapi disabled in production (`docs_url=None`, `redoc_url=None`, `openapi_url=None`)
- [x] Backend: `debug=False` by default in config
- [x] Backend: `log_level=INFO` by default, not DEBUG
- [x] Backend: DevTools only opens with `VITE_DEV_SERVER_URL` in dev mode
- [x] Desktop: `DevTools` only in dev mode
- [x] Desktop: `console.log` statements reduced to production-safe level
- [x] No `print()` statements remain in production code paths

## 2. Remove Development Logs

- [x] Backend `logging_config.py`: `uvicorn.access` set to `WARNING` level
- [x] Redaction filter active on all log output
- [x] No `logger.debug()` in hot code paths (only in error handling)
- [x] Audit logs use structured JSONL format, not debug formatting

## 3. Verify Windows Installer

- [x] `package.json`: electron-builder configured for Windows NSIS
  - `oneClick: false` — allows custom install directory
  - `allowToChangeInstallationDirectory: true`
  - Desktop shortcut: enabled
  - Start Menu shortcut: enabled
- [x] `extraResources` includes `apps/backend` folder (Python backend bundled)
- [x] Backend auto-starts via `BackendManager` on app launch

## 4. Verify Electron Packaging

- [x] `files` config includes: `dist/**/*`, `dist-electron/**/*`, `backend/**/*`
- [x] `appId: com.dash.desktop`
- [x] `productName: DASH`
- [x] Build output directory: `release/`

## 5. Verify Backend Auto-Start

- [x] `BackendManager` spawns Python process on `app.whenReady()`
- [x] Health check pings `http://127.0.0.1:8000/health` every 5 seconds
- [x] Auto-restart on crash (exponential backoff, max 5 attempts)
- [x] Graceful shutdown via SIGTERM → SIGKILL after 5s timeout
- [x] Python path detection for common Windows installs

## 6. Verify Updater

- [x] `electron-updater` configured with GitHub provider
- [x] Repository: `shadow909559/dash`
- [x] `autoDownload: false` — user triggers download
- [x] `autoInstallOnAppQuit: false` — user triggers install
- [x] IPC handlers: `status`, `check`, `download`, `install`
- [x] Desktop notification on update available/downloaded
- [x] Dev mode check prevents update checks in development

## 7. Verify Android Release Build

- [x] Flutter project configured at `apps/mobile/`
- [x] Android manifest: internet permission, WebSocket support
- [x] API client: points to configurable backend URL
- [x] WebSocket reconnection: exponential backoff
- [x] Error recovery service: retry logic for failed API calls

## 8. Verify Settings Migration

- [x] Backend config loaded from environment variables (`.env` or system)
- [x] Pydantic `SettingsConfigDict` with `env_prefix="DASH_"`
- [x] Migration path: SQLAlchemy Alembic migrations in `alembic/`
- [x] No hardcoded paths in production code

## 9. Verify Crash Recovery

- [x] Backend: `lifespan` handler for startup/shutdown
- [x] Backend: `pool_pre_ping=True` for DB connection recovery
- [x] Desktop: Single instance lock prevents duplicate launches
- [x] Desktop: Backend auto-restart on crash
- [x] Desktop: Memory cleanup runs every 5 minutes
- [x] WebSocket: Reconnect with exponential backoff (max 10 attempts)
- [x] WebSocket: Auto-reconnect timer on disconnect

## 10. Verify Backups

- [x] Docker Compose with persistent PostgreSQL volume (`postgres_data`)
- [x] Audit logs: JSONL files with auto-rotation at 10MB
- [x] No in-memory-only state for critical data

## Production Configuration

- [x] `DASH_JWT_SECRET_KEY` must be set (runtime error if missing in production)
- [x] `DASH_ENV=production` disables debug endpoints
- [x] `DASH_CORS_ORIGINS` must not contain `*` in production (runtime error)
- [x] `DASH_DATABASE_URL` must point to PostgreSQL, not SQLite
- [x] `DASH_LOG_LEVEL=INFO` or `WARNING` in production

## Docker Production Deployment

```bash
docker compose -f docker-compose.prod.yml up -d
```

This starts:
- PostgreSQL 15 (persistent volume)
- Redis 7 (alpine)
- DASH Backend (production build)
- Nginx frontend server

## RC1 Build Command

```bash
cd apps/desktop
npm run dist
```

Output: `apps/desktop/release/DASH Setup 1.0.0.exe`

