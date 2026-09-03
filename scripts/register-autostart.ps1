# DASH Auto-Start Registration (run as admin)
# Registers all DASH services to start on every login

Write-Host "Registering DASH auto-start tasks..." -ForegroundColor Cyan

# 1. DASH-AllServices — the main startup script
schtasks /delete /tn "DASH-AllServices" /f 2>$null
schtasks /create /tn "DASH-AllServices" `
    /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$env:LOCALAPPDATA\DASH\scripts\start-all.ps1`"" `
    /sc onlogon /rl highest /f
Write-Host "  [OK] DASH-AllServices" -ForegroundColor Green

# 2. DASH-Backend — backup in case all-in-one fails
schtasks /delete /tn "DASH-Backend" /f 2>$null
schtasks /create /tn "DASH-Backend" `
    /tr "cmd.exe /c cd /d C:\Users\Asus\Desktop\dash\apps\backend && start /min pythonw -m uvicorn dash_backend.main:app --host 0.0.0.0 --port 8000" `
    /sc onlogon /rl highest /f
Write-Host "  [OK] DASH-Backend" -ForegroundColor Green

# 3. DASH-Ollama — AI model server
schtasks /delete /tn "DASH-Ollama" /f 2>$null
schtasks /create /tn "DASH-Ollama" `
    /tr "cmd.exe /c start /min ollama serve" `
    /sc onlogon /rl highest /f
Write-Host "  [OK] DASH-Ollama" -ForegroundColor Green

# 4. DASH-Desktop — Electron app
schtasks /delete /tn "DASH-Desktop" /f 2>$null
schtasks /create /tn "DASH-Desktop" `
    /tr "cmd.exe /c cd /d C:\Users\Asus\Desktop\dash\apps\desktop && npm run dev" `
    /sc onlogon /rl highest /f
Write-Host "  [OK] DASH-Desktop" -ForegroundColor Green

Write-Host ""
Write-Host "All 4 tasks registered! They will start on every login." -ForegroundColor Green
Write-Host ""
Write-Host "Tasks:" -ForegroundColor Yellow
Get-ScheduledTask | Where-Object { $_.TaskName -like "DASH-*" } | 
    Select-Object TaskName, State | Format-Table -AutoSize
