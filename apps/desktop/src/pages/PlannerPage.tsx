import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import {
  CalendarDays,
  Plus,
  RefreshCw,
  CheckCircle2,
  Circle,
  AlertCircle,
  Clock,
  Play,
} from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Plan {
  plan_id: string;
  user_query: string;
  status: string;
  steps: Array<Record<string, any>>;
}

export const PlannerPage: React.FC = () => {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  const fetchPlans = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/ai-os/plans?limit=20`);
      setPlans(await r.json());
    } catch {}
    setLoading(false);
  }, []);

  const executePlan = async () => {
    if (!query.trim()) return;
    try {
      await authFetch(`${API}/ai-os/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: query }),
      });
      setQuery("");
      fetchPlans();
    } catch {}
  };

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  const statusColor = (s: string) =>
    s === "completed"
      ? "var(--dash-success)"
      : s === "failed"
        ? "var(--dash-danger)"
        : s === "running"
          ? "var(--dash-warning)"
          : "var(--dash-text-muted)";

  const StatusIcon = ({ s }: { s: string }) =>
    s === "completed" ? (
      <CheckCircle2 size={16} color="var(--dash-success)" />
    ) : s === "failed" ? (
      <AlertCircle size={16} color="var(--dash-danger)" />
    ) : s === "running" ? (
      <Play size={16} color="var(--dash-warning)" />
    ) : (
      <Circle size={16} color="var(--dash-text-muted)" />
    );

  return (
    <PageShell glowColor="rgba(77, 148, 255, 0.05)">
      <PageHeader
        icon={<CalendarDays size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        title="Executive Planner"
        subtitle="Multi-step goal decomposition and execution timelines"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "var(--dash-accent-glow)",
              color: "var(--dash-accent)",
              border: "1px solid var(--dash-border-accent)",
            }}
          >
            <Clock size={10} />
            {plans.length} plans
          </span>
        }
        actions={
          <button onClick={fetchPlans} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Input */}
        <GlassCard glow padding={16}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && executePlan()}
              placeholder="Describe a goal or task to plan..."
              className="dash-input-ultron"
              style={{ flex: 1 }}
            />
            <button
              onClick={executePlan}
              disabled={!query.trim()}
              className="dash-btn-primary"
            >
              <Plus size={14} /> Execute
            </button>
          </div>
        </GlassCard>

        {/* Plans list */}
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
            <div>Loading plans...</div>
          </div>
        ) : plans.length === 0 ? (
          <EmptyState
            icon={
              <CalendarDays size={28} style={{ color: "var(--dash-accent)" }} />
            }
            title="No plans yet"
            description="Describe a goal above and DASH will decompose it into executable steps."
          />
        ) : (
          <div className="dash-stagger">
            <SectionTitle count={plans.length}>Execution Plans</SectionTitle>
            {plans.map((p) => (
              <GlassCard key={p.plan_id} padding={0} className="dash-card-glow">
                <div style={{ padding: "16px 20px" }}>
                  {/* Header */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      marginBottom: 12,
                    }}
                  >
                    <StatusIcon s={p.status} />
                    <span
                      style={{
                        fontSize: 14,
                        fontWeight: 600,
                        color: "var(--dash-text)",
                        flex: 1,
                      }}
                    >
                      {p.user_query}
                    </span>
                    <span
                      className="dash-badge-glow"
                      style={{
                        background: `${statusColor(p.status)}15`,
                        color: statusColor(p.status),
                        border: `1px solid ${statusColor(p.status)}30`,
                      }}
                    >
                      {p.status}
                    </span>
                  </div>

                  {/* Steps timeline */}
                  {p.steps && p.steps.length > 0 && (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 0,
                        marginLeft: 6,
                        borderLeft: "2px solid var(--dash-border)",
                        paddingLeft: 16,
                      }}
                    >
                      {p.steps.map((step, i) => (
                        <div
                          key={i}
                          style={{
                            position: "relative",
                            padding: "8px 0",
                          }}
                        >
                          {/* Timeline dot */}
                          <div
                            style={{
                              position: "absolute",
                              left: -22,
                              top: 12,
                              width: 10,
                              height: 10,
                              borderRadius: "50%",
                              background:
                                i < p.steps.length - 1
                                  ? "var(--dash-surface-active)"
                                  : statusColor(p.status),
                              border: `2px solid ${
                                i < p.steps.length - 1
                                  ? "var(--dash-border)"
                                  : statusColor(p.status)
                              }`,
                            }}
                          />
                          <div
                            style={{
                              fontSize: 12,
                              color: "var(--dash-text-secondary)",
                              fontFamily: "'JetBrains Mono', monospace",
                              lineHeight: 1.5,
                            }}
                          >
                            <span
                              style={{
                                color: "var(--dash-text-muted)",
                                marginRight: 8,
                              }}
                            >
                              {i + 1}.
                            </span>
                            {step.description ||
                              step.name ||
                              JSON.stringify(step).substring(0, 80)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default PlannerPage;
