@echo off
REM ============================================================
REM DASH Auto-Start Installer
REM Run ONCE as Administrator to install all services.
REM After this, everything starts automatically on boot.
REM ============================================================

setlocal enabledelayedexpansion

echo ╔══════════════════════════════════════════╗
echo ║   DASH Auto-Start Installer             ║
echo ╚══════════════════════════════════════════╝
echo.
echo This will install:
echo   1. Ollama (auto-start on boot)
echo   2. Cloudflare tunnel (auto-start on boot)
echo   3. DASH auto-connect (auto-start on boot)
echo   4. Desktop control service (auto-start on boot)
echo   5. Watchdog (auto-restart if anything crashes)
echo.
echo Run as Administrator!
echo.

REM === Check for admin ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Run this as Administrator!
    echo Right-click the file and select "Run as administrator"
    pause
    exit /b 1
)

REM === Create DASH directory ===
echo [1/6] Creating directories...
set DASH_DIR=%LOCALAPPDATA%\DASH
set DASH_SCRIPTS=%DASH_DIR%\scripts
set DASH_LOGS=%DASH_DIR%\logs
mkdir "%DASH_DIR%" 2>nul
mkdir "%DASH_SCRIPTS%" 2>nul
mkdir "%DASH_LOGS%" 2>nul
echo   Created: %DASH_DIR%

REM === Copy scripts ===
echo [2/6] Installing scripts...
copy /Y "%~dp0auto-connect.py" "%DASH_SCRIPTS%\auto-connect.py" >nul
copy /Y "%~dp0watchdog.py" "%DASH_SCRIPTS%\watchdog.py" >nul
copy /Y "%~dp0service-manager.py" "%DASH_SCRIPTS%\service-manager.py" >nul
echo   Scripts installed to %DASH_SCRIPTS%

REM === Install Ollama auto-start ===
echo [3/6] Setting up Ollama auto-start...
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    REM Create scheduled task for Ollama
    schtasks /create /tn "DASH-Ollama" /tr "ollama serve" /sc onlogon /rl highest /f >nul 2>&1
    echo   ✓ Ollama auto-start task created
) else (
    echo   ⚠ Ollama not found. Install from https://ollama.ai
    echo     Then run this installer again.
)

REM === Install Cloudflare tunnel auto-start ===
echo [4/6] Setting up Cloudflare tunnel auto-start...
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    REM Create batch file for tunnel
    (
        echo @echo off
        echo REM DASH Ollama Tunnel — auto-started on boot
        echo timeout /t 15 /nobreak ^> nul
        echo REM Wait for Ollama to start
        echo :loop
        echo cloudflared tunnel --url http://localhost:11434 ^> "%DASH_LOGS%\tunnel.log" 2^>^&1
        echo REM Restart if crashed
        echo timeout /t 5 /nobreak ^> nul
        echo goto loop
    ) > "%DASH_SCRIPTS%\ollama-tunnel.bat"

    schtasks /create /tn "DASH-Ollama-Tunnel" /tr "\"%DASH_SCRIPTS%\ollama-tunnel.bat\"" /sc onlogon /rl highest /f >nul 2>&1
    echo   ✓ Ollama tunnel auto-start task created
) else (
    echo   ⚠ cloudflared not found. Install with:
    echo     winget install Cloudflare.cloudflared
)

REM === Install auto-connect ===
echo [5/6] Setting up DASH auto-connect...
(
    echo @echo off
    echo REM DASH Auto-Connect — auto-started on boot
    echo timeout /t 30 /nobreak ^> nul
    echo REM Wait for network + Ollama + tunnel
    echo cd /d "%DASH_SCRIPTS%"
    echo python auto-connect.py ^> "%DASH_LOGS%\auto-connect.log" 2^>^&1
) > "%DASH_SCRIPTS%\auto-connect-startup.bat"

schtasks /create /tn "DASH-AutoConnect" /tr "\"%DASH_SCRIPTS%\auto-connect-startup.bat\"" /sc onlogon /rl highest /f >nul 2>&1
echo   ✓ Auto-connect task created

REM === Install watchdog ===
echo [6/6] Setting up watchdog (auto-restart)...
(
    echo @echo off
    echo REM DASH Watchdog — monitors all services, restarts on crash
    echo cd /d "%DASH_SCRIPTS%"
    echo python watchdog.py ^> "%DASH_LOGS%\watchdog.log" 2^>^&1
) > "%DASH_SCRIPTS%\watchdog-startup.bat"

schtasks /create /tn "DASH-Watchdog" /tr "\"%DASH_SCRIPTS%\watchdog-startup.bat\"" /sc onlogon /rl highest /f >nul 2>&1
echo   ✓ Watchdog task created

REM === Create startup shortcut ===
echo.
echo Creating desktop shortcut...
set SHORTCUT=%USERPROFILE%\Desktop\DASH Auto-Start.lnk
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = 'schtasks'; $s.Arguments = '/run /tn DASH-Ollama /tn DASH-Ollama-Tunnel /tn DASH-AutoConnect /tn DASH-Watchdog'; $s.WorkingDirectory = '%DASH_DIR%'; $s.Description = 'Start all DASH services'; $s.Save()"

echo.
echo ╔══════════════════════════════════════════╗
echo ║   Installation Complete!                ║
echo ╚══════════════════════════════════════════╝
echo.
echo All services will auto-start on next boot.
echo.
echo Installed services:
echo   ✓ DASH-Ollama        — Local AI (auto-start)
echo   ✓ DASH-Ollama-Tunnel — Cloud tunnel (auto-start)
echo   ✓ DASH-AutoConnect   — Cloud registration (auto-start)
echo   ✓ DASH-Watchdog      — Crash recovery (auto-start)
echo.
echo Logs: %DASH_LOGS%
echo.
echo To test now, run:
echo   schtasks /run /tn DASH-Ollama
echo   schtasks /run /tn DASH-Ollama-Tunnel
echo   schtasks /run /tn DASH-AutoConnect
echo.
echo Or double-click "DASH Auto-Start" on your desktop.
echo.
pause
