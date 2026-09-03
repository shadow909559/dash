@echo off
REM === DASH Auto-Start Setup ===
REM Run this as Administrator to register all auto-start tasks

echo.
echo ========================================
echo   DASH Auto-Start Setup
echo ========================================
echo.

REM Check for admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Run this as Administrator!
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo [1/4] Registering DASH-AllServices (Backend + Ollama + Desktop + Tunnel)...
schtasks /delete /tn "DASH-AllServices" /f >nul 2>&1
schtasks /create /tn "DASH-AllServices" ^
    /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%USERPROFILE%\AppData\Local\DASH\scripts\start-all.ps1\"" ^
    /sc onlogon ^
    /rl highest ^
    /f
echo       Done.

echo.
echo [2/4] Registering DASH-Backend (backend only, in case all-in-one fails)...
schtasks /delete /tn "DASH-Backend" /f >nul 2>&1
schtasks /create /tn "DASH-Backend" ^
    /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command \"Set-Location 'C:\Users\Asus\Desktop\dash\apps\backend'; Start-Process pythonw '-m uvicorn dash_backend.main:app --host 0.0.0.0 --port 8000' -WindowStyle Hidden\"" ^
    /sc onlogon ^
    /rl highest ^
    /f
echo       Done.

echo.
echo [3/4] Registering DASH-Ollama (Ollama serve)...
schtasks /delete /tn "DASH-Ollama" /f >nul 2>&1
schtasks /create /tn "DASH-Ollama" ^
    /tr "cmd.exe /c start /min ollama serve" ^
    /sc onlogon ^
    /rl highest ^
    /f
echo       Done.

echo.
echo [4/4] Registering DASH-Desktop (Electron app)...
REM Try to find the desktop app
set "DESKTOP_EXE="
if exist "%LOCALAPPDATA%\DASH\dash-desktop.exe" (
    set "DESKTOP_EXE=%LOCALAPPDATA%\DASH\dash-desktop.exe"
) else if exist "%ProgramFiles%\DASH\dash-desktop.exe" (
    set "DESKTOP_EXE=%ProgramFiles%\DASH\dash-desktop.exe"
)
schtasks /delete /tn "DASH-Desktop" /f >nul 2>&1
if defined DESKTOP_EXE (
    schtasks /create /tn "DASH-Desktop" ^
        /tr "\"%DESKTOP_EXE%\"" ^
        /sc onlogon ^
        /rl highest ^
        /f
) else (
    REM Fallback: use npm dev
    schtasks /create /tn "DASH-Desktop" ^
        /tr "cmd.exe /c cd /d C:\Users\Asus\Desktop\dash\apps\desktop && npm run dev" ^
        /sc onlogon ^
        /rl highest ^
        /f
)
echo       Done.

echo.
echo ========================================
echo   All tasks registered!
echo ========================================
echo.
echo Tasks will run on every login:
echo   - DASH-AllServices (main script)
echo   - DASH-Backend (backend backup)
echo   - DASH-Ollama (AI model server)
echo   - DASH-Desktop (desktop app)
echo.
pause
