@echo off
REM DASH Backend — starts FastAPI server on boot (runs hidden via run-hidden.vbs)
REM Uses the full pythonw path (bare pythonw resolves to the Store stub
REM which does nothing in non-interactive / scheduled-task sessions).
REM No "start" wrapper — run-hidden.vbs already runs this non-blocking.

timeout /t 10 /nobreak > nul
mkdir "%LOCALAPPDATA%\DASH\logs" 2> nul

cd /d "C:\Users\Asus\Desktop\dash\apps\backend"
"C:\Users\Asus\AppData\Local\Python\bin\pythonw.exe" -m uvicorn dash_backend.main:app --host 0.0.0.0 --port 8000 >> "%LOCALAPPDATA%\DASH\logs\backend.log" 2>&1