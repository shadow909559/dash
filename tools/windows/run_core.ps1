# run_core.ps1 — DASH Core startup script
# Runs on boot via DASHCore scheduled task
# Waits for network, then starts backend and verifies health

$LOG_DIR = "$env:LOCALAPPDATA\DASH\logs"
$BACKEND_URL = "http://127.0.0.1:8000/health"
$BACKEND_DIR = "C:\Users\Asus\Desktop\dash\apps\backend"

# Create log directory
New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null

# Wait for network to be ready
Start-Sleep -Seconds 15

# Check if backend is already running
try {
    $response = Invoke-WebRequest -Uri $BACKEND_URL -TimeoutSec 3 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        # Backend already running
        exit 0
    }
} catch {
    # Backend not running — start it
}

# Start the backend
Set-Location $BACKEND_DIR
Start-Process -FilePath "pythonw" -ArgumentList "-m", "uvicorn", "dash_backend.main:app", "--host", "0.0.0.0", "--port", "8000" -WindowStyle Hidden -WorkingDirectory $BACKEND_DIR

# Wait for backend to come up
$timeout = 30
$elapsed = 0
while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds 2
    $elapsed += 2
    try {
        $response = Invoke-WebRequest -Uri $BACKEND_URL -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            exit 0
        }
    } catch {
        continue
    }
}

# If we get here, backend didn't start in time
exit 1
