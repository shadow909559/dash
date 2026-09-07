#!/bin/bash
# ============================================================
# DASH Backend — Cloud Deployment (FREE FOREVER)
# Uses Fly.io free tier: 3 VMs, 160GB bandwidth, always-on
# Plus Supabase: free database + auth + realtime
# ============================================================

set -e

echo "╔══════════════════════════════════════════╗"
echo "║   DASH Cloud Deployment (Free Forever)  ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Services used (all free):"
echo "  • Fly.io      — Backend API (always-on, no expiry)"
echo "  • Supabase    — Database + Auth + Realtime"
echo "  • Vercel      — Web Dashboard"
echo "  • GitHub      — Source code + CI/CD"
echo "  • Cloudflare  — PC tunnel (Ollama + Desktop)"
echo ""
echo "Total cost: \$0/month, forever"
echo ""

# ─── Step 1: Install flyctl ──────────────────────────────
echo "[1/6] Installing Fly.io CLI..."
if ! command -v flyctl &> /dev/null; then
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
fi
echo "  ✓ flyctl $(flyctl version --short)"

# ─── Step 2: Authenticate ────────────────────────────────
echo "[2/6] Authenticating..."
if ! flyctl auth whoami &> /dev/null 2>&1; then
    echo "  Opening browser for login..."
    flyctl auth login
fi
echo "  ✓ Logged in as $(flyctl auth whoami)"

# ─── Step 3: Create app ──────────────────────────────────
echo "[3/6] Creating Fly.io app..."
cd "$(dirname "$0")/.."

if ! flyctl apps list 2>/dev/null | grep -q "dash-backend"; then
    flyctl apps create dash-backend
    echo "  ✓ App created"
else
    echo "  ✓ App already exists"
fi

# ─── Step 4: Set secrets ─────────────────────────────────
echo "[4/6] Setting secrets..."

# Generate JWT secret
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)

echo ""
echo "  You need to set these secrets manually."
echo "  Copy and paste each command:"
echo ""
echo "  # JWT Secret (auto-generated)"
echo "  flyctl secrets set DASH_JWT_SECRET_KEY='$JWT_SECRET' --app dash-backend"
echo ""
echo "  # Database (from Supabase — see setup-supabase.sh)"
echo "  flyctl secrets set DATABASE_URL='postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres' --app dash-backend"
echo ""
echo "  # Supabase keys (from Supabase dashboard)"
echo "  flyctl secrets set SUPABASE_URL='https://YOUR_PROJECT.supabase.co' --app dash-backend"
echo "  flyctl secrets set SUPABASE_ANON_KEY='eyJ...' --app dash-backend"
echo "  flyctl secrets set SUPABASE_SERVICE_KEY='eyJ...' --app dash-backend"
echo ""
echo "  # Redis (optional — can use Supabase Realtime instead)"
echo "  # flyctl secrets set REDIS_URL='redis://...' --app dash-backend"
echo ""
echo "  # Ollama (set when your PC tunnel is running)"
echo "  flyctl secrets set OLLAMA_BASE_URL='https://xxx.trycloudflare.com' --app dash-backend"
echo ""
read -p "  Press Enter after setting secrets (or Ctrl+C to set them later)..."

# ─── Step 5: Deploy ──────────────────────────────────────
echo "[5/6] Deploying to Fly.io..."
flyctl deploy --app dash-backend --remote-only

# ─── Step 6: Verify ──────────────────────────────────────
echo "[6/6] Verifying deployment..."
sleep 5

HEALTH=$(curl -s "https://dash-backend.fly.dev/health" 2>/dev/null)
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "  ✓ Backend is live and healthy!"
else
    echo "  ⚠ Backend may still be starting. Check: https://dash-backend.fly.dev/health"
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Deployment Complete!                   ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Your DASH backend is now live (FREE FOREVER):"
echo ""
echo "  🌐 API:     https://dash-backend.fly.dev"
echo "  📊 Health:  https://dash-backend.fly.dev/health"
echo "  📖 Docs:    https://dash-backend.fly.dev/docs"
echo ""
echo "Connect your apps:"
echo "  Server IP: dash-backend.fly.dev"
echo "  Port:      443 (HTTPS)"
echo ""
echo "Your PC (for AI + Desktop control):"
echo "  python scripts/pc-auto-connect.py"
echo ""
