# DASH All-in-One Startup Script
Start-Process "C:\Program Files\DASH\DASH.exe"
Start-Sleep 3
Start-Process cmd -ArgumentList "/c ollama serve" -WindowStyle Minimized
Start-Sleep 2
Start-Process cmd -ArgumentList "/c cd /d C:\Users\Asus\Desktop\dash\apps\backend && python -m uvicorn dash_backend.main:app --host 0.0.0.0 --port 8000" -WindowStyle Minimized
