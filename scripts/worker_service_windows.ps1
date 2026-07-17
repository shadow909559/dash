# Example PowerShell script to register the Executive worker as a Windows service using NSSM
# Prerequisites: NSSM (https://nssm.cc/) installed and in PATH

$serviceName = "DashExecutiveWorker"
$pythonExe = "C:\\Python39\\python.exe"  # adjust path to Python
$scriptPath = "C:\\Users\\Asus\\Desktop\\dash\\apps\\backend\\dash_backend\\executive\\worker.py"

# Install service using NSSM
nssm install $serviceName $pythonExe "-u `"$scriptPath`""
# Set working directory
nssm set $serviceName AppDirectory "C:\\Users\\Asus\\Desktop\\dash"
# Set stdout/stderr
nssm set $serviceName AppStdout "C:\\Users\\Asus\\Desktop\\dash\\logs\\worker_stdout.log"
nssm set $serviceName AppStderr "C:\\Users\\Asus\\Desktop\\dash\\logs\\worker_stderr.log"

Write-Host "Installed service $serviceName via NSSM. Start it with: nssm start $serviceName"