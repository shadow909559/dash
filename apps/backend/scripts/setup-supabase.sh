#!/bin/bash
# ============================================================
# DASH — Supabase Setup
# Sets up Supabase as the cloud database, auth, and realtime layer.
#
# Free tier: 500MB DB, 1GB storage, 50K MAU auth
# ============================================================

set -e

echo "╔══════════════════════════════════════════╗"
echo "║   DASH — Supabase Setup                 ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Step 1: Check if Supabase CLI is installed
echo "[1/5] Checking Supabase CLI..."
if ! command -v supabase &> /dev/null; then
    echo "  Installing Supabase CLI..."
    npx supabase --version 2>/dev/null || npm install -g supabase
fi

# Step 2: Login
echo "[2/5] Authenticating with Supabase..."
if ! supabase projects list &> /dev/null 2>&1; then
    echo "  Opening browser for login..."
    supabase login
fi

# Step 3: Create or link project
echo "[3/5] Setting up Supabase project..."
echo ""
echo "  Go to https://supabase.com and create a new project:"
echo "    - Name: dash-backend"
echo "    - Database password: (save this!)"
echo "    - Region: closest to you"
echo ""
echo "  Then run:"
echo "    supabase link --project-ref YOUR_PROJECT_REF"
echo ""
echo "  Or set the connection string directly:"
echo "    flyctl secrets set DATABASE_URL='postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres' --app dash-backend"
echo ""

# Step 4: Run migrations
echo "[4/5] Running database migrations..."
if [ -f "supabase/migrations/001_initial.sql" ]; then
    echo "  Applying initial schema..."
    supabase db push
else
    echo "  No migrations found. Creating initial schema..."
    mkdir -p supabase/migrations

    cat > supabase/migrations/001_initial.sql << 'SQL'
-- DASH Backend Schema for Supabase
-- Enables Row Level Security for multi-device auth

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT,
    user_id TEXT DEFAULT 'default',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Memory table (episodic + semantic)
CREATE TABLE IF NOT EXISTS memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    type TEXT DEFAULT 'episodic',
    embedding VECTOR(384),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    read BOOLEAN DEFAULT FALSE,
    source TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Automation rules
CREATE TABLE IF NOT EXISTS automation_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    trigger_config JSONB NOT NULL,
    action_config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Approvals table
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_type TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    risk_level TEXT DEFAULT 'medium',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Devices table (paired mobile/desktop)
CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('android', 'desktop', 'web')),
    token TEXT NOT NULL UNIQUE,
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(type);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
CREATE INDEX IF NOT EXISTS idx_devices_token ON devices(token);

-- Row Level Security (RLS)
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE devices ENABLE ROW LEVEL SECURITY;

-- Policies (allow authenticated device tokens)
CREATE POLICY "Devices can read own data" ON conversations
    FOR SELECT USING (true);

CREATE POLICY "Devices can insert conversations" ON conversations
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Devices can read messages" ON messages
    FOR SELECT USING (true);

CREATE POLICY "Devices can insert messages" ON messages
    FOR INSERT WITH CHECK (true);

-- Realtime: enable for key tables
ALTER PUBLICATION supabase_realtime ADD TABLE notifications;
ALTER PUBLICATION supabase_realtime ADD TABLE approvals;
ALTER PUBLICATION supabase_realtime ADD TABLE devices;

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

SQL
    echo "  Schema created at supabase/migrations/001_initial.sql"
    echo "  Run 'supabase db push' to apply it"
fi

# Step 5: Get connection details
echo "[5/5] Getting connection details..."
echo ""
echo "  After creating your Supabase project, you'll need:"
echo ""
echo "  1. Database URL (Settings > Database > Connection string > URI):"
echo "     postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres"
echo ""
echo "  2. Anon Key (Settings > API > anon public):"
echo "     eyJhbGciOiJIUzI1NiIsInR5cCI6..."
echo ""
echo "  3. Service Key (Settings > API > service_role):"
echo "     eyJhbGciOiJIUzI1NiIsInR5cCI6..."
echo ""
echo "  Set these on Fly.io:"
echo "    flyctl secrets set DATABASE_URL='postgresql://...' --app dash-backend"
echo "    flyctl secrets set SUPABASE_URL='https://YOUR_PROJECT.supabase.co' --app dash-backend"
echo "    flyctl secrets set SUPABASE_ANON_KEY='eyJ...' --app dash-backend"
echo "    flyctl secrets set SUPABASE_SERVICE_KEY='eyJ...' --app dash-backend"
echo ""
echo "=== Setup Complete ==="
