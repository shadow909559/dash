#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== DASH Test Suite ==="

echo -e "\n[1/3] Building JS/TS packages..."
npm install
npm run build

echo -e "\n[2/3] Running Python backend tests..."
BACKEND="$ROOT/apps/backend"
VENV_PYTHON="$BACKEND/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  cd "$BACKEND"
  python3 -m venv .venv
  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -e ".[dev]"
  cd "$ROOT"
fi

"$VENV_PYTHON" -m pytest apps/backend/tests -v

echo -e "\n[3/3] Running Python package tests..."
for pkg in ai-core agents automation memory prompts voice; do
  echo "  Testing $pkg..."
  "$VENV_PYTHON" -m pip install -e "packages/$pkg" -q
  "$VENV_PYTHON" -m pytest "packages/$pkg/tests" -v
done

if command -v flutter >/dev/null 2>&1; then
  echo -e "\n[Optional] Running Flutter tests..."
  cd apps/mobile
  flutter pub get
  flutter analyze
  flutter test
else
  echo -e "\n[Skipped] Flutter not found in PATH"
fi

echo -e "\n=== All tests passed ==="
