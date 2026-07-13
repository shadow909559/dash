#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/apps/backend"
VENV_PYTHON="$BACKEND/.venv/bin/python"

cd "$BACKEND"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -e ".[dev]"
fi

echo "Starting DASH backend on http://localhost:8000"
exec "$VENV_PYTHON" -m uvicorn dash_backend.main:app --reload --host 0.0.0.0 --port 8000
