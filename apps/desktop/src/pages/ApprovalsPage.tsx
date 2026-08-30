import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import {
  CheckSquare,
  Shield,
  Check,
  X,
  RefreshCw,
  Clock,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";
import {
  PageShell,
  PageHeader,
  EmptyState,
  GlassCard,
  TabBar,
  StatusIndicator,
} from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Approval {
  id: string;
  action_type: string;
  description: string;
  status: string;
  created_at: string;
  risk_level?: string;
}

export const ApprovalsPage: React.FC = () => {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"pending" | "resolved">(
    "pending"
  );

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/desktop/approvals`);
      const data = await r.json();
      setApprovals(data.approvals || data || []);
    } catch {}
    setLoading(false);
  }, []);

  const approve = async (id: string) => {
    try {
      await authFetch(`${API}/desktop/approvals/${id}/approve`, {
        method: "POST",
      });
      fetchApprovals();
    } catch {}
  };

  const deny = async (id: string) => {
    try {
      await authFetch(`${API}/desktop/approvals/${id}/deny`, {
        method: "POST",
      });
      fetchApprovals();
    } catch {}
  };

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const pending = approvals.filter(
    (a) => a.status === "pending" || a.status === "PENDING"
  );
  const resolved = approvals.filter(
    (a) => a.status !== "pending" && a.status !== "PENDING"
  );

  return (
    <PageShell glowColor="rgba(251, 191, 36, 0.05)">
      <PageHeader
        icon={<Shield size={22} color="var(--dash-warning)" />}
        iconColor="var(--dash-warning)"
        iconBg="rgba(251, 191, 36, 0.12)"
        title="Security & Approvals"
        subtitle="Human-in-the-loop tool execution review"
        badge={
          pending.length > 0 ? (
            <span
              className="dash-badge-glow animate-status-pulse"
              style={{
                background: "rgba(251,191,36,0.12)",
                color: "var(--dash-warning)",
                border: "1px solid rgba(251,191,36,0.25)",
              }}
            >
              <AlertTriangle size={10} />
              {pending.length} pending
            </span>
          ) : undefined
        }
        actions={
          <button onClick={fetchApprovals} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Tabs */}
        <TabBar
          tabs={[
            {
              id: "pending",
              label: "Pending",
              count: pending.length,
              icon: <Clock size={12} />,
            },
            {
              id: "resolved",
              label: "Resolved",
              count: resolved.length,
              icon: <CheckSquare size={12} />,
            },
          ]}
          activeTab={activeTab}
          onTabChange={(id) => setActiveTab(id as "pending" | "resolved")}
        />

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
            <div>Loading approvals...</div>
          </div>
        ) : activeTab === "pending" ? (
          pending.length === 0 ? (
            <EmptyState
              icon={
                <ShieldCheck
                  size={28}
                  style={{ color: "var(--dash-success)" }}
                />
              }
              title="All Clear"
              description="No pending approvals. All actions are authorized."
            />
          ) : (
            <div className="dash-stagger">
              {pending.map((a) => (
                <GlassCard
                  key={a.id}
                  glow
                  padding={0}
                  className="animate-slide-up"
                >
                  <div
                    style={{
                      display: "flex",
                      gap: 14,
                      alignItems: "flex-start",
                      padding: "18px 20px",
                    }}
                  >
                    <div
                      style={{
                        width: 3,
                        minHeight: 40,
                        borderRadius: 2,
                        background: "var(--dash-warning)",
                        opacity: 0.6,
                        flexShrink: 0,
                      }}
                    />
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: 8,
                        }}
                      >
                        <div>
                          <span
                            style={{
                              fontSize: 14,
                              fontWeight: 600,
                              color: "var(--dash-text)",
                            }}
                          >
                            {a.action_type || "Action"}
                          </span>
                          <span
                            style={{
                              fontSize: 10,
                              color: "var(--dash-text-muted)",
                              marginLeft: 8,
                              fontFamily: "'JetBrains Mono', monospace",
                            }}
                          >
                            {a.created_at
                              ? new Date(a.created_at).toLocaleString()
                              : ""}
                          </span>
                        </div>
                        <span
                          className="dash-badge-glow"
                          style={{
                            background: "rgba(251,191,36,0.12)",
                            color: "var(--dash-warning)",
                            border: "1px solid rgba(251,191,36,0.25)",
                          }}
                        >
                          {a.risk_level || "review"}
                        </span>
                      </div>
                      <p
                        style={{
                          fontSize: 12,
                          color: "var(--dash-text-secondary)",
                          margin: "0 0 14px",
                          lineHeight: 1.5,
                        }}
                      >
                        {a.description}
                      </p>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          onClick={() => approve(a.id)}
                          style={{
                            padding: "7px 16px",
                            borderRadius: "var(--dash-radius-sm)",
                            border: "none",
                            background: "var(--dash-success)",
                            color: "white",
                            cursor: "pointer",
                            fontSize: 12,
                            fontWeight: 600,
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                            boxShadow: "0 0 12px var(--dash-success-glow)",
                            transition: "all var(--dash-transition-fast)",
                          }}
                        >
                          <Check size={13} /> Approve
                        </button>
                        <button
                          onClick={() => deny(a.id)}
                          style={{
                            padding: "7px 16px",
                            borderRadius: "var(--dash-radius-sm)",
                            border: "none",
                            background: "var(--dash-danger)",
                            color: "white",
                            cursor: "pointer",
                            fontSize: 12,
                            fontWeight: 600,
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                            boxShadow: "0 0 12px var(--dash-danger-glow)",
                            transition: "all var(--dash-transition-fast)",
                          }}
                        >
                          <X size={13} /> Deny
                        </button>
                      </div>
                    </div>
                  </div>
                </GlassCard>
              ))}
            </div>
          )
        ) : resolved.length === 0 ? (
          <EmptyState
            icon={<CheckSquare size={28} style={{ color: "var(--dash-text-muted)" }} />}
            title="No resolved approvals"
            description="Approved and denied actions will appear here."
          />
        ) : (
          <div className="dash-stagger">
            {resolved.map((a) => (
              <GlassCard key={a.id} padding={14} className="dash-card-glow">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 13,
                        color: "var(--dash-text)",
                        opacity: 0.7,
                      }}
                    >
                      {a.action_type}
                    </span>
                  </div>
                  <span
                    className="dash-badge-glow"
                    style={{
                      background:
                        a.status === "approved" || a.status === "APPROVED"
                          ? "rgba(34,197,94,0.12)"
                          : "rgba(239,68,68,0.12)",
                      color:
                        a.status === "approved" || a.status === "APPROVED"
                          ? "var(--dash-success)"
                          : "var(--dash-danger)",
                      border: `1px solid ${
                        a.status === "approved" || a.status === "APPROVED"
                          ? "rgba(34,197,94,0.25)"
                          : "rgba(239,68,68,0.25)"
                      }`,
                    }}
                  >
                    {a.status}
                  </span>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default ApprovalsPage;
