#!/bin/bash
# ============================================================
# DASH Backend — Full Cloud Deployment
# Deploys backend to Fly.io with database, Redis, and AI.
#
# Usage:
#   bash deploy-flyio.sh
#
# Prerequisites:
#   - Fly.io account (free at https://fly.io)
#   - At least one AI API key (OpenAI, Claude, or Gemini)
# ============================================================

set -e

APP_NAME="dash-backend"
REGION="sjc"

echo "╔══════════════════════════════════════════╗"
echo "║   DASH Cloud Backend Deployment         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Step 1: Install flyctl
echo "[1/7] Checking Fly.io CLI..."
if ! command -v flyctl &> /dev/null; then
    echo "  Installing flyctl..."
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
fi
echo "  flyctl version: $(flyctl version --short)"

# Step 2: Authenticate
echo "[2/7] Authenticating..."
if ! flyctl auth whoami &> /dev/null 2>&1; then
    echo "  Opening browser for login..."
    flyctl auth login
fi
echo "  Logged in as: $(flyctl auth whoami)"

# Step 3: Launch app
echo "[3/7] Setting up Fly.io app..."
cd "$(dirname "$0")/.."

if flyctl apps list | grep -q "$APP_NAME"; then
    echo "  App '$APP_NAME' already exists"
else
    echo "  Creating app '$APP_NAME'..."
    flyctl apps create "$APP_NAME" --json | head -5
fi

# Step 4: Create Postgres database
echo "[4/7] Setting up Postgres database..."
if ! flyctl postgres list 2>/dev/null | grep -q "dash-db"; then
    echo "  Creating Postgres database..."
    flyctl postgres create --name dash-db --region "$REGION" --app "$APP_NAME"
    echo "  Connecting database..."
    flyctl postgres attach dash-db --app "$APP_NAME"
else
    echo "  Database already exists"
fi

# Step 5: Create Redis (Upstash recommended, or use Fly Redis)
echo "[5/7] Setting up Redis..."
echo "  Redis options:"
echo "    a) Upstash (free tier, recommended): https://upstash.com"
echo "    b) Fly Redis: flyctl redis create --app $APP_NAME"
echo ""
echo "  For now, setting up with localhost Redis (will be replaced)"
echo "  To add cloud Redis later:"
echo "    flyctl secrets set REDIS_URL='redis://...' --app $APP_NAME"

# Step 6: Set secrets
echo "[6/7] Setting secrets..."
echo ""
echo "  You need to set these secrets. Run each command:"
echo ""

# Generate JWT secret
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
echo "  # JWT Secret (auto-generated)"
echo "  flyctl secrets set DASH_JWT_SECRET_KEY='$JWT_SECRET' --app $APP_NAME"
echo ""

echo "  # AI Provider — set at least one:"
echo "  flyctl secrets set OPENAI_API_KEY='sk-your-key' --app $APP_NAME"
echo "  # OR"
echo "  flyctl secrets set ANTHROPIC_API_KEY='sk-ant-your-key' --app $APP_NAME"
echo "  # OR"
echo "  flyctl secrets set GEMINI_API_KEY='your-key' --app $APP_NAME"
echo ""

echo "  # Ollama (for local AI when PC is on):"
echo "  flyctl secrets set OLLAMA_BASE_URL='https://xxx.trycloudflare.com' --app $APP_NAME"
echo ""

echo "  # Redis (when you have cloud Redis):"
echo "  flyctl secrets set REDIS_URL='redis://...' --app $APP_NAME"
echo ""

# Step 7: Deploy
echo "[7/7] Deploying to Fly.io..."
echo "  This will build and deploy the Docker image..."
echo ""
flyctl deploy --app "$APP_NAME" --remote-only

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Deployment Complete!                   ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Your DASH backend is now live at:"
echo "  https://$APP_NAME.fly.dev"
echo ""
echo "Health check:"
echo "  curl https://$APP_NAME.fly.dev/health"
echo ""
echo "API docs:"
echo "  https://$APP_NAME.fly.dev/docs"
echo ""
echo "Next steps:"
echo "  1. Set the secrets listed above (step 6)"
echo "  2. Run 'bash scripts/pc-autostart.bat' on your PC (as Admin)"
echo "  3. Update mobile/desktop apps to connect to:"
echo "     Server IP: $APP_NAME.fly.dev"
echo "     Port: 443"
echo ""
echo "Your Android app will now connect to the cloud backend."
echo "AI works via cloud APIs (always) + local Ollama (when PC is on)."
echo "Desktop control works via WoL + Cloudflare tunnel (when PC is on)."
