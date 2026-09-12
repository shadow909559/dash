import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { PageShell, PageHeader, GlassCard, SectionTitle } from "@/components/ultron";
import { Cloud, RefreshCw, Loader2, Server, Globe, MonitorSmartphone, Radio } from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Ec2State {
  instance_id?: string;
  state?: string;
  public_ip?: string;
  instance_type?: string;
  cloud_backend_url?: string;
  error?: string;
}
interface TunnelState {
  running?: boolean;
  provider?: string | null;
  cost?: string;
  setup?: string | string[];
}
interface PcStatus {
  online?: boolean;
  tunnel_url?: string;
  last_seen?: string;
  device_id?: string;
  capabilities?: string[];
  [k: string]: unknown;
}

const iconSpan = { display: "inline-flex", alignItems: "center", gap: 6 } as const;

export default function RemoteAccessPage() {
  const [ec2, setEc2] = useState<Ec2State | null>(null);
  const [tunnel, setTunnel] = useState<TunnelState | null>(null);
  const [pc, setPc] = useState<PcStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const safeJson = async (url: string): Promise<unknown | null> => {
      try {
        const r = await authFetch(url);
        if (r?.ok) return await r.json();
      } catch { /* offline */ }
      return null;
    };
    const [e, t, p] = await Promise.all([
      safeJson(`${API}/ec2/status`),
      safeJson(`${API}/tunnel/status`),
      safeJson(`${API}/relay/pc-status`),
    ]);
    setEc2((e as Ec2State) ?? null);
    setTunnel((t as TunnelState) ?? null);
    setPc((p as PcStatus) ?? null);
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const startEc2 = useCallback(async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await authFetch(`${API}/ec2/start`, { method: "POST" });
      const data = r?.ok ? await r.json() : { error: `HTTP ${r?.status}` };
      setMsg(data.ok === false ? `Start failed: ${data.error}` : data.message || "Start requested");
    } catch (e) {
      setMsg(`Start failed: ${e instanceof Error ? e.message : "network error"}`);
    }
    setBusy(false);
    fetchAll();
  }, [fetchAll]);

  const stateColor = (s?: string) =>
    s === "running" ? "var(--accent, #22c55e)" : s === "stopped" ? "#ef4444" : s === "pending" ? "#f59e0b" : "var(--dash-text-muted)";

  return (
    <PageShell>
      <PageHeader
        icon={<Cloud size={18} />}
        title="Remote Access"
        subtitle="EC2 cloud backend • Tunnels • Cloud relay • Companion reachability"
        actions={
          <button onClick={fetchAll} aria-label="Refresh remote access data" style={{ display: "flex", alignItems: "center", gap: 6, background: "var(--dash-surface)", border: "1px solid var(--dash-border)", color: "var(--dash-text)", borderRadius: 8, padding: "8px 12px", cursor: "pointer" }}>
            <RefreshCw size={14} /> Refresh
          </button>
        }
      />

      <div style={{ padding: 20, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16 }}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--dash-text-muted)", padding: 24 }} role="status">
            <Loader2 size={16} className="spin" /> Loading remote access…
          </div>
        ) : (
          <>
            {/* EC2 Cloud Backend */}
            <GlassCard>
              <SectionTitle><span style={iconSpan}><Server size={14} /> EC2 Cloud Backend</span></SectionTitle>
              {ec2 ? (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13, marginBottom: 8 }}>
                    <span style={{ fontWeight: 600 }}>{ec2.instance_id || "instance"}</span>
                    <span style={{ display: "flex", alignItems: "center", gap: 6, color: stateColor(ec2.state) }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: stateColor(ec2.state) }} aria-hidden />
                      {ec2.state || "unknown"}
                    </span>
                  </div>
                  {ec2.public_ip && <div style={{ fontSize: 12, color: "var(--dash-text-muted)", marginBottom: 4 }}>IP: <code>{ec2.public_ip}</code></div>}
                  {ec2.instance_type && <div style={{ fontSize: 12, color: "var(--dash-text-muted)", marginBottom: 4 }}>Type: {ec2.instance_type}</div>}
                  {ec2.error && <div style={{ fontSize: 11, color: "#f59e0b", marginBottom: 8 }}>{ec2.error}</div>}
                  <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 12 }}>
                    Cloud backend: <code>{ec2.cloud_backend_url || "—"}</code>
                  </div>
                  <button
                    onClick={startEc2}
                    disabled={busy || ec2.state === "running"}
                    aria-label="Start EC2 instance"
                    style={{ background: "rgba(63,169,245,0.15)", border: "1px solid rgba(63,169,245,0.4)", color: "#3fa9f5", borderRadius: 8, padding: "8px 14px", cursor: busy || ec2.state === "running" ? "default" : "pointer", opacity: busy || ec2.state === "running" ? 0.6 : 1 }}
                  >
                    {busy ? "Starting…" : ec2.state === "running" ? "Running" : "Start instance"}
                  </button>
                  {msg && <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 8 }} role="status">{msg}</div>}
                </>
              ) : (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>EC2 status unavailable (AWS CLI not configured on this machine — the cloud relay still works without it).</p>
              )}
            </GlassCard>

            {/* Tunnel */}
            <GlassCard>
              <SectionTitle><span style={iconSpan}><Globe size={14} /> Internet Tunnel</span></SectionTitle>
              {tunnel ? (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13, marginBottom: 8 }}>
                    <span style={{ fontWeight: 600, textTransform: "capitalize" }}>{tunnel.provider || "no tunnel"}</span>
                    <span style={{ display: "flex", alignItems: "center", gap: 6, color: tunnel.running ? "var(--accent, #22c55e)" : "var(--dash-text-muted)" }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: tunnel.running ? "var(--accent, #22c55e)" : "var(--dash-text-muted)" }} aria-hidden />
                      {tunnel.running ? "active" : "offline"}
                    </span>
                  </div>
                  {tunnel.cost && <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 8 }}>Cost: {tunnel.cost.replace(/_/g, " ")}</div>}
                  {!tunnel.running && tunnel.setup && (
                    <div style={{ fontSize: 11, color: "var(--dash-text-muted)", background: "var(--dash-surface)", borderRadius: 6, padding: "8px 10px" }}>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>Setup</div>
                      {(Array.isArray(tunnel.setup) ? tunnel.setup : [tunnel.setup]).map((s, i) => (
                        <div key={i} style={{ marginBottom: 2 }}>{s}</div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>Tunnel status unavailable.</p>
              )}
            </GlassCard>

            {/* Cloud Relay PC status */}
            <GlassCard>
              <SectionTitle><span style={iconSpan}><MonitorSmartphone size={14} /> Cloud Relay — PC Status</span></SectionTitle>
              {pc ? (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13, marginBottom: 8 }}>
                    <span style={{ fontWeight: 600 }}>{String(pc.device_id || "primary PC")}</span>
                    <span style={{ display: "flex", alignItems: "center", gap: 6, color: pc.online ? "var(--accent, #22c55e)" : "#ef4444" }}>
                      <Radio size={12} aria-hidden />
                      {pc.online ? "online" : "offline"}
                    </span>
                  </div>
                  {pc.tunnel_url && <div style={{ fontSize: 12, color: "var(--dash-text-muted)", marginBottom: 4, wordBreak: "break-all" }}>Tunnel: <code>{String(pc.tunnel_url)}</code></div>}
                  {pc.last_seen && <div style={{ fontSize: 12, color: "var(--dash-text-muted)", marginBottom: 4 }}>Last seen: {new Date(String(pc.last_seen)).toLocaleString()}</div>}
                  {Array.isArray(pc.capabilities) && pc.capabilities.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                      {pc.capabilities.map((c) => (
                        <span key={c} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "rgba(63,169,245,0.12)", color: "#3fa9f5" }}>{c}</span>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>Relay unreachable — this PC may not be registered with the cloud relay yet (registration happens from the Android companion).</p>
              )}
            </GlassCard>
          </>
        )}
      </div>
    </PageShell>
  );
}
