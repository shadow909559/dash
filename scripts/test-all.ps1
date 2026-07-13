#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== DASH Test Suite ===" -ForegroundColor Cyan

# JavaScript / TypeScript
Write-Host "`n[1/3] Building JS/TS packages..." -ForegroundColor Yellow
npm install
npm run build

Write-Host "`n[2/3] Running Python backend tests..." -ForegroundColor Yellow
$Backend = Join-Path $Root "apps\backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Set-Location $Backend
    python -m venv .venv
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -e ".[dev]"
    Set-Location $Root
}

& $VenvPython -m pytest apps/backend/tests -v

Write-Host "`n[3/3] Running Python package tests..." -ForegroundColor Yellow
$Packages = @("ai-core", "agents", "automation", "memory", "prompts", "voice")
foreach ($Pkg in $Packages) {
    $PkgPath = Join-Path $Root "packages\$Pkg"
    Write-Host "  Testing $Pkg..."
    & $VenvPython -m pip install -e $PkgPath -q
    & $VenvPython -m pytest (Join-Path $PkgPath "tests") -v
}

# Flutter (if available)
$Flutter = Get-Command flutter -ErrorAction SilentlyContinue
if ($Flutter) {
    Write-Host "`n[Optional] Running Flutter tests..." -ForegroundColor Yellow
    Set-Location (Join-Path $Root "apps\mobile")
    flutter pub get
    flutter analyze
    flutter test
    Set-Location $Root
} else {
    Write-Host "`n[Skipped] Flutter not found in PATH" -ForegroundColor DarkGray
}

Write-Host "`n=== All tests passed ===" -ForegroundColor Green
