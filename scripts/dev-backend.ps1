#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "apps\backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

Set-Location $Backend

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -e ".[dev]"
}

Write-Host "Starting DASH backend on http://localhost:8000"
& $VenvPython -m uvicorn dash_backend.main:app --reload --host 0.0.0.0 --port 8000
