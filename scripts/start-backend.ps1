# DASH Backend auto-start — uses full pythonw path (bare pythonw resolves to
# the Store stub which is inert in non-interactive sessions)
Set-Location "C:\Users\Asus\Desktop\dash\apps\backend"
Start-Process "C:\Users\Asus\AppData\Local\Python\bin\pythonw.exe" -ArgumentList "-m uvicorn dash_backend.main:app --host 0.0.0.0 --port 8000" -WindowStyle Hidden