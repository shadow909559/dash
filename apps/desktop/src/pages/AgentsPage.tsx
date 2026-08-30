import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { Bot, RefreshCw, Cpu, Activity, Zap } from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle, StatusIndicator } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Agent {
  id: string;
  name: string;
  status: string;
  task?: string;
  model?: string;
}

export const AgentsPage: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/ai-os/plans?limit=50`);
      const data = await r.json();
      setAgents(
        data.map((p: any) => ({
          id: p.plan_id,
          name: p.user_query?.substring(0, 50) || "Agent",
          status: p.status,
          task: p.steps?.[0]?.description || "",
          model: "ollama",
        }))
      );
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const activeCount = agents.filter((a) => a.status === "running").length;
  const completedCount = agents.filter((a) => a.status === "completed").length;

  return (
    <PageShell glowColor="rgba(34, 197, 94, 0.05)">
      <PageHeader
        icon={<Bot size={22} color="var(--dash-success)" />}
        iconColor="var(--dash-success)"
        iconBg="rgba(34, 197, 94, 0.12)"
        title="Multi-Agent System"
        subtitle="Sub-agent orchestration and role delegation"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "rgba(34, 197, 94, 0.10)",
              color: "var(--dash-success)",
              border: "1px solid rgba(34, 197, 94, 0.25)",
            }}
          >
            <Activity size={10} />
            {activeCount} active / {completedCount} done
          </span>
        }
        actions={
          <button onClick={fetchAgents} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Summary cards */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          {[
            {
              label: "Total Agents",
              value: agents.length,
              icon: Bot,
              color: "var(--dash-success)",
            },
            {
              label: "Running",
              value: activeCount,
              icon: Zap,
              color: "var(--dash-warning)",
            },
            {
              label: "Completed",
              value: completedCount,
              icon: Cpu,
              color: "var(--dash-accent)",
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
                    fontSize: 22,
                    fontWeight: 700,
                    color: stat.color,
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {stat.value}
                </div>
              </GlassCard>
            );
          })}
        </div>

        {/* Agent list */}
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
            <div>Loading agents...</div>
          </div>
        ) : agents.length === 0 ? (
          <EmptyState
            icon={<Bot size={28} style={{ color: "var(--dash-success)" }} />}
            title="No active agents"
            description="Use the Planner to create agent tasks, or ask DASH in chat to delegate work to sub-agents."
          />
        ) : (
          <div className="dash-stagger">
            <SectionTitle count={agents.length}>Agent Pool</SectionTitle>
            {agents.map((a) => {
              const statusMap: Record<
                string,
                "online" | "offline" | "warning" | "processing"
              > = {
                completed: "online",
                failed: "offline",
                running: "processing",
                pending: "warning",
              };
              return (
                <GlassCard key={a.id} padding={0} className="dash-card-glow">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                      padding: "14px 18px",
                    }}
                  >
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: "var(--dash-radius-sm)",
                        background: "rgba(34,197,94,0.12)",
                        border: "1px solid rgba(34,197,94,0.2)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <Bot size={16} style={{ color: "var(--dash-success)" }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: "var(--dash-text)",
                          marginBottom: 3,
                        }}
                      >
                        {a.name}
                      </div>
                      {a.task && (
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--dash-text-muted)",
                            fontFamily: "'JetBrains Mono', monospace",
                          }}
                        >
                          {a.task}
                        </div>
                      )}
                    </div>
                    <StatusIndicator
                      status={statusMap[a.status] || "offline"}
                      label={a.status}
                    />
                  </div>
                </GlassCard>
              );
            })}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default AgentsPage;
