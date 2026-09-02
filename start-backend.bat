@echo off
cd /d C:\Users\Asus\Desktop\dash\apps\backend
python -m uvicorn dash_backend.main:app --host 0.0.0.0 --port 8000
