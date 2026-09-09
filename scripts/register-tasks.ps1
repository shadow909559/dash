# register-tasks.ps1 — Registers all DASH auto-start scheduled tasks
# Run as Administrator.

$scripts = "$env:LOCALAPPDATA\DASH\scripts"
$vbs = "$scripts\run-hidden.vbs"

function Register-DashTask {
    param(
        [string]$Name,
        [string]$Execute,
        [string]$Argument
    )
    try {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
        $action = New-ScheduledTaskAction -Execute $Execute -Argument $Argument
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
        Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Force -ErrorAction Stop | Out-Null
        Write-Output "OK: $Name"
    } catch {
        Write-Output "FAIL: $Name -> $($_.Exception.Message)"
    }
}

# 1. DASH-Backend — FastAPI server via hidden bat
Register-DashTask -Name "DASH-Backend" -Execute "wscript.exe" -Argument "`"$vbs`" `"$scripts\backend-startup.bat`""

# 2. DASH-Ollama — Ollama serve at logon
Register-DashTask -Name "DASH-Ollama" -Execute "cmd.exe" -Argument "/c start /min ollama serve"

# 3. DASH-Desktop — desktop app hidden (tray)
Register-DashTask -Name "DASH-Desktop" -Execute "`"C:\Program Files\DASH\DASH.exe`"" -Argument "--hidden"

# 4. DASH-Watchdog — service monitor via hidden bat
Register-DashTask -Name "DASH-Watchdog" -Execute "wscript.exe" -Argument "`"$vbs`" `"$scripts\watchdog-startup.bat`""

# 5. DASH-AutoConnect — cloud relay registration via hidden bat
Register-DashTask -Name "DASH-AutoConnect" -Execute "wscript.exe" -Argument "`"$vbs`" `"$scripts\auto-connect-startup.bat`""

Write-Output ""
Write-Output "=== Verification ==="
Get-ScheduledTask -TaskName "DASH-*" | Select-Object TaskName, State | Format-Table -AutoSize