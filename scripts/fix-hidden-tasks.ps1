# One-shot (run as admin): rewrite the two DASH logon tasks that open visible terminals.
# 1) DASH-Ollama     - was: cmd.exe /c start /min ollama serve (console stays open all session)
# 2) DASH-AllServices - was: bare powershell.exe (console flashes at every logon)
# Both now launch through run-hidden.vbs (wscript, windowless).

$vbs = 'C:\Users\Asus\AppData\Local\DASH\scripts\run-hidden.vbs'

$a1 = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + $vbs + '" "cmd /c ollama serve"')
Set-ScheduledTask -TaskName 'DASH-Ollama' -Action $a1 | Out-Null
Write-Output 'OLLAMA_OK'

$a2 = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + $vbs + '" "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Users\Asus\AppData\Local\DASH\scripts\start-all.ps1"')
Set-ScheduledTask -TaskName 'DASH-AllServices' -Action $a2 | Out-Null
Write-Output 'ALLSERVICES_OK'

Get-ScheduledTask | Where-Object { $_.TaskName -like 'DASH*' } | ForEach-Object {
    $a = ($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' | '
    Write-Output ($_.TaskName + ' :: ' + $a)
}
