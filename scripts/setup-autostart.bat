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
REM Wrapped in wscript run-hidden: even with -WindowStyle Hidden, Task Scheduler
REM briefly flashes a conhost window for console hosts — the VBS wrapper hides it fully.
schtasks /create /tn "DASH-AllServices" ^
    /tr "wscript.exe \"%USERPROFILE%\AppData\Local\DASH\scripts\run-hidden.vbs\" \"powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File %USERPROFILE%\AppData\Local\DASH\scripts\start-all.ps1\"" ^
    /sc onlogon ^
    /rl highest ^
    /f
echo       Done.

echo.
echo [2/4] Registering DASH-Backend (backend only, in case all-in-one fails)...
schtasks /delete /tn "DASH-Backend" /f >nul 2>&1
schtasks /create /tn "DASH-Backend" ^
    /tr "wscript.exe \"%USERPROFILE%\AppData\Local\DASH\scripts\run-hidden.vbs\" \"%USERPROFILE%\AppData\Local\DASH\scripts\backend-startup.bat\"" ^
    /sc onlogon ^
    /f
echo       Done.

echo.
echo [3/4] Registering DASH-Ollama (Ollama serve)...
schtasks /delete /tn "DASH-Ollama" /f >nul 2>&1
REM Was: cmd.exe /c start /min ollama serve — that left a minimized console
REM window open for the entire session. The VBS wrapper runs serve with no window.
schtasks /create /tn "DASH-Ollama" ^
    /tr "wscript.exe \"%USERPROFILE%\AppData\Local\DASH\scripts\run-hidden.vbs\" \"cmd /c ollama serve\"" ^
    /sc onlogon ^
    /rl highest ^
    /f
echo       Done.

echo.
echo [4/4] Registering DASH-Desktop (Electron app)...
REM Try to find the desktop app
set "DESKTOP_EXE="
if exist "%ProgramFiles%\DASH\DASH.exe" (
    set "DESKTOP_EXE=%ProgramFiles%\DASH\DASH.exe"
) else if exist "%LOCALAPPDATA%\DASH\DASH.exe" (
    set "DESKTOP_EXE=%LOCALAPPDATA%\DASH\DASH.exe"
) else if exist "%LOCALAPPDATA%\DASH\dash-desktop.exe" (
    set "DESKTOP_EXE=%LOCALAPPDATA%\DASH\dash-desktop.exe"
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
