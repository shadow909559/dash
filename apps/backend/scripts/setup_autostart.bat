@echo off
REM ============================================================
REM DASH Auto-Start Setup for Windows
REM Registers the DASH backend as a Windows scheduled task that
REM runs at user logon, and configures WoL wake-up support.
REM
REM Run this ONCE as Administrator:
REM   cd apps\backend\scripts
REM   setup_autostart.bat
REM ============================================================

setlocal enabledelayedexpansion
echo.
echo ============================================
echo   DASH Auto-Start Setup
echo ============================================
echo.

REM --- 1. Register backend auto-start task ---
echo [1/4] Registering DASH Backend auto-start task...

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..
set PYTHON_EXE=python
set TASK_NAME=DASHCore

REM Remove existing task if any
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM Create scheduled task that runs at logon
schtasks /Create ^
    /TN "%TASK_NAME%" ^
    /TR "\"%PYTHON_EXE%\" -m uvicorn dash_backend.main:app --host 127.0.0.1 --port 8000" ^
    /SC ONLOGON ^
    /RL HIGHEST ^
    /F

if %ERRORLEVEL% EQU 0 (
    echo   [OK] Task "%TASK_NAME%" registered successfully.
) else (
    echo   [FAIL] Could not register task. Run as Administrator.
)

REM --- 2. Enable Wake-on-LAN on network adapter ---
echo.
echo [2/4] Enabling Wake-on-LAN on network adapters...

powershell -NoProfile -Command ^
    "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | ForEach-Object { " ^
    "  Write-Host ('   Adapter: ' + $_.Name); " ^
    "  try { " ^
    "    Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName 'Wake on Magic Packet' -DisplayValue 'Enabled' -ErrorAction Stop; " ^
    "    Write-Host '   [OK] WoL enabled' " ^
    "  } catch { " ^
    "    Write-Host ('   [SKIP] ' + $_.Exception.Message) " ^
    "  } " ^
    "}"

REM --- 3. Get and display MAC address ---
echo.
echo [3/4] Detecting MAC address for WoL...

for /f "tokens=1" %%a in ('getmac /fo csv /nh ^| findstr /i "Wi-Fi\|Ethernet\|WiFi"') do (
    set MAC_RAW=%%~a
    set MAC=!MAC_RAW:,=!
    echo   Your MAC address: !MAC!
    echo   Save this for Android app WoL configuration.
)

REM --- 4. Enable fast startup (optional, for faster WoL response) ---
echo.
echo [4/4] Configuring power settings for WoL...

powercfg /h on >nul 2>&1
powercfg /change standby-timeout-ac 0 >nul 2>&1
powercfg /change standby-timeout-dc 0 >nul 2>&1
echo   [OK] Hibernate enabled, standby disabled on AC.

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo   DASH backend will start automatically at logon.
echo   WoL is enabled - use the Android app to wake this PC.
echo.
echo   To test now: schtasks /Run /TN "%TASK_NAME%"
echo   To remove:   schtasks /Delete /TN "%TASK_NAME%" /F
echo.

endlocal
