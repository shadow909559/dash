# DASH Hybrid Setup Guide — $0 Forever

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          ☁️ CLOUD ($0/month, free forever)          │
│                                                     │
│  Supabase            Fly.io              Vercel     │
│  ├─ Database         ├─ Backend API      ├─ Web UI  │
│  ├─ Auth             ├─ WebSocket        └─ Dashboard│
│  ├─ Realtime         ├─ Always-on                   │
│  ├─ File Storage     └─ Docker                     │
│  └─ Edge Functions                                 │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
     ┌────▼────┐ ┌─────▼────┐ ┌────▼────┐
     │ Android │ │ Web App  │ │ Desktop │
     │ (local) │ │ (browser)│ │ (local) │
     └─────────┘ └──────────┘ └────┬────┘
                                   │
                            ┌──────▼──────┐
                            │  Your PC    │
                            │  Ollama AI  │
                            │  Desktop    │
                            └─────────────┘
```

## Free Services (all free forever)

| Service | Free Tier | What It Does |
|---------|-----------|-------------|
| **Fly.io** | 3 VMs, 160GB bandwidth | Backend API (always-on) |
| **Supabase** | 500MB DB, 1GB storage, 50K MAU | Database, Auth, Realtime |
| **Vercel** | 100GB bandwidth | Web dashboard |
| **GitHub** | Unlimited repos, 2000 CI mins | Code + CI/CD |
| **Cloudflare** | Free tunnel | PC ↔ Cloud connection |

## Quick Start (5 minutes)

### 1. Supabase (Database)
```bash
# Create account at https://supabase.com
# Create project: dash-backend
# Copy database URL and API keys
```

### 2. Fly.io (Backend)
```bash
cd apps/backend
bash scripts/deploy-cloud.sh
```

### 3. Vercel (Web Dashboard)
```bash
# Import GitHub repo at https://vercel.com
# Root directory: apps/desktop
# Deploy
```

### 4. PC Auto-Connect
```bash
# On your Windows PC
python scripts/pc-auto-connect.py
```

### 5. Mobile App
```
Server IP: dash-backend.fly.dev
Port: 443
```

## Detailed Setup

### Supabase

1. Go to https://supabase.com → Create account
2. New project → Name: `dash-backend`
3. Go to Settings → Database → Connection string
4. Copy the URI (looks like `postgresql://postgres:xxx@db.xxx.supabase.co:5432/postgres`)
5. Go to Settings → API → Copy `anon` and `service_role` keys
6. Run migrations:
   ```bash
   npx supabase login
   npx supabase link --project-ref YOUR_PROJECT_REF
   npx supabase db push
   ```

### Fly.io

1. Install CLI:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
2. Login:
   ```bash
   flyctl auth login
   ```
3. Set secrets:
   ```bash
   flyctl secrets set DATABASE_URL='postgresql://...' --app dash-backend
   flyctl secrets set SUPABASE_URL='https://xxx.supabase.co' --app dash-backend
   flyctl secrets set SUPABASE_ANON_KEY='eyJ...' --app dash-backend
   flyctl secrets set SUPABASE_SERVICE_KEY='eyJ...' --app dash-backend
   flyctl secrets set DASH_JWT_SECRET_KEY='$(openssl rand -hex 32)' --app dash-backend
   ```
4. Deploy:
   ```bash
   flyctl deploy --app dash-backend
   ```

### PC Auto-Connect

On your Windows PC:

```bash
# Install cloudflared
winget install Cloudflare.cloudflared

# Install Python dependencies
pip install requests

# Run auto-connect
python scripts/pc-auto-connect.py
```

This will:
- Register your PC with the cloud
- Start tunnel for Ollama
- Keep connection alive with heartbeats
- Auto-reconnect if connection drops

## How It Works

### PC OFF → Cloud Only
```
Android → Fly.io Backend → Supabase DB
                          → Cloud AI (if configured)
```
Works: Chat, memory, notifications, auth, web dashboard

### PC ON → Full Features
```
Android → Fly.io Backend → Supabase DB
                          → PC Auto-Connect
                            → Ollama (local AI)
                            → Desktop Control
                            → Screenshots
```
Works: Everything

## Secrets Reference

```bash
# Required
flyctl secrets set DATABASE_URL='...' --app dash-backend
flyctl secrets set DASH_JWT_SECRET_KEY='...' --app dash-backend

# Supabase
flyctl secrets set SUPABASE_URL='...' --app dash-backend
flyctl secrets set SUPABASE_ANON_KEY='...' --app dash-backend
flyctl secrets set SUPABASE_SERVICE_KEY='...' --app dash-backend

# AI (optional — cloud APIs when PC is off)
flyctl secrets set OPENAI_API_KEY='sk-...' --app dash-backend
flyctl secrets set ANTHROPIC_API_KEY='sk-ant-...' --app dash-backend
flyctl secrets set GEMINI_API_KEY='...' --app dash-backend

# Ollama (set when PC tunnel is running)
flyctl secrets set OLLAMA_BASE_URL='https://xxx.trycloudflare.com' --app dash-backend

# Redis (optional — can use Supabase Realtime instead)
# flyctl secrets set REDIS_URL='...' --app dash-backend
```

## Cost

| Service | Cost | Notes |
|---------|------|-------|
| Fly.io | $0 | Free forever, no expiry |
| Supabase | $0 | Free tier, no expiry |
| Vercel | $0 | Free tier, no expiry |
| GitHub | $0 | Free tier, no expiry |
| Cloudflare | $0 | Free tunnel, no expiry |
| **Total** | **$0/month** | **Forever** |
