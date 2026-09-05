import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useAIStore } from "@/stores/aiStore";
import {
  BarChart3,
  Cpu,
  HardDrive,
  Wifi,
  RefreshCw,
  MessageSquare,
  Bot,
  Zap,
  Clock,
  Database,
  Activity,
} from "lucide-react";
import { PageShell, PageHeader, GlassCard, StatusIndicator, SectionTitle } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

export const AnalyticsPage: React.FC = () => {
  const { systemStats } = useAIStore();
  const [metrics, setMetrics] = useState<any>({});
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [conversationCount, setConversationCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    try {
      const [r, h, c] = await Promise.all([
        authFetch(`${API}/status/overview`).then((r) => r.json()),
        authFetch(`${API.replace("/api/v1", "")}/health`)
          .then((r) => r.json())
          .catch(() => null),
        authFetch(`${API}/conversations?limit=1`)
          .then((r) => r.json())
          .catch(() => ({ total: 0 })),
      ]);
      setMetrics(r.details || {});
      setHealthStatus(h);
      setConversationCount(c.total || 0);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  const system = metrics.system || {};
  const snapshot = system.snapshot || {};

  const MetricBar = ({
    label,
    value,
    color,
    icon: Icon,
  }: {
    label: string;
    value: number;
    color: string;
    icon: any;
  }) => (
    <div style={{ marginBottom: 18 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 6,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Icon size={12} style={{ color }} />
          <span
            style={{
              fontSize: 12,
              color: "var(--dash-text-secondary)",
            }}
          >
            {label}
          </span>
        </div>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {value.toFixed(1)}%
        </span>
      </div>
      <div
        style={{
          height: 6,
          borderRadius: 3,
          background: "rgba(255,255,255,0.04)",
          overflow: "hidden",
        }}
      >
        <div
          className="metric-bar-fill"
          style={{
            height: "100%",
            width: `${Math.min(value, 100)}%`,
            borderRadius: 3,
            background: `linear-gradient(90deg, ${color}, ${color}cc)`,
            boxShadow: `0 0 8px ${color}40`,
          }}
        />
      </div>
    </div>
  );

  return (
    <PageShell glowColor="rgba(77, 148, 255, 0.05)">
      <PageHeader
        icon={<BarChart3 size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        title="System Analytics"
        subtitle="Real-time resource telemetry and performance metrics"
        badge={
          <StatusIndicator
            status={healthStatus?.status === "ok" ? "online" : "offline"}
            label={healthStatus?.status === "ok" ? "Live" : "Offline"}
          />
        }
        actions={
          <button onClick={fetchMetrics} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Quick Stats Row */}
        <div
          className="dash-stagger"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 12,
          }}
        >
          {[
            {
              label: "Conversations",
              value: conversationCount,
              icon: MessageSquare,
              color: "var(--dash-accent)",
            },
            {
              label: "Backend Uptime",
              value: healthStatus?.uptime
                ? `${Math.floor(healthStatus.uptime / 3600)}h`
                : "--",
              icon: Clock,
              color: "var(--dash-success)",
            },
            {
              label: "CPU Load",
              value: `${(systemStats?.cpu ?? 0).toFixed(0)}%`,
              icon: Cpu,
              color: "var(--dash-cyan)",
            },
            {
              label: "Memory Usage",
              value: `${(systemStats?.ram ?? 0).toFixed(0)}%`,
              icon: HardDrive,
              color: "var(--dash-accent-secondary)",
            },
          ].map((stat) => {
            const Icon = stat.icon;
            return (
              <GlassCard key={stat.label} padding={14}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 8,
                  }}
                >
                  <Icon size={14} style={{ color: stat.color }} />
                  <span
                    style={{
                      fontSize: 10,
                      color: "var(--dash-text-muted)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {stat.label}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 700,
                    color: "var(--dash-text)",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {stat.value}
                </div>
              </GlassCard>
            );
          })}
        </div>

        {/* Detailed metrics */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
          }}
        >
          {/* System Resources */}
          <GlassCard glow padding={18}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 16,
              }}
            >
              <Cpu size={16} style={{ color: "var(--dash-accent)" }} />
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "var(--dash-text)",
                }}
              >
                System Resources
              </span>
              <span
                style={{
                  fontSize: 10,
                  color: "var(--dash-text-muted)",
                  marginLeft: "auto",
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {snapshot.hostname || "localhost"}
              </span>
            </div>
            <MetricBar
              label="CPU Usage"
              value={snapshot.cpu_percent || systemStats?.cpu || 0}
              color="#3b82f6"
              icon={Cpu}
            />
            <MetricBar
              label="Memory (RAM)"
              value={snapshot.memory_percent || systemStats?.ram || 0}
              color="#8b5cf6"
              icon={HardDrive}
            />
            <MetricBar
              label="Disk Usage"
              value={snapshot.disk_percent || systemStats?.disk || 0}
              color="#22c55e"
              icon={Database}
            />
            {(snapshot.gpu_percent || systemStats?.gpu || 0) > 0 && (
              <MetricBar
                label="GPU Usage"
                value={snapshot.gpu_percent || systemStats?.gpu || 0}
                color="#f59e0b"
                icon={Zap}
              />
            )}
          </GlassCard>

          {/* Service Health */}
          <GlassCard glow padding={18}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 16,
              }}
            >
              <Wifi
                size={16}
                style={{
                  color:
                    healthStatus?.status === "ok"
                      ? "var(--dash-success)"
                      : "var(--dash-danger)",
                }}
              />
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "var(--dash-text)",
                }}
              >
                Service Health
              </span>
              <span
                className={`dash-badge ${
                  healthStatus?.status === "ok"
                    ? "dash-badge-success"
                    : "dash-badge-danger"
                }`}
                style={{ marginLeft: "auto" }}
              >
                {healthStatus?.status || "unknown"}
              </span>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 10,
              }}
            >
              {[
                {
                  label: "Backend",
                  value:
                    healthStatus?.status === "ok" ? "Online" : "Offline",
                },
                {
                  label: "Version",
                  value: healthStatus?.version || "--",
                },
                {
                  label: "Uptime",
                  value: healthStatus?.uptime
                    ? `${Math.floor(healthStatus.uptime / 60)}m`
                    : "--",
                },
                {
                  label: "Environment",
                  value: healthStatus?.environment || "dev",
                },
              ].map((item) => (
                <div
                  key={item.label}
                  style={{
                    padding: "10px 14px",
                    borderRadius: "var(--dash-radius-sm)",
                    background: "var(--dash-bg-subtle)",
                    border: "1px solid var(--dash-border-subtle)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 10,
                      color: "var(--dash-text-muted)",
                      marginBottom: 3,
                      fontFamily: "'JetBrains Mono', monospace",
                      letterSpacing: "0.05em",
                      textTransform: "uppercase",
                    }}
                  >
                    {item.label}
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: "var(--dash-text)",
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {item.value}
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      </div>
    </PageShell>
  );
};

export default AnalyticsPage;
