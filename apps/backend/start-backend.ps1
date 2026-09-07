Set-Location "C:\Users\Asus\Desktop\dash\apps\backend"
Start-Process pythonw -ArgumentList "-m uvicorn dash_backend.main:app --host 0.0.0.0 --port 8000" -WindowStyle Hidden
