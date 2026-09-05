import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { Smartphone, RefreshCw, Wifi, WifiOff, Link2 } from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, StatusIndicator } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

export const PhonePage: React.FC = () => {
  const [devices, setDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [companionStatus, setCompanionStatus] = useState<any>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/companion/devices`);
      const d = await r.json();
      setDevices(d.devices || d || []);
    } catch {}
    try {
      const r = await authFetch(`${API}/phone/status`);
      setCompanionStatus(await r.json());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return (
    <PageShell glowColor="rgba(77, 148, 255, 0.05)">
      <PageHeader
        icon={<Smartphone size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        title="Phone Link"
        subtitle="Mobile device synchronization and notification forwarding"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background:
                devices.length > 0
                  ? "rgba(34,197,94,0.10)"
                  : "rgba(107,114,128,0.10)",
              color:
                devices.length > 0
                  ? "var(--dash-success)"
                  : "var(--dash-text-muted)",
              border: `1px solid ${
                devices.length > 0
                  ? "rgba(34,197,94,0.25)"
                  : "var(--dash-border)"
              }`,
            }}
          >
            {devices.length > 0 ? <Wifi size={10} /> : <WifiOff size={10} />}
            {devices.length > 0 ? "Connected" : "No devices"}
          </span>
        }
        actions={
          <button onClick={fetchStatus} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {loading ? (
          <div
            style={{
              textAlign: "center",
              padding: 48,
              color: "var(--dash-text-muted)",
            }}
          >
            <RefreshCw
              size={18}
              className="animate-rotate"
              style={{ marginBottom: 10 }}
            />
            <div>Scanning for devices...</div>
          </div>
        ) : (
          <>
            {/* Companion status */}
            {companionStatus && (
              <GlassCard padding={18}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    marginBottom: 12,
                  }}
                >
                  <Link2 size={14} style={{ color: "var(--dash-accent)" }} />
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: "var(--dash-text)",
                    }}
                  >
                    Companion Status
                  </span>
                </div>
                <pre
                  style={{
                    fontSize: 11,
                    color: "var(--dash-text-muted)",
                    fontFamily: "'JetBrains Mono', monospace",
                    whiteSpace: "pre-wrap",
                    margin: 0,
                    padding: 12,
                    background: "var(--dash-bg)",
                    borderRadius: "var(--dash-radius-sm)",
                    border: "1px solid var(--dash-border-subtle)",
                  }}
                >
                  {JSON.stringify(companionStatus, null, 2)}
                </pre>
              </GlassCard>
            )}

            {/* Devices */}
            {devices.length === 0 ? (
              <EmptyState
                icon={
                  <Smartphone
                    size={28}
                    style={{ color: "var(--dash-accent)" }}
                  />
                }
                title="No devices connected"
                description="Install the DASH Android companion app and connect via Device Pairing to sync your phone."
              />
            ) : (
              devices.map((d: any, i: number) => (
                <GlassCard key={i} padding={0} className="dash-card-glow">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                      padding: "16px 20px",
                    }}
                  >
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: "var(--dash-radius-sm)",
                        background: "rgba(34,197,94,0.12)",
                        border: "1px solid rgba(34,197,94,0.2)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <Smartphone
                        size={18}
                        style={{ color: "var(--dash-success)" }}
                      />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: "var(--dash-text)",
                        }}
                      >
                        {d.name || d.device_name || "Android Device"}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace",
                          marginTop: 2,
                        }}
                      >
                        {d.id || d.device_id || ""}
                      </div>
                    </div>
                    <StatusIndicator
                      status="online"
                      label={d.status || "connected"}
                    />
                  </div>
                </GlassCard>
              ))
            )}
          </>
        )}
      </div>
    </PageShell>
  );
};

export default PhonePage;
