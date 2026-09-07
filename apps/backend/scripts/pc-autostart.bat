@echo off
REM ============================================================
REM DASH PC Auto-Start — Cloud Connectivity
REM Run this ONCE as Administrator to register as startup task.
REM
REM What it does on every boot:
REM   1. Starts Ollama (local AI)
REM   2. Starts Cloudflare tunnel (exposes Ollama to cloud)
REM   3. Registers WoL listener (wake PC from cloud)
REM   4. Starts DASH backend (optional, for local access)
REM ============================================================

setlocal enabledelayedexpansion

echo === DASH PC Auto-Start Setup ===
echo.
echo This script sets up your PC to be remotely accessible from the
echo DASH cloud backend and Android app.
echo.
echo Requirements:
echo   - Ollama installed and running
echo   - cloudflared installed
echo   - Run as Administrator
echo.

REM Step 1: Check prerequisites
echo [1/4] Checking prerequisites...

where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Ollama not found in PATH
    echo Install from: https://ollama.ai
    echo.
)

where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: cloudflared not found in PATH
    echo Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo.
)

REM Step 2: Create startup script
echo [2/4] Creating startup script...

set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set DASH_SCRIPT=%STARTUP_DIR%\dash-cloud-connect.bat

(
echo @echo off
echo REM DASH Cloud Connection — Auto-started on boot
echo REM Started at %date% %time%
echo.
echo REM Wait for network
echo timeout /t 10 /nobreak ^> nul
echo.
echo REM Start Ollama if not running
echo tasklist /FI "IMAGENAME eq ollama.exe" 2^>nul ^| find /I "ollama.exe" ^> nul
echo if errorlevel 1 ^(
echo     echo Starting Ollama...
echo     start "" "ollama" serve
echo     timeout /t 5 /nobreak ^> nul
echo ^)
echo.
echo REM Start Cloudflare tunnel for Ollama
echo echo Starting Cloudflare tunnel...
echo start "" cloudflared tunnel --url http://localhost:11434
echo.
echo REM Log the tunnel URL (check cloudflared output for URL)
echo echo DASH cloud connection started at %date% %time%
echo echo Check the cloudflared window for the tunnel URL
echo echo Then set it on Fly.io: flyctl secrets set OLLAMA_BASE_URL="^<url^>" --app dash-backend
) > "%DASH_SCRIPT%"

echo   Created: %DASH_SCRIPT%

REM Step 3: Create scheduled task for WoL listener
echo [3/4] Setting up Wake-on-LAN listener...

schtasks /create /tn "DASH-WoL-Listener" /tr "pythonw %~dp0wol-listener.py" /sc onlogon /rl highest /f >nul 2>&1
if %errorlevel% equ 0 (
    echo   WoL listener task created
) else (
    echo   WARNING: Could not create WoL task (run as Admin)
)

REM Step 4: Enable Wake-on-LAN in Windows
echo [4/4] Configuring Wake-on-LAN...

REM Enable WoL on all network adapters
for /f "tokens=*" %%a in ('powershell -Command "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty Name"') do (
    powershell -Command "Set-NetAdapterAdvancedProperty -Name '%%a' -DisplayName 'Wake on Magic Packet' -DisplayValue 'Enabled'" >nul 2>&1
    powershell -Command "Set-NetAdapterAdvancedProperty -Name '%%a' -DisplayName 'Wake on Pattern Match' -DisplayValue 'Enabled'" >nul 2>&1
)

REM Enable fast startup (faster boot for WoL)
powercfg /h on >nul 2>&1

echo.
echo === Setup Complete ===
echo.
echo Your PC will now:
echo   - Start Ollama on boot
echo   - Open Cloudflare tunnel for Ollama
echo   - Listen for Wake-on-LAN packets
echo.
echo To get the tunnel URL, check the cloudflared window after boot.
echo Then run on Fly.io:
echo   flyctl secrets set OLLAMA_BASE_URL="https://xxx.trycloudflare.com" --app dash-backend
echo.
echo To test WoL from another device:
echo   wakeonlan YOUR_PC_MAC_ADDRESS
echo.
pause
