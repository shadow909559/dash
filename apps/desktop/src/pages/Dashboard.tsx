import { useEffect, useState, useRef, useMemo, memo } from "react";
import { useNavigate } from "react-router-dom";
import { SystemMonitorService, type SystemSnapshot } from "@/lib/systemMonitor";

function formatUptime(seconds: number | null): string {
  if (!seconds) return "---";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(" ");
}

function formatBytes(bytes: number | null): string {
  if (!bytes) return "---";
  const gb = bytes / (1024 ** 3);
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / (1024 ** 2)).toFixed(0)} MB`;
}

// Memoized components to prevent unnecessary re-renders
const CpuBar = memo(function CpuBar({ pct }: { pct: number | null }) {
  const v = pct ?? 0;
  const color = v > 80 ? "var(--danger)" : v > 50 ? "var(--warning)" : "var(--success)";
  return (
    <div className="metric-bar-track">
      <div className="metric-bar-fill" style={{ width: `${Math.min(v, 100)}%`, background: color }} />
    </div>
  );
});

const AnimatedValue = memo(function AnimatedValue({ value, suffix = "" }: { value: string | number | null | undefined; suffix?: string }) {
  const display = value ?? "---";
  return (
    <span className="metric-value">
      {display}{suffix}
    </span>
  );
});

const MetricRow = memo(function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{value}</span>
    </div>
  );
});

export default function Dashboard() {
  const navigate = useNavigate();
  const [healthData, setHealthData] = useState<{ status: string; version: string; uptime: number } | null>(null);
  const [isBackendOnline, setIsBackendOnline] = useState(false);
  const [sys, setSys] = useState<SystemSnapshot | null>(null);
  const [monitorConnected, setMonitorConnected] = useState(false);
  const monitorRef = useRef<SystemMonitorService | null>(null);


  // Health check
  useEffect(() => {
    async function fetchHealth() {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/v1/health", { headers: { "Content-Type": "application/json" } });
        const h = await res.json();
        setHealthData(h);
        setIsBackendOnline(true);
      } catch {
        setIsBackendOnline(false);
      }
    }
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // System monitor
  useEffect(() => {
    const monitor = new SystemMonitorService(
      (data) => {
        // Only update state if data actually changed to prevent unnecessary re-renders
        setSys(prevSys => {
          if (JSON.stringify(prevSys) === JSON.stringify(data)) {
            return prevSys;
          }
          return data;
        });
        setMonitorConnected(true);
      },
      (connected) => {
        setMonitorConnected(connected);
      }
    );
    monitorRef.current = monitor;
    return () => {
      monitor.disconnect();
      monitorRef.current = null;
    };
  }, []);

  // Memoize derived values to prevent recalculations on every render
  const cpuCoresText = useMemo(() => `${sys?.cpu?.cores_physical ?? "?"}P / ${sys?.cpu?.cores_logical ?? "?"}L`, [sys?.cpu?.cores_physical, sys?.cpu?.cores_logical]);
  const cpuFrequencyText = useMemo(() => sys?.cpu?.frequency_current_mhz ? `${sys.cpu.frequency_current_mhz} MHz` : "---", [sys?.cpu?.frequency_current_mhz]);
  const cpuTempText = useMemo(() => sys?.cpu?.temperature_celsius ? `${sys.cpu.temperature_celsius}°C` : "N/A", [sys?.cpu?.temperature_celsius]);
  const cpuArchitectureText = useMemo(() => sys?.cpu?.architecture || "---", [sys?.cpu?.architecture]);
  
  const ramUsedText = useMemo(() => sys?.ram?.used_gb ? `${sys.ram.used_gb} GB` : "---", [sys?.ram?.used_gb]);
  const ramFreeText = useMemo(() => sys?.ram?.free_gb ? `${sys.ram.free_gb} GB` : "---", [sys?.ram?.free_gb]);
  const ramTotalText = useMemo(() => sys?.ram?.total_gb ? `${sys.ram.total_gb} GB` : "---", [sys?.ram?.total_gb]);
  
  const storageTotalText = useMemo(() => sys?.storage?.total_gb ? `${sys.storage.total_gb} GB` : "---", [sys?.storage?.total_gb]);
  const storageUsedText = useMemo(() => sys?.storage?.used_gb ? `${sys.storage.used_gb} GB` : "---", [sys?.storage?.used_gb]);
  const storageFreeText = useMemo(() => sys?.storage?.free_gb ? `${sys.storage.free_gb} GB` : "---", [sys?.storage?.free_gb]);
  
  const networkDownloadText = useMemo(() => sys?.network?.download_speed_mbps ? `${sys.network.download_speed_mbps} Mbps` : "---", [sys?.network?.download_speed_mbps]);
  const networkUploadText = useMemo(() => sys?.network?.upload_speed_mbps ? `${sys.network.upload_speed_mbps} Mbps` : "---", [sys?.network?.upload_speed_mbps]);
  const networkIpText = useMemo(() => sys?.network?.ip_address || "---", [sys?.network?.ip_address]);
  const networkHostnameText = useMemo(() => sys?.network?.hostname || "---", [sys?.network?.hostname]);
  
  const systemOsText = useMemo(() => sys?.system?.os ? `${sys.system.os} ${sys.system.os_release ?? ""}` : "---", [sys?.system?.os, sys?.system?.os_release]);
  const systemUsernameText = useMemo(() => sys?.system?.username || "---", [sys?.system?.username]);
  const systemUptimeText = useMemo(() => sys?.system?.uptime_formatted || "---", [sys?.system?.uptime_formatted]);
  const systemHostnameText = useMemo(() => sys?.system?.hostname || "---", [sys?.system?.hostname]);
  
  const batteryStatusText = useMemo(() => sys?.battery?.charging ? "🔌 Charging" : "🔋 Discharging", [sys?.battery?.charging]);
  const batteryPercentText = useMemo(() => `${sys?.battery?.percent}%`, [sys?.battery?.percent]);
  const batteryRemainingText = useMemo(() => sys?.battery?.remaining_minutes ? `${Math.round(sys.battery.remaining_minutes)} min` : "", [sys?.battery?.remaining_minutes]);

  // Memoize storage drives to prevent unnecessary re-renders of the list
  const storageDrives = useMemo(() => 
    sys?.storage?.drives?.slice(0, 3).map((d, i) => (
      <div key={i} style={{ fontSize: 12, color: "var(--text-secondary)" }}>
        {d.device}: {d.used_gb}GB / {d.total_gb}GB ({d.percent}%)
      </div>
    )), [sys?.storage?.drives]);

  // Memoize GPU items to prevent unnecessary re-renders
  const gpuItems = useMemo(() => 
    sys?.gpu?.map((g, i) => (
      <div key={i}>
        <MetricRow label="Name" value={g.name || "Unknown"} />
        <div style={{ marginTop: 4 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ color: "var(--text-secondary)", fontSize: 13 }}>Usage</span>
            <span style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: 13 }}>
              {g.usage_percent ?? "N/A"}%
            </span>
          </div>
          <CpuBar pct={g.usage_percent ?? null} />
        </div>
        <MetricRow label="VRAM" value={g.vram_used_mb && g.vram_total_mb ? `${g.vram_used_mb}MB / ${g.vram_total_mb}MB` : "N/A"} />
        <MetricRow label="Temperature" value={g.temperature_celsius ? `${g.temperature_celsius}°C` : "N/A"} />
      </div>
    )), [sys?.gpu]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Dashboard</h2>
          <p className="page-subtitle">Real-time system monitoring</p>
        </div>
      </div>

      {/* Status row */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        <div className="glass-card animate-fade-in" style={{ padding: 20 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>🟢</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "var(--success)", marginBottom: 4 }}>
            {monitorConnected ? "Live" : "Connecting..."}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>System Monitor</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: 20 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>⚡</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
            <AnimatedValue value={sys?.cpu?.percentage} suffix="%" />
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>CPU Usage</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: 20 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>🧠</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
            <AnimatedValue value={sys?.ram?.percent} suffix="%" />
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>RAM Usage</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: 20 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>📦</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
            {healthData?.version || "---"}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Version</div>
        </div>
      </div>

      {/* System Metrics */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* CPU */}
        <div className="glass-card animate-fade-in" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            🔲 CPU
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ color: "var(--text-secondary)", fontSize: 13 }}>Usage</span>
                <span style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: 13 }}>
                  {sys?.cpu?.percentage ?? "---"}%
                </span>
              </div>
              <CpuBar pct={sys?.cpu?.percentage ?? null} />
            </div>
            <MetricRow label="Cores" value={cpuCoresText} />
            <MetricRow label="Frequency" value={cpuFrequencyText} />
            <MetricRow label="Temperature" value={cpuTempText} />
            <MetricRow label="Architecture" value={cpuArchitectureText} />
          </div>
        </div>

        {/* RAM */}
        <div className="glass-card animate-fade-in" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            💾 RAM
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ color: "var(--text-secondary)", fontSize: 13 }}>Usage</span>
                <span style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: 13 }}>
                  {sys?.ram?.used_gb ?? "---"}GB / {sys?.ram?.total_gb ?? "---"}GB
                </span>
              </div>
              <CpuBar pct={sys?.ram?.percent ?? null} />
            </div>
            <MetricRow label="Used" value={ramUsedText} />
            <MetricRow label="Free" value={ramFreeText} />
            <MetricRow label="Total" value={ramTotalText} />
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* Storage */}
        <div className="glass-card animate-fade-in" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            💽 Storage
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <MetricRow label="Total" value={storageTotalText} />
            <MetricRow label="Used" value={storageUsedText} />
            <MetricRow label="Free" value={storageFreeText} />
            {storageDrives}
          </div>
        </div>

        {/* GPU */}
        <div className="glass-card animate-fade-in" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            🎮 GPU
          </h3>
          {sys?.gpu && sys.gpu.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {gpuItems}
            </div>
          ) : (
            <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>No GPU detected</div>
          )}
        </div>
      </div>

      <div className="grid-2">
        {/* Network */}
        <div className="glass-card animate-fade-in" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            🌐 Network
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <MetricRow label="Download" value={networkDownloadText} />
            <MetricRow label="Upload" value={networkUploadText} />
            <MetricRow label="IP Address" value={networkIpText} />
            <MetricRow label="Hostname" value={networkHostnameText} />
          </div>
        </div>

        {/* System / Battery */}
        <div className="glass-card animate-fade-in" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            🖥️ System
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <MetricRow label="OS" value={systemOsText} />
            <MetricRow label="Username" value={systemUsernameText} />
            <MetricRow label="Uptime" value={systemUptimeText} />
            <MetricRow label="Hostname" value={systemHostnameText} />
            {sys?.battery && sys.battery.percent !== null && (
              <>
                <div style={{ borderTop: "1px solid var(--border-glass)", margin: "4px 0" }} />
                <MetricRow label="Battery" value={batteryStatusText} />
                <MetricRow label="Battery %" value={batteryPercentText} />
                {sys.battery.remaining_minutes && (
                  <MetricRow label="Remaining" value={batteryRemainingText} />
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}