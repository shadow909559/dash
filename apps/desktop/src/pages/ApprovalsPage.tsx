import React, { useState, useEffect, useCallback, useRef } from "react";
import { authFetch } from "@/lib/api";
import { getWsClient } from "@/lib/wsClient";
import {
  CheckSquare,
  Shield,
  Check,
  X,
  RefreshCw,
  Clock,
  AlertTriangle,
  ShieldCheck,
  Bot,
  Bell,
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

// Assistant authority-engine record (POST /assistant/*, decisions.md #92)
interface AssistantApproval {
  id: string;
  action_kind: string;
  description: string;
  reason: string;
  risk_level: number;
  target: string;
  proposed?: string;
  consequences?: string[];
  status: string;
  requested_at: number;
  expires_at?: number;
  scope?: string;
}

interface MeetingAlert {
  meeting_id: string;
  alerts: string[];
  ts: number;
}

const RISK_LABEL: Record<number, string> = {
  0: "informational",
  1: "safe local",
  2: "low-risk external",
  3: "external comms",
  4: "high impact",
  5: "owner only",
};

export const ApprovalsPage: React.FC = () => {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"pending" | "resolved" | "assistant">(
    "pending"
  );
  // Assistant authority-engine approvals + live meeting alerts (WS-pushed)
  const [assistantPending, setAssistantPending] = useState<AssistantApproval[]>([]);
  const [assistantResolved, setAssistantResolved] = useState<AssistantApproval[]>([]);
  const [meetingAlerts, setMeetingAlerts] = useState<MeetingAlert[]>([]);

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

  const fetchAssistant = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([
        authFetch(`${API}/assistant/approvals?status=pending`),
        authFetch(`${API}/assistant/approvals?status=resolved`),
      ]);
      const pd = await p.json();
      const rd = await r.json();
      setAssistantPending(pd.approvals || []);
      setAssistantResolved(rd.approvals || []);
    } catch {}
  }, []);

  const resolveAssistant = async (id: string, decision: "approve" | "reject") => {
    try {
      await authFetch(`${API}/assistant/approvals/${id}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, scope: decision === "approve" ? "once" : null }),
      });
      fetchAssistant();
    } catch {}
  };

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  useEffect(() => {
    fetchAssistant();
  }, [fetchAssistant]);

  // Live updates over the existing /ws socket (decisions.md #92):
  // approval.created / approval.resolved / meeting.alert, best-effort —
  // the REST poll above remains the reconciliation fallback.
  const wsBound = useRef(false);
  useEffect(() => {
    if (wsBound.current) return;
    const ws = getWsClient();
    const onCreated = (data: Record<string, unknown>) => {
      const a = data.approval as AssistantApproval | undefined;
      if (!a?.id) return;
      setAssistantPending((prev) =>
        prev.some((x) => x.id === a.id) ? prev : [a, ...prev]
      );
    };
    const onResolved = (data: Record<string, unknown>) => {
      const a = data.approval as AssistantApproval | undefined;
      if (!a?.id) return;
      setAssistantPending((prev) => prev.filter((x) => x.id !== a.id));
      if (a.status === "granted" || a.status === "rejected") {
        setAssistantResolved((prev) => [a, ...prev.filter((x) => x.id !== a.id)]);
      }
    };
    const onMeetingAlert = (data: Record<string, unknown>) => {
      const meetingId = String(data.meeting_id || "");
      const alerts = (data.alerts as string[]) || [];
      if (!meetingId || alerts.length === 0) return;
      setMeetingAlerts((prev) =>
        [{ meeting_id: meetingId, alerts, ts: Date.now() }, ...prev].slice(0, 5)
      );
    };
    ws.on("approval.created", onCreated);
    ws.on("approval.resolved", onResolved);
    ws.on("meeting.alert", onMeetingAlert);
    wsBound.current = true;
    return () => {
      ws.off("approval.created", onCreated);
      ws.off("approval.resolved", onResolved);
      ws.off("meeting.alert", onMeetingAlert);
      wsBound.current = false;
    };
  }, []);

  const pending = approvals.filter(
    (a) => a.status === "pending" || a.status === "PENDING"
  );
  const resolved = approvals.filter(
    (a) => a.status !== "pending" && a.status !== "PENDING"
  );
  const assistantCount =
    assistantPending.length + meetingAlerts.length;

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
            {
              id: "assistant",
              label: "Assistant",
              count: assistantCount,
              icon: <Bot size={12} />,
            },
          ]}
          activeTab={activeTab}
          onTabChange={(id) => setActiveTab(id as "pending" | "resolved" | "assistant")}
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
        ) : activeTab === "assistant" ? (
          <div className="dash-stagger">
            {/* Live meeting alerts (pushed over /ws, private to the owner) */}
            {meetingAlerts.map((m, i) => (
              <GlassCard key={`alert-${m.meeting_id}-${i}`} padding={14} glow>
                <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <Bell size={15} style={{ color: "var(--dash-warning)", flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 4 }}>
                      Meeting {m.meeting_id} — live alerts ({new Date(m.ts).toLocaleTimeString()})
                    </div>
                    {m.alerts.map((a, j) => (
                      <p key={j} style={{ fontSize: 12, color: "var(--dash-text)", margin: "2px 0", lineHeight: 1.45 }}>
                        {a}
                      </p>
                    ))}
                  </div>
                </div>
              </GlassCard>
            ))}

            {assistantPending.length === 0 && meetingAlerts.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck size={28} style={{ color: "var(--dash-success)" }} />}
                title="Nothing needs your decision"
                description="Assistant approvals and live meeting alerts will appear here in real time."
              />
            ) : (
              assistantPending.map((a) => (
                <GlassCard key={a.id} glow padding={0} className="animate-slide-up">
                  <div style={{ padding: "18px 20px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <span style={{ fontSize: 14, fontWeight: 600, color: "var(--dash-text)", display: "flex", alignItems: "center", gap: 8 }}>
                        <Bot size={14} style={{ color: "var(--dash-accent)" }} />
                        {a.description}
                      </span>
                      <span
                        className="dash-badge-glow"
                        style={{
                          background: (a.risk_level || 0) >= 4 ? "rgba(239,68,68,0.12)" : "rgba(251,191,36,0.12)",
                          color: (a.risk_level || 0) >= 4 ? "var(--dash-danger)" : "var(--dash-warning)",
                          border: `1px solid ${(a.risk_level || 0) >= 4 ? "rgba(239,68,68,0.25)" : "rgba(251,191,36,0.25)"}`,
                        }}
                      >
                        {RISK_LABEL[a.risk_level] || `level ${a.risk_level}`}
                      </span>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--dash-text-secondary)", margin: "0 0 6px" }}>
                      <strong>Why:</strong> {a.reason}
                    </p>
                    {a.target ? (
                      <p style={{ fontSize: 12, color: "var(--dash-text-secondary)", margin: "0 0 6px" }}>
                        <strong>Target:</strong> {a.target}
                      </p>
                    ) : null}
                    {a.proposed ? (
                      <div style={{
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.06)",
                        borderRadius: "var(--dash-radius-sm)",
                        padding: "10px 12px",
                        margin: "8px 0",
                        fontSize: 12,
                        color: "var(--dash-text)",
                        whiteSpace: "pre-wrap",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {a.proposed}
                      </div>
                    ) : null}
                    {a.consequences?.length ? (
                      <ul style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: "6px 0 10px", paddingLeft: 18 }}>
                        {a.consequences.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    ) : null}
                    <div style={{ fontSize: 10, color: "var(--dash-text-muted)", marginBottom: 12 }}>
                      Requested {new Date(a.requested_at * 1000).toLocaleString()}
                      {a.expires_at ? ` · expires ${new Date(a.expires_at * 1000).toLocaleTimeString()}` : ""}
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        onClick={() => resolveAssistant(a.id, "approve")}
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
                        }}
                      >
                        <Check size={13} /> Approve once
                      </button>
                      <button
                        onClick={() => resolveAssistant(a.id, "reject")}
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
                        }}
                      >
                        <X size={13} /> Reject
                      </button>
                    </div>
                  </div>
                </GlassCard>
              ))
            )}

            {assistantResolved.length > 0 ? (
              <>
                <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 10, marginBottom: 4 }}>
                  RECENTLY RESOLVED
                </div>
                {assistantResolved.slice(0, 8).map((a) => (
                  <GlassCard key={`res-${a.id}`} padding={12}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 12, color: "var(--dash-text-secondary)" }}>
                        {a.description}
                      </span>
                      <span
                        className="dash-badge-glow"
                        style={{
                          background: a.status === "granted" ? "rgba(34,197,94,0.12)" : "rgba(63,169,245,0.12)",
                          color: a.status === "granted" ? "var(--dash-success)" : "var(--dash-text-muted)",
                          border: `1px solid ${a.status === "granted" ? "rgba(34,197,94,0.25)" : "rgba(255,255,255,0.08)"}`,
                        }}
                      >
                        {a.status}
                      </span>
                    </div>
                  </GlassCard>
                ))}
              </>
            ) : null}
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
                          aria-label="Approve action"
                          title="Approve"
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
                          aria-label="Deny action"
                          title="Deny"
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
                          : "rgba(63,169,245,0.12)",
                      color:
                        a.status === "approved" || a.status === "APPROVED"
                          ? "var(--dash-success)"
                          : "var(--dash-danger)",
                      border: `1px solid ${
                        a.status === "approved" || a.status === "APPROVED"
                          ? "rgba(34,197,94,0.25)"
                          : "rgba(63,169,245,0.25)"
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
