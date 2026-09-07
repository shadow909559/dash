@echo off
REM === Cloudflare Tunnel Setup for DASH ===
REM Exposes local backend to internet for free (replaces EC2)
REM No credit card required

echo.
echo ========================================
echo   Cloudflare Tunnel Setup for DASH
echo ========================================
echo.

REM Check if cloudflared is installed
where cloudflared >nul 2>&1
if %errorLevel% neq 0 (
    echo [1/3] Downloading cloudflared...
    echo.
    echo Please download cloudflared from:
    echo   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo.
    echo Or run in PowerShell (as admin):
    echo   winget install Cloudflare.cloudflared
    echo.
    echo After installing, run this script again.
    pause
    exit /b 1
)

echo [2/3] cloudflared found!
echo.

REM Check if already logged in
cloudflared tunnel list >nul 2>&1
if %errorLevel% neq 0 (
    echo [3/3] Logging into Cloudflare...
    echo.
    echo A browser window will open. Sign in with your Cloudflare account.
    echo If you don't have one, create one for free at https://dash.cloudflare.com
    echo.
    cloudflared tunnel login
)

echo.
echo ========================================
echo   Creating DASH tunnel...
echo ========================================
echo.

REM Create tunnel
cloudflared tunnel create dash-backend 2>nul
if %errorLevel% neq 0 (
    echo Tunnel 'dash-backend' already exists, using existing one.
)

REM Route DNS
echo Routing tunnel to dash.yourdomain.com...
echo.
echo NOTE: You need a domain on Cloudflare for this to work.
echo If you have a domain, run:
echo   cloudflared tunnel route dns dash-backend dash.yourdomain.com
echo.
echo If you don't have a domain, use the free trycloudflare URL:
echo   cloudflared tunnel --url http://localhost:8000
echo.

REM Quick start - free temporary URL
echo Starting tunnel with free temporary URL...
echo Your backend will be accessible at the URL shown below.
echo Share this URL with your Android app.
echo.
echo Press Ctrl+C to stop the tunnel.
echo.
cloudflared tunnel --url http://localhost:8000
