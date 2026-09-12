@echo off
REM One-shot: rewrite the two DASH logon tasks that visibly open terminals.
REM 1) DASH-Ollama  - was: cmd.exe /c start /min ollama serve (console stays open all session)
REM 2) DASH-AllServices - was: bare powershell.exe (console flashes at every logon)
REM Both now launch through run-hidden.vbs (wscript, windowless).

schtasks /Change /TN "DASH-Ollama" /TR "wscript.exe \"C:\Users\Asus\AppData\Local\DASH\scripts\run-hidden.vbs\" \"cmd /c ollama serve\""
echo OLLAMA_EXIT=%ERRORLEVEL%

schtasks /Change /TN "DASH-AllServices" /TR "wscript.exe \"C:\Users\Asus\AppData\Local\DASH\scripts\run-hidden.vbs\" \"powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Users\Asus\AppData\Local\DASH\scripts\start-all.ps1\""
echo ALLSERVICES_EXIT=%ERRORLEVEL%

powershell -NoProfile -Command "Get-ScheduledTask | Where-Object {$_.TaskName -like 'DASH*'} | ForEach-Object { $a = ($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' | '; Write-Output ($_.TaskName + ' :: ' + $a) }"
