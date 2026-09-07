# start-all.ps1 - Single entry point for all DASH background services
# Replaces: DASHCore, DASH-Watchdog, DASH-AutoConnect, DASH-Ollama, DASH-Ollama-Tunnel, DASH-Tunnel
# Runs hidden via powershell.exe -WindowStyle Hidden

$scriptDir = "$env:LOCALAPPDATA\DASH\scripts"
$logDir = "$env:LOCALAPPDATA\DASH\logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Start-ServiceSilent {
    param([string]$Name, [scriptblock]$Action)
    try {
        & $Action
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] $Name started"
    } catch {
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] $Name failed: $_"
    }
}

# Wait for network
Start-Sleep -Seconds 10

# 1. Backend (the critical one - must start first)
$backendRunning = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $backendRunning = $true }
} catch {}

if (-not $backendRunning) {
    Set-Location "C:\Users\Asus\Desktop\dash\apps\backend"
    Start-Process -FilePath "pythonw" -ArgumentList "-m", "uvicorn", "dash_backend.main:app", "--host", "0.0.0.0", "--port", "8000" -WindowStyle Hidden
    # Wait for backend to come up
    $elapsed = 0
    while ($elapsed -lt 30) {
        Start-Sleep -Seconds 2
        $elapsed += 2
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $backendRunning = $true; break }
        } catch { continue }
    }
}

# 2. Ollama (if installed)
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaPath) {
    $ollamaRunning = Get-Process ollama -ErrorAction SilentlyContinue
    if (-not $ollamaRunning) {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    }
}

# 3. Wait for Ollama to be ready before starting tunnel
Start-Sleep -Seconds 15

# 4. Cloudflare tunnel (if cloudflared exists)
$cloudflared = "$env:LOCALAPPDATA\DASH\cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    $cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
}
if ($cloudflared) {
    $tunnelRunning = Get-Process cloudflared -ErrorAction SilentlyContinue
    if (-not $tunnelRunning) {
        Start-Process -FilePath $cloudflared -ArgumentList "tunnel", "--url", "http://localhost:11434" -WindowStyle Hidden
    }
}

# 5. Watchdog (if script exists)
if (Test-Path "$scriptDir\watchdog.py") {
    $watchdogRunning = Get-Process python* | Where-Object { $_.CommandLine -like "*watchdog*" }
    if (-not $watchdogRunning) {
        Start-Process -FilePath "pythonw" -ArgumentList "$scriptDir\watchdog.py" -WindowStyle Hidden
    }
}

# 6. Auto-connect (if script exists)
if (Test-Path "$scriptDir\auto-connect.py") {
    $autoConnectRunning = Get-Process python* | Where-Object { $_.CommandLine -like "*auto-connect*" }
    if (-not $autoConnectRunning) {
        Start-Process -FilePath "pythonw" -ArgumentList "$scriptDir\auto-connect.py" -WindowStyle Hidden
    }
}
