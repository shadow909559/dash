import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useAIStore } from "@/stores/aiStore";
import { LiveRegion } from "@/components/LiveRegion";
import {
  Activity,
  Cpu,
  HardDrive,
  Wifi,
  Thermometer,
  RefreshCw,
  Monitor,
  Database,
  Bot,
  Smartphone,
  Clock,
  Zap,
} from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

/** Compact relative time for last-tick / next-due stamps. Past → "2m ago",
 * future → "in 30s", missing → "never" (not dressed up as something else). */
function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return "never";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "unknown";
  const diff = Math.round((t - Date.now()) / 1000);
  const abs = Math.abs(diff);
  const span =
    abs < 60
      ? `${abs}s`
      : abs < 3600
        ? `${Math.floor(abs / 60)}m`
        : `${Math.floor(abs / 3600)}h ${Math.floor((abs % 3600) / 60)}m`;
  return diff >= 0 ? `in ${span}` : `${span} ago`;
}

export const SystemMonitorPage: React.FC = () => {
  const { systemStats, systemStatus, websocketStatus, aiProviderStatus } = useAIStore();
  const [healthData, setHealthData] = useState<any>(null);
  const [monitorData, setMonitorData] = useState<any>(null);
  const [triggerStatus, setTriggerStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [h, m, t] = await Promise.all([
        authFetch(`${API.replace("/api/v1", "")}/health`).then((r) => r.json()),
        authFetch(`${API}/monitor/health`).then((r) => r.json()).catch(() => null),
        authFetch(`${API}/enhanced/workflows/trigger-status`)
          .then((r) => r.json())
          .catch(() => null),
      ]);
      setHealthData(h);
      setMonitorData(m);
      setTriggerStatus(t);
    } catch { }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const resources = monitorData?.resources || {};
  const components = monitorData?.components || {};

  const MetricCard = ({
    icon: Icon,
    label,
    value,
    color,
    barPercent,
    barColor,
  }: {
    icon: any;
    label: string;
    value: string;
    color: string;
    barPercent?: number;
    barColor?: string;
  }) => (
    <div className="dash-card" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Icon size={16} style={{ color }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--dash-text)" }}>{label}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--dash-text)", marginLeft: "auto", fontFamily: "JetBrains Mono, monospace" }}>{value}</span>
      </div>
      {barPercent !== undefined && (
        <div style={{ height: 4, borderRadius: 2, background: "rgba(255,255,255,0.05)" }}>
          <div className="metric-bar-fill" style={{ height: "100%", width: `${Math.min(barPercent, 100)}%`, borderRadius: 2, background: barColor || color, transition: "width 0.5s" }} />
        </div>
      )}
    </div>
  );

  const ServiceStatus = ({
    name,
    status,
    detail,
  }: {
    name: string;
    status: "ok" | "error" | "unknown";
    detail?: string;
  }) => (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: "var(--dash-radius-sm)", background: "var(--dash-bg-subtle)", border: "1px solid var(--dash-border-subtle)" }}>
      <span className="animate-status-pulse" style={{ width: 7, height: 7, borderRadius: "50%", background: status === "ok" ? "var(--dash-success)" : status === "error" ? "var(--dash-danger)" : "var(--dash-text-muted)", display: "inline-block", flexShrink: 0 }} />
      <span style={{ fontSize: 12, fontWeight: 500, color: "var(--dash-text)", flex: 1 }}>{name}</span>
      {detail && <span style={{ fontSize: 10, color: "var(--dash-text-muted)", fontFamily: "JetBrains Mono, monospace" }}>{detail}</span>}
      <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: status === "ok" ? "rgba(34,197,94,0.12)" : status === "error" ? "rgba(63,169,245,0.12)" : "rgba(255,255,255,0.06)", color: status === "ok" ? "var(--dash-success)" : status === "error" ? "var(--dash-danger)" : "var(--dash-text-muted)", fontFamily: "JetBrains Mono, monospace" }}>
        {status === "ok" ? "ONLINE" : status === "error" ? "ERROR" : "UNKNOWN"}
      </span>
    </div>
  );

  return (
    <div style={{ padding: "20px 28px", maxWidth: 1200, margin: "0 auto", height: "100%", overflowY: "auto" }}>
      {/* Header */}
      <div className="dash-card" style={{ padding: "20px 24px", display: "flex", alignItems: "center", gap: 16, marginBottom: 18 }}>
        <div style={{ width: 44, height: 44, borderRadius: "var(--dash-radius-md)", backgroundColor: "var(--dash-success-bg)", border: "1px solid rgba(52,211,153,0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Activity size={22} style={{ color: "var(--dash-success)" }} />
        </div>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--dash-text)", margin: 0 }}>System Monitor</h1>
          <p style={{ fontSize: 12, color: "var(--dash-text-secondary)", margin: "3px 0 0" }}>Real-time system health and service monitoring</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="animate-status-pulse" style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--dash-success)", display: "inline-block" }} />
          <span style={{ fontSize: 10, color: "var(--dash-success)" }}>Auto-refreshing 5s</span>
        </div>
        <button onClick={fetchData} style={{ padding: "8px 12px", borderRadius: "var(--dash-radius-md)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text-secondary)", cursor: "pointer" }}><RefreshCw size={14} /></button>
      </div>

      {/* Screen reader announcement for system stats */}
      <LiveRegion>
        {`System resources: CPU ${(resources.cpu?.percent ?? systemStats?.cpu ?? 0).toFixed(1)} percent, Memory ${(resources.memory?.percent ?? systemStats?.ram ?? 0).toFixed(1)} percent, Disk ${(resources.disk?.percent ?? systemStats?.disk ?? 0).toFixed(1)} percent.`}
      </LiveRegion>

      {/* Resource Metrics Grid */}
      <div className="dash-section-title">System Resources</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 20 }}>
        <MetricCard icon={Cpu} label="CPU" value={`${(resources.cpu?.percent ?? systemStats?.cpu ?? 0).toFixed(1)}%`} color="var(--dash-cyan)" barPercent={resources.cpu?.percent ?? systemStats?.cpu ?? 0} barColor="var(--dash-cyan)" />
        <MetricCard icon={HardDrive} label="Memory" value={`${(resources.memory?.percent ?? systemStats?.ram ?? 0).toFixed(1)}%`} color="var(--dash-accent-secondary)" barPercent={resources.memory?.percent ?? systemStats?.ram ?? 0} barColor="var(--dash-accent-secondary)" />
        <MetricCard icon={Monitor} label="Disk" value={`${(resources.disk?.percent ?? systemStats?.disk ?? 0).toFixed(1)}%`} color="var(--dash-success)" barPercent={resources.disk?.percent ?? systemStats?.disk ?? 0} barColor="var(--dash-success)" />
        {(resources.gpu?.percent ?? 0) > 0 && <MetricCard icon={Zap} label="GPU" value={`${resources.gpu?.percent}%`} color="var(--dash-warning)" barPercent={resources.gpu?.percent} barColor="var(--dash-warning)" />}
        <MetricCard icon={Wifi} label="Network" value={`${resources.network?.bytes_recv ? `${((resources.network.bytes_recv) / 1048576).toFixed(1)}MB recv` : "Idle"}`} color="var(--dash-info)" />
        <MetricCard icon={Clock} label="Uptime" value={`${Math.floor((systemStats?.uptime ?? 0) / 3600)}h ${Math.floor(((systemStats?.uptime ?? 0) % 3600) / 60)}m`} color="var(--dash-text-secondary)" />
      </div>

      {/* Service Health */}
      <div className="dash-section-title">Service Health</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
        <ServiceStatus name="Backend API" status={systemStatus === "online" ? "ok" : "error"} detail={healthData?.version || ""} />
        <ServiceStatus name="WebSocket" status={websocketStatus === "connected" ? "ok" : "error"} detail={websocketStatus} />
        <ServiceStatus name="AI Provider" status={aiProviderStatus === "ready" ? "ok" : aiProviderStatus === "offline" ? "error" : "unknown"} detail={aiProviderStatus} />
        {components.obsidian && <ServiceStatus name="Obsidian" status={components.obsidian.status === "ok" ? "ok" : "unknown"} detail={components.obsidian.notes !== undefined ? `${components.obsidian.notes} notes` : ""} />}
        {components.backend && <ServiceStatus name="Backend Process" status={components.backend.status === "ok" ? "ok" : "unknown"} detail={components.backend.uptime ? `${Math.floor(components.backend.uptime / 60)}m` : ""} />}
      </div>

      {/* Workflow Triggers (decisions.md #81) */}
      <div className="dash-section-title">Workflow Triggers</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
        {triggerStatus ? (
          <>
            <ServiceStatus
              name="Trigger Scheduler"
              status={triggerStatus.scheduler?.running ? "ok" : "error"}
              detail={`poll ${triggerStatus.scheduler?.poll_seconds ?? "?"}s · last tick ${fmtRelative(triggerStatus.scheduler?.last_tick_at)}`}
            />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8 }}>
              <MetricCard
                icon={Clock}
                label="Schedules"
                value={`${triggerStatus.schedules_active}/${triggerStatus.schedules_total}${triggerStatus.schedules_paused > 0 ? ` (${triggerStatus.schedules_paused} paused)` : ""}`}
                color={triggerStatus.schedules_paused > 0 ? "var(--dash-warning)" : "var(--dash-success)"}
                barPercent={triggerStatus.schedules_total > 0 ? (triggerStatus.schedules_active / triggerStatus.schedules_total) * 100 : 0}
                barColor="var(--dash-success)"
              />
              <MetricCard
                icon={Zap}
                label="Webhooks"
                value={`${triggerStatus.webhooks_active}/${triggerStatus.webhooks_total}${triggerStatus.webhooks_paused > 0 ? ` (${triggerStatus.webhooks_paused} paused)` : ""}`}
                color={triggerStatus.webhooks_paused > 0 ? "var(--dash-warning)" : "var(--dash-success)"}
                barPercent={triggerStatus.webhooks_total > 0 ? (triggerStatus.webhooks_active / triggerStatus.webhooks_total) * 100 : 0}
                barColor="var(--dash-success)"
              />
              <MetricCard
                icon={Activity}
                label="Event Triggers"
                value={`${triggerStatus.event_triggers_active}/${triggerStatus.event_triggers_total}${triggerStatus.event_triggers_paused > 0 ? ` (${triggerStatus.event_triggers_paused} paused)` : ""}`}
                color={triggerStatus.event_triggers_paused > 0 ? "var(--dash-warning)" : "var(--dash-success)"}
                barPercent={triggerStatus.event_triggers_total > 0 ? (triggerStatus.event_triggers_active / triggerStatus.event_triggers_total) * 100 : 0}
                barColor="var(--dash-success)"
              />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: "var(--dash-radius-sm)", background: "var(--dash-bg-subtle)", border: "1px solid var(--dash-border-subtle)" }}>
              <Clock size={13} style={{ color: "var(--dash-cyan)", flexShrink: 0 }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--dash-text)", flexShrink: 0 }}>Next due</span>
              {triggerStatus.next_due ? (
                <>
                  <span style={{ fontSize: 11, color: "var(--dash-text)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {triggerStatus.next_due.workflow_name}
                    <span style={{ fontFamily: "JetBrains Mono, monospace", color: "var(--dash-text-muted)", marginLeft: 6 }}>{triggerStatus.next_due.cron}</span>
                  </span>
                  <span style={{ fontSize: 10, color: "var(--dash-cyan)", fontFamily: "JetBrains Mono, monospace" }}>{fmtRelative(triggerStatus.next_due.due_at)}</span>
                </>
              ) : (
                <span style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>none scheduled</span>
              )}
            </div>
          </>
        ) : (
          <div style={{ padding: "10px 14px", borderRadius: "var(--dash-radius-sm)", background: "var(--dash-bg-subtle)", border: "1px solid var(--dash-border-subtle)", fontSize: 11, color: "var(--dash-text-muted)" }}>
            Trigger status unavailable
          </div>
        )}
      </div>

      {/* Connected Devices */}
      <div className="dash-section-title">Connected Devices</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div className="dash-card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Monitor size={16} style={{ color: "var(--dash-accent)" }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--dash-text)" }}>Desktop</span>
            <span className="dash-badge dash-badge-success" style={{ marginLeft: "auto" }}>Local</span>
          </div>
          <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 8, fontFamily: "JetBrains Mono, monospace" }}>
            Windows {navigator.platform.includes("Win") ? "" : ""} • Electron
          </div>
        </div>
        <div className="dash-card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Smartphone size={16} style={{ color: "var(--dash-cyan)" }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--dash-text)" }}>Android</span>
            <span className="dash-badge dash-badge-neutral" style={{ marginLeft: "auto" }}>Companion</span>
          </div>
          <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 8, fontFamily: "JetBrains Mono, monospace" }}>
            Connect via Device Pairing
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemMonitorPage;
