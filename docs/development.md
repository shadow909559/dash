# Development Guide

## Environment Setup

1. Copy `.env.example` to `.env`
2. Install Node.js 20+ and Python 3.11+
3. Install Flutter 3.24+ for mobile development

## Backend

```powershell
cd apps\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn dash_backend.main:app --reload
```

## Desktop

```powershell
npm install
npm run dev:desktop
```

## Mobile

```powershell
cd apps\mobile
flutter pub get
flutter run
```

## Python Packages

Each package under `packages/` can be installed independently:

```powershell
pip install -e packages/ai-core
pip install -e packages/agents
```

## Linting and Formatting

```powershell
# JavaScript / TypeScript
npm run lint
npm run format:check

# Python
ruff check apps/backend packages tests
black --check apps/backend packages tests
```

## Testing

```powershell
scripts\test-all.ps1
```
