-- DASH Cloud Relay — schema additions
-- Uses existing dash_devices table for device registry.
-- Extra fields (tunnel_url, mac_address, local_ip) stored in capabilities jsonb.
-- Tables below are for audit/history purposes.

-- 1. Indexes on existing dash_devices for fast lookups
CREATE INDEX IF NOT EXISTS idx_dash_devices_status ON dash_devices (status);
CREATE INDEX IF NOT EXISTS idx_dash_devices_last_seen ON dash_devices (last_seen_at);

-- 2. tunnel_urls: history of tunnel endpoints (audit trail)
CREATE TABLE IF NOT EXISTS dash_tunnel_urls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_name TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT 'ollama',
    url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_dash_tunnel_urls_device ON dash_tunnel_urls (device_name);

-- 3. wol_triggers: log Wake-on-LAN requests (audit trail)
CREATE TABLE IF NOT EXISTS dash_wol_triggers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_name TEXT NOT NULL,
    mac_address TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    triggered_by TEXT DEFAULT 'android',
    packets_sent INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_dash_wol_triggers_device ON dash_wol_triggers (device_name);

-- 4. RLS policies
ALTER TABLE dash_tunnel_urls ENABLE ROW LEVEL SECURITY;
ALTER TABLE dash_wol_triggers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON dash_tunnel_urls FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON dash_wol_triggers FOR ALL USING (true) WITH CHECK (true);
