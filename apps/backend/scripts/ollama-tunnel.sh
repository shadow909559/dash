#!/bin/bash
# ============================================================
# DASH Ollama Reverse Tunnel
# Connects the cloud backend to your local Ollama instance.
#
# Option 1: SSH reverse tunnel (simple, no account needed)
# Option 2: Cloudflare tunnel (more reliable, needs account)
#
# Run this on YOUR PC (not the server) when you want AI to work.
# ============================================================

set -e

OLLAMA_PORT="${OLLAMA_PORT:-11434}"
CLOUD_HOST="${CLOUD_HOST:-dash-backend.fly.dev}"

echo "=== DASH Ollama Reverse Tunnel ==="
echo ""
echo "This connects your local Ollama to the cloud backend."
echo "AI will only work while this tunnel is running (and your PC is on)."
echo ""

# Check if Ollama is running
if ! curl -s "http://localhost:$OLLAMA_PORT/api/tags" > /dev/null 2>&1; then
    echo "ERROR: Ollama is not running on port $OLLAMA_PORT"
    echo "Start Ollama first: ollama serve"
    exit 1
fi

echo "Ollama is running on port $OLLAMA_PORT"
echo ""

# Option 1: SSH reverse tunnel (recommended for simplicity)
echo "Setting up SSH reverse tunnel..."
echo "This will forward your local Ollama to the cloud server."
echo ""
echo "NOTE: You need SSH access to your Fly.io app."
echo "Run: fly ssh console --app dash-backend"
echo "Then from the server, the tunnel will be available."
echo ""

# Create a simple SSH tunnel
# This requires the Fly.io SSH key to be set up
# flyctl ssh issue --app dash-backend

echo "--- Alternative: Use Cloudflare Tunnel ---"
echo ""
echo "If SSH doesn't work, use Cloudflare Tunnel instead:"
echo ""
echo "1. Install cloudflared (if not installed):"
echo "   winget install Cloudflare.cloudflared"
echo ""
echo "2. Start tunnel to forward Ollama:"
echo "   cloudflared tunnel --url http://localhost:$OLLAMA_PORT"
echo ""
echo "3. Copy the URL (e.g., https://xxx.trycloudflare.com)"
echo ""
echo "4. Set it as OLLAMA_BASE_URL on Fly.io:"
echo "   flyctl secrets set OLLAMA_BASE_URL='https://xxx.trycloudflare.com' --app dash-backend"
echo ""
echo "--- Quick SSH Tunnel Method ---"
echo ""
echo "If you have SSH access to the Fly.io machine:"
echo ""
echo "  # On your PC, create the tunnel:"
echo "  ssh -R 11434:localhost:$OLLAMA_PORT root@<fly-app-ip>"
echo ""
echo "  # Or use flyctl:"
echo "  flyctl ssh console --app dash-backend -C 'echo Tunnel ready'"
echo "  # Then in another terminal:"
echo "  flyctl ssh tunnel --app dash-backend --machine <machine-id> --local-addr localhost:$OLLAMA_PORT --remote-addr localhost:$OLLAMA_PORT"
echo ""
echo "=== Press Ctrl+C to stop the tunnel ==="
echo ""

# Start the tunnel using cloudflared if available
if command -v cloudflared &> /dev/null; then
    echo "Starting Cloudflare Tunnel for Ollama..."
    echo "Once you see a URL, set it on Fly.io:"
    echo "  flyctl secrets set OLLAMA_BASE_URL='<url>' --app dash-backend"
    echo ""
    cloudflared tunnel --url "http://localhost:$OLLAMA_PORT"
else
    echo "cloudflared not found. Install it first:"
    echo "  winget install Cloudflare.cloudflared"
    echo ""
    echo "Or use SSH tunnel (see instructions above)."
    echo "Waiting... (Ctrl+C to exit)"
    sleep infinity
fi
