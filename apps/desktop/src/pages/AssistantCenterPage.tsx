import React, { useState, useEffect, useCallback, useRef } from "react";
import { authFetch } from "@/lib/api";
import { getWsClient } from "@/lib/wsClient";
import { useAIStore } from "@/stores/aiStore";
import {
  Radar,
  RefreshCw,
  BellRing,
  UserCheck,
  CalendarClock,
  OctagonX,
  Check,
  X,
  Search,
  Briefcase,
  Activity,
} from "lucide-react";
import {
  PageShell,
  PageHeader,
  EmptyState,
  GlassCard,
  SectionTitle,
  StatusIndicator,
} from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Briefing {
  text: string;
  meetings_today: { id: string; title: string; when: number }[];
  pending_approvals: number;
  overdue_actions: number;
  tasks_running: number;
  tasks_failed: number;
}

interface Attention {
  counts: { urgent: number; important: number; waiting: number };
  urgent: { kind: string; text: string }[];
  important: { kind: string; text: string }[];
  waiting: { kind: string; text: string }[];
}

interface FollowUp {
  id: string;
  client_id: string;
  reason: string;
  status: string;
  created_at: number;
}

interface ControlStatus {
  active: boolean;
  since: number | null;
  by: string | null;
}

interface CapabilityReport {
  overall: string;
  degraded_mode: boolean;
  message: string;
  systems: Record<string, {
    state: string;
    detail?: string;
    reason?: string;
    queued_notifications?: number;
    active_devices?: number;
  }>;
}

interface MetricsReport {
  latency: Record<string, { n: number; avg_ms: number; median_ms: number; p95_ms: number; p99_ms: number }>;
  counters: Record<string, number>;
  errors: Record<string, number>;
}

interface AgentTask {
  id: string;
  goal: string;
  status: string;
  progress: number;
  pending_confirmation: boolean;
  created_at: number;
  updated_at: number;
  final_report: string | null;
}

interface TaskStep {
  id: string;
  index: number;
  description: string;
  tool: string | null;
  risk: string;
  status: string;
  attempts: number;
  max_attempts: number;
  result_summary: string | null;
  error: string | null;
  verification: { status: string; detail: string };
}

interface TaskEvent {
  ts: number;
  type: string;
  detail: string;
}

interface AgentTaskDetail extends AgentTask {
  steps: TaskStep[];
  events: TaskEvent[];
}

interface TimelineEvent {
  ts: number;
  type: string;
  text: string;
  status: string | null;
  id?: string;
  client_id?: string | null;
}

interface TimelineData {
  events: TimelineEvent[];
  total: number;
}

/** One real presence transition from /assistant/presence/history (#123). */
interface PresenceTransition {
  state: string;
  source: string;
  detail: string;
  at: number;
}

function ts(n: number | null | undefined): string {
  return n ? new Date(n * 1000).toLocaleString() : "—";
}

export const AssistantCenterPage: React.FC = () => {
  const { presenceState, presenceSource, presenceDetail } = useAIStore();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [attention, setAttention] = useState<Attention | null>(null);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [control, setControl] = useState<ControlStatus | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityReport | null>(null);
  const [metrics, setMetrics] = useState<MetricsReport | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [presenceHistory, setPresenceHistory] = useState<PresenceTransition[]>([]);
  const [timelineType, setTimelineType] = useState<string>("all");
  const [expandedTask, setExpandedTask] = useState<string | null>(null);
  const [taskDetail, setTaskDetail] = useState<AgentTaskDetail | null>(null);
  const [taskDetailLoading, setTaskDetailLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [confirmStop, setConfirmStop] = useState(false);
  const [flash, setFlash] = useState("");
  const wsBound = useRef(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [b, a, f, c, cap, met, t, tl, ph] = await Promise.all([
        authFetch(`${API}/assistant/briefing`),
        authFetch(`${API}/assistant/attention`),
        authFetch(`${API}/assistant/follow-ups?status=pending`),
        authFetch(`${API}/assistant/control/status`),
        authFetch(`${API}/assistant/capabilities`),
        authFetch(`${API}/assistant/metrics`),
        authFetch(`${API}/agent/tasks`),
        authFetch(`${API}/assistant/timeline?limit=120`),
        authFetch(`${API}/assistant/presence/history?limit=20`),
      ]);
      if (b.ok) setBriefing(await b.json());
      if (a.ok) setAttention(await a.json());
      if (f.ok) setFollowUps((await f.json()).follow_ups || []);
      if (c.ok) setControl(await c.json());
      if (cap.ok) setCapabilities(await cap.json());
      if (met.ok) setMetrics(await met.json());
      if (t.ok) setTasks((await t.json()).tasks || []);
      if (tl.ok) setTimeline(await tl.json());
      if (ph.ok) setPresenceHistory(await ph.json());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Live proactive digests + approval events refresh the view instantly
  useEffect(() => {
    if (wsBound.current) return;
    const ws = getWsClient();
    const refresh = () => fetchAll();
    ws.on("proactive.digest", refresh);
    ws.on("approval.created", refresh);
    ws.on("approval.resolved", refresh);
    // Task orchestrator pushes keep the task center + timeline live (#126)
    const taskEvents = ["task.created", "task.plan_ready", "task.completed",
      "task.failed", "task.waiting_confirmation", "task.recovery"];
    taskEvents.forEach((e) => ws.on(e, refresh));
    // Presence transitions keep the presence panel live (#123)
    ws.on("presence.update", refresh);
    wsBound.current = true;
    return () => {
      ws.off("proactive.digest", refresh);
      ws.off("approval.created", refresh);
      ws.off("approval.resolved", refresh);
      taskEvents.forEach((e) => ws.off(e, refresh));
      ws.off("presence.update", refresh);
      wsBound.current = false;
    };
  }, [fetchAll]);

  const resolveFollowUp = async (id: string, status: "sent" | "dismissed") => {
    try {
      await authFetch(`${API}/assistant/follow-ups/${id}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      fetchAll();
    } catch {}
  };

  const emergencyStop = async () => {
    setConfirmStop(false);
    try {
      const r = await authFetch(`${API}/assistant/control/stop`, { method: "POST" });
      const body = await r.json().catch(() => ({}));
      if (r.ok) {
        setFlash(
          `Emergency stop active — ${body.paused_tasks?.length ?? 0} task(s) paused, ` +
          `${body.revoked_approvals?.length ?? 0} approval(s) revoked, outbound sends gated.`
        );
      } else {
        setFlash(body.detail || "Stop failed");
      }
      fetchAll();
    } catch {
      setFlash("Network error during emergency stop");
    }
  };

  const resume = async () => {
    try {
      await authFetch(`${API}/assistant/control/resume`, { method: "POST" });
      setFlash("Gate lifted. Paused tasks remain paused until you resume each one.");
      fetchAll();
    } catch {}
  };

  const taskAction = async (id: string, action: "pause" | "resume" | "cancel") => {
    try {
      const r = await authFetch(`${API}/agent/task/${id}/${action}`, { method: "POST" });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setFlash(body.detail || `Task ${action} failed`);
      }
      fetchAll();
      // Keep the drill-down truthful after an action
      if (expandedTask === id) await openTaskDetail(id);
    } catch {
      setFlash("Network error during task action");
    }
  };

  // Inspect (#126/#71): real steps, verification, and event history
  const openTaskDetail = async (id: string) => {
    if (expandedTask === id) { setExpandedTask(null); setTaskDetail(null); return; }
    setExpandedTask(id);
    setTaskDetailLoading(true);
    try {
      const r = await authFetch(`${API}/agent/task/${id}`);
      setTaskDetail(r.ok ? await r.json() : null);
    } catch { setTaskDetail(null); }
    setTaskDetailLoading(false);
  };

  return (
    <PageShell glowColor="rgba(168, 85, 247, 0.05)">
      <PageHeader
        icon={<Radar size={22} color="var(--dash-accent-secondary)" />}
        iconColor="var(--dash-accent-secondary)"
        iconBg="rgba(168,85,247,0.12)"
        title="Assistant Center"
        subtitle="What DASH is doing, what needs you, and total control"
        badge={
          control?.active ? (
            <span className="dash-badge-glow animate-status-pulse" style={{
              background: "rgba(239,68,68,0.12)",
              color: "var(--dash-danger)",
              border: "1px solid rgba(239,68,68,0.25)",
            }}>
              <OctagonX size={10} /> STOP ACTIVE
            </span>
          ) : undefined
        }
        actions={
          <button onClick={fetchAll} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {loading ? (
          <div style={{ textAlign: "center", padding: 48, color: "var(--dash-text-muted)" }}>
            <RefreshCw size={18} className="animate-rotate" style={{ marginBottom: 10 }} />
            <div>Loading assistant state...</div>
          </div>
        ) : (
          <>
            {/* Emergency stop */}
            <SectionTitle>Owner control</SectionTitle>
            <GlassCard padding={16} glow={!!control?.active}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <StatusIndicator
                  status={control?.active ? "offline" : "online"}
                  label={control?.active ? "Autonomy STOPPED" : "Autonomy normal"}
                />
                <span style={{ fontSize: 11, color: "var(--dash-text-muted)", flex: 1 }}>
                  {control?.active
                    ? `Since ${ts(control.since)} — tasks paused, approvals revoked, sends gated.`
                    : "Stop pauses every autonomous task, revokes pending approvals, and gates outbound sends."}
                </span>
                {control?.active ? (
                  <button onClick={resume} style={resumeBtnStyle}>
                    <Check size={13} /> Lift gate
                  </button>
                ) : confirmStop ? (
                  <>
                    <span style={{ fontSize: 11, color: "var(--dash-danger)" }}>
                      Pause all tasks and revoke approvals?
                    </span>
                    <button onClick={emergencyStop} style={stopBtnStyle}>
                      <OctagonX size={13} /> Confirm stop
                    </button>
                    <button onClick={() => setConfirmStop(false)} className="dash-btn-ghost">
                      Cancel
                    </button>
                  </>
                ) : (
                  <button onClick={() => setConfirmStop(true)} style={stopBtnStyle}>
                    <OctagonX size={13} /> Emergency stop
                  </button>
                )}
              </div>
              {flash ? (
                <p style={{ fontSize: 11, color: "var(--dash-text-secondary)", margin: "10px 0 0" }}>
                  {flash}
                </p>
              ) : null}
            </GlassCard>

            {/* Presence — the one authoritative signal (#117/#123) */}
            <SectionTitle>Presence</SectionTitle>
            <GlassCard padding={16}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <StatusIndicator
                  status={presenceState && presenceState !== "idle" ? "online" : "offline"}
                  label={(presenceState || "idle").replace(/_/g, " ").toUpperCase()}
                />
                <span style={{ fontSize: 11, color: "var(--dash-text-muted)", flex: 1 }}>
                  {presenceSource
                    ? `via ${presenceSource}${presenceDetail ? ` — ${presenceDetail}` : ""}`
                    : "No active claims — fused from voice, tasks, approvals, and meetings."}
                </span>
              </div>
              {presenceHistory.length > 0 ? (
                <div style={{ marginTop: 12, borderTop: "1px solid var(--dash-border, rgba(255,255,255,0.06))", paddingTop: 10 }}>
                  {presenceHistory.slice().reverse().slice(0, 8).map((h, i) => (
                    <div key={`${h.at}-${i}`} style={{
                      display: "flex", gap: 10, alignItems: "baseline",
                      fontSize: 11, padding: "3px 0", color: "var(--dash-text-secondary)",
                    }}>
                      <span style={{ color: "var(--dash-text-muted)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                        {new Date(h.at * 1000).toLocaleTimeString()}
                      </span>
                      <span style={{ color: "var(--dash-accent)", flexShrink: 0, minWidth: 90 }}>
                        {h.state.replace(/_/g, " ")}
                      </span>
                      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {h.source ? `${h.source}${h.detail ? ` — ${h.detail}` : ""}` : "auto-released"}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: "10px 0 0" }}>
                  No transitions recorded yet this session.
                </p>
              )}
            </GlassCard>

            {/* Daily briefing */}
            <SectionTitle>Daily briefing</SectionTitle>
            {briefing ? (
              <GlassCard padding={16}>
                <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <Briefcase size={15} style={{ color: "var(--dash-accent)", marginTop: 2, flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    {briefing.text.split("\n").map((line, i) => (
                      <p key={i} style={{ fontSize: 12, color: "var(--dash-text)", margin: "2px 0", lineHeight: 1.5 }}>
                        {line}
                      </p>
                    ))}
                    {briefing.meetings_today.length > 0 ? (
                      <div style={{ marginTop: 8 }}>
                        {briefing.meetings_today.map((m) => (
                          <div key={m.id} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 11, color: "var(--dash-text-muted)" }}>
                            <CalendarClock size={11} />
                            {m.title} — {new Date(m.when * 1000).toLocaleTimeString()}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              </GlassCard>
            ) : (
              <p style={muted}>Briefing unavailable.</p>
            )}

            {/* Attention */}
            <SectionTitle>What needs your attention</SectionTitle>
            {attention ? (
              attention.counts.urgent + attention.counts.important + attention.counts.waiting === 0 ? (
                <EmptyState
                  icon={<Activity size={28} style={{ color: "var(--dash-success)" }} />}
                  title="All clear"
                  description="Nothing needs your attention right now."
                />
              ) : (
                <div className="dash-stagger">
                  {(["urgent", "important", "waiting"] as const).map((bucket) =>
                    attention[bucket].map((item, i) => (
                      <GlassCard
                        key={`${bucket}-${item.kind}-${i}`}
                        padding={12}
                        glow={bucket === "urgent"}
                      >
                        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                          <span className="dash-badge-glow" style={{
                            background:
                              bucket === "urgent" ? "rgba(239,68,68,0.12)"
                              : bucket === "important" ? "rgba(251,191,36,0.12)"
                              : "rgba(63,169,245,0.12)",
                            color:
                              bucket === "urgent" ? "var(--dash-danger)"
                              : bucket === "important" ? "var(--dash-warning)"
                              : "var(--dash-accent)",
                            border: "1px solid rgba(255,255,255,0.08)",
                            flexShrink: 0,
                          }}>
                            {bucket}
                          </span>
                          <span style={{ fontSize: 12, color: "var(--dash-text)" }}>
                            {item.text}
                          </span>
                        </div>
                      </GlassCard>
                    ))
                  )}
                </div>
              )
            ) : (
              <p style={muted}>Attention data unavailable.</p>
            )}

            {/* Follow-ups */}
            <SectionTitle count={followUps.length}>Client follow-ups owed</SectionTitle>
            {followUps.length === 0 ? (
              <p style={muted}>No client is waiting on a reply.</p>
            ) : (
              <div className="dash-stagger">
                {followUps.map((f) => (
                  <GlassCard key={f.id} padding={12}>
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <BellRing size={13} style={{ color: "var(--dash-warning)", flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, color: "var(--dash-text)" }}>{f.reason}</div>
                        <div style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>
                          client {f.client_id} · since {ts(f.created_at)}
                        </div>
                      </div>
                      <button onClick={() => resolveFollowUp(f.id, "sent")} style={miniBtnStyle} title="Mark follow-up sent">
                        <UserCheck size={12} /> Sent
                      </button>
                      <button onClick={() => resolveFollowUp(f.id, "dismissed")} className="dash-btn-ghost" title="Dismiss">
                        <X size={12} />
                      </button>
                    </div>                      </GlassCard>
                ))}
              </div>
            )}

            {/* Autonomous task center (#126): live status + owner control */}
            <SectionTitle count={tasks.length}>Autonomous tasks</SectionTitle>
            {tasks.length === 0 ? (
              <GlassCard padding={14}>
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)", margin: 0 }}>
                  No autonomous tasks yet. DASH creates them from goals and
                  confirmed requirements — every step is verified and audited.
                </p>
              </GlassCard>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {tasks.map((t) => (
                  <GlassCard key={t.id} padding={12}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span style={{
                        fontSize: 10, padding: "2px 8px", borderRadius: 999,
                        fontWeight: 700, letterSpacing: 0.3,
                        color: t.status === "completed" ? "var(--dash-success)"
                          : t.status === "failed" || t.status === "cancelled" ? "var(--dash-danger)"
                          : t.status === "paused" ? "var(--dash-warning)"
                          : "var(--dash-accent-secondary)",
                        background: "rgba(255,255,255,0.04)",
                      }}>
                        {t.status.replace(/_/g, " ").toUpperCase()}
                      </span>
                      <span style={{ fontSize: 12, color: "var(--dash-text)", flex: 1, minWidth: 200 }}>
                        {t.goal.length > 90 ? `${t.goal.slice(0, 90)}…` : t.goal}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>
                        {Math.round((t.progress || 0) * 100)}%
                      </span>
                      <span style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>
                        {ts(t.updated_at)}
                      </span>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button onClick={() => openTaskDetail(t.id)} className="dash-btn-ghost"
                                title={expandedTask === t.id ? "Hide details" : "Inspect steps, verification, history"}>
                          <Search size={12} />
                        </button>
                        {t.status === "paused" && (
                          <button onClick={() => taskAction(t.id, "resume")} className="dash-btn-ghost" title="Resume task">
                            <Check size={12} />
                          </button>
                        )}
                        {t.status === "running" && (
                          <button onClick={() => taskAction(t.id, "pause")} className="dash-btn-ghost" title="Pause task">
                            <CalendarClock size={12} />
                          </button>
                        )}
                        {["completed", "failed", "cancelled"].includes(t.status) ? null : (
                          <button onClick={() => taskAction(t.id, "cancel")} className="dash-btn-ghost" title="Cancel task">
                            <X size={12} />
                          </button>
                        )}
                      </div>
                    </div>
                    {t.pending_confirmation && (
                      <p style={{ fontSize: 11, color: "var(--dash-warning)", margin: "6px 0 0" }}>
                        Waiting for your confirmation — approve in the task view or via chat.
                      </p>
                    )}
                    {t.final_report && t.status === "failed" && (
                      <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: "6px 0 0" }}>
                        {String(t.final_report).slice(0, 160)}
                      </p>
                    )}
                    {expandedTask === t.id && (
                      <div style={{ marginTop: 10, borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: 10 }}>
                        {taskDetailLoading ? (
                          <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: 0 }}>Loading task detail…</p>
                        ) : taskDetail ? (
                          <>
                            <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.4, color: "var(--dash-text-muted)", margin: "0 0 6px", textTransform: "uppercase" }}>
                              Steps — execution & verification (#64)
                            </p>
                            {taskDetail.steps.length === 0 ? (
                              <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: "0 0 10px" }}>No steps planned yet.</p>
                            ) : (
                              <div style={{ display: "grid", gap: 4, marginBottom: 10 }}>
                                {taskDetail.steps.map((s) => (
                                  <div key={s.id} style={{
                                    padding: "6px 8px", borderRadius: 6, fontSize: 11,
                                    background: "rgba(255,255,255,0.03)",
                                  }}>
                                    <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                                      <span style={{
                                        fontSize: 10, fontWeight: 700, flexShrink: 0,
                                        color: s.status === "completed" ? "var(--dash-success)"
                                          : s.status === "failed" ? "var(--dash-danger)"
                                          : s.status === "running" ? "var(--dash-accent-secondary)"
                                          : "var(--dash-text-muted)",
                                      }}>
                                        {s.status.replace(/_/g, " ")}
                                      </span>
                                      <span style={{ color: "var(--dash-text)", flex: 1, minWidth: 160 }}>
                                        {s.index + 1}. {s.description}
                                      </span>
                                      {s.tool && (
                                        <code style={{ fontSize: 10, color: "var(--dash-text-secondary)" }}>{s.tool}</code>
                                      )}
                                      {s.risk !== "safe" && (
                                        <span style={{ fontSize: 10, color: s.risk === "high" ? "var(--dash-danger)" : "var(--dash-warning)" }}>
                                          risk: {s.risk}
                                        </span>
                                      )}
                                      <span style={{
                                        fontSize: 10, flexShrink: 0,
                                        color: s.verification.status === "verified" ? "var(--dash-success)"
                                          : s.verification.status === "not_run" ? "var(--dash-text-muted)"
                                          : "var(--dash-warning)",
                                      }}>
                                        ✓ {s.verification.status.replace(/_/g, " ")}
                                      </span>
                                      <span style={{ fontSize: 10, color: "var(--dash-text-muted)", flexShrink: 0 }}>
                                        attempt {s.attempts}/{s.max_attempts}
                                      </span>
                                    </div>
                                    {(s.error || s.result_summary) && (
                                      <div style={{ fontSize: 10, color: s.error ? "var(--dash-danger)" : "var(--dash-text-muted)", marginTop: 3 }}>
                                        {s.error || s.result_summary}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                            <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.4, color: "var(--dash-text-muted)", margin: "0 0 6px", textTransform: "uppercase" }}>
                              Event history (#71)
                            </p>
                            {taskDetail.events && taskDetail.events.length > 0 ? (
                              <div style={{ display: "grid", gap: 2 }}>
                                {taskDetail.events.slice(-12).reverse().map((e, i) => (
                                  <div key={i} style={{ display: "flex", gap: 8, fontSize: 10, alignItems: "baseline" }}>
                                    <span style={{ color: "var(--dash-text-muted)", flexShrink: 0 }}>
                                      {new Date(e.ts * 1000).toLocaleTimeString()}
                                    </span>
                                    <span style={{ color: "var(--dash-accent-secondary)", flexShrink: 0, fontWeight: 600 }}>
                                      {e.type.replace(/_/g, " ")}
                                    </span>
                                    <span style={{ color: "var(--dash-text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                      {e.detail}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: 0 }}>No events recorded yet.</p>
                            )}
                          </>
                        ) : (
                          <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: 0 }}>Task detail unavailable.</p>
                        )}
                      </div>
                    )}
                  </GlassCard>
                ))}
              </div>
            )}

            {/* Unified activity timeline (#127): filter by type */}
            <SectionTitle count={timeline?.total}>Activity timeline</SectionTitle>
            {timeline && timeline.events.length > 0 ? (
              <GlassCard padding={14}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <select
                    value={timelineType}
                    onChange={(e) => setTimelineType(e.target.value)}
                    style={{
                      fontSize: 11, padding: "4px 8px", borderRadius: 6,
                      background: "rgba(255,255,255,0.04)",
                      color: "var(--dash-text)", border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  >
                    <option value="all">All types</option>
                    {Array.from(new Set(timeline.events.map((e) => e.type))).sort().map((t) => (
                      <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                  <span style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>
                    {timeline.total} total events
                  </span>
                </div>
                <div style={{ display: "grid", gap: 4, maxHeight: 320, overflowY: "auto" }}>
                  {timeline.events
                    .filter((e) => timelineType === "all" || e.type === timelineType)
                    .slice(0, 60)
                    .map((e, i) => (
                      <div key={`${e.id}-${i}`} style={{
                        display: "flex", gap: 8, alignItems: "baseline",
                        fontSize: 11, padding: "4px 6px", borderRadius: 4,
                        background: i % 2 ? "rgba(255,255,255,0.02)" : "transparent",
                      }}>
                        <span style={{ color: "var(--dash-text-muted)", flexShrink: 0 }}>
                          {new Date(e.ts * 1000).toLocaleTimeString()}
                        </span>
                        <span style={{
                          color: "var(--dash-accent-secondary)", flexShrink: 0,
                          fontSize: 10, fontWeight: 600, minWidth: 90,
                        }}>
                          {e.type.replace(/_/g, " ")}
                        </span>
                        <span style={{ color: "var(--dash-text-secondary)", flex: 1 }}>
                          {e.text}
                        </span>
                        {e.status && (
                          <span style={{ color: "var(--dash-text-muted)", flexShrink: 0 }}>{e.status}</span>
                        )}
                      </div>
                    ))}
                </div>
              </GlassCard>
            ) : (
              <GlassCard padding={14}>
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)", margin: 0 }}>
                  No recorded activity yet — requirements, communications,
                  approvals, meetings, and task events appear here as they happen.
                </p>
              </GlassCard>
            )}

            {/* Diagnostics: degraded mode + measured latency (#90/#114) */}
            <SectionTitle>Diagnostics</SectionTitle>
            {capabilities ? (
              <GlassCard padding={16}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <StatusIndicator
                    status={capabilities.degraded_mode ? "offline" : "online"}
                    label={capabilities.degraded_mode ? "Degraded mode" : "All systems operational"}
                  />
                  <span style={{ fontSize: 11, color: "var(--dash-text-muted)", flex: 1 }}>
                    {capabilities.message}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 6, marginTop: 10 }}>
                  {Object.entries(capabilities.systems).map(([name, sys]) => (
                    <div key={name} style={{
                      fontSize: 11, padding: "6px 8px", borderRadius: 6,
                      background: "rgba(255,255,255,0.03)",
                      border: `1px solid ${sys.state === "operational" ? "rgba(34,197,94,0.2)" : "rgba(234,179,8,0.25)"}`,
                    }}>
                      <span style={{ color: sys.state === "operational" ? "var(--dash-success)" : "var(--dash-warning)", fontWeight: 600 }}>
                        {sys.state}
                      </span>
                      <span style={{ color: "var(--dash-text-secondary)" }}> · {name.replace(/_/g, " ")}</span>
                      {name === "push_transport" && sys.queued_notifications !== undefined && (
                        <span style={{ fontSize: 10, color: "var(--dash-text-muted)", marginLeft: 6 }}>
                          queued {sys.queued_notifications} · devices {sys.active_devices ?? 0}
                        </span>
                      )}
                      {(sys.detail || sys.reason) && (
                        <div style={{ fontSize: 10, color: "var(--dash-text-muted)", marginTop: 2 }}>
                          {sys.detail || sys.reason}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </GlassCard>
            ) : null}
            {metrics && Object.keys(metrics.latency).length > 0 ? (
              <GlassCard padding={16}>
                <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: "0 0 8px" }}>
                  Measured latency (ms, avg / p95) — real samples, never claimed:
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 6 }}>
                  {Object.entries(metrics.latency).map(([kind, s]) => (
                    <div key={kind} style={{
                      fontSize: 11, padding: "6px 8px", borderRadius: 6,
                      background: "rgba(255,255,255,0.03)",
                    }}>
                      <span style={{ color: "var(--dash-text)", fontWeight: 600 }}>{kind.replace(/_/g, " ")}</span>
                      <div style={{ color: "var(--dash-text-secondary)", marginTop: 2 }}>
                        {s.avg_ms} / {s.p95_ms} ms · n={s.n}
                      </div>
                    </div>
                  ))}
                </div>
              </GlassCard>
            ) : null}
          </>
        )}
      </div>
    </PageShell>
  );
};

const stopBtnStyle: React.CSSProperties = {
  padding: "7px 14px",
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
};

const resumeBtnStyle: React.CSSProperties = {
  padding: "7px 14px",
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
};

const miniBtnStyle: React.CSSProperties = {
  padding: "5px 10px",
  borderRadius: "var(--dash-radius-sm)",
  border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(255,255,255,0.04)",
  color: "var(--dash-text)",
  cursor: "pointer",
  fontSize: 11,
  display: "flex",
  alignItems: "center",
  gap: 4,
  flexShrink: 0,
};

const muted: React.CSSProperties = {
  fontSize: 12,
  color: "var(--dash-text-muted)",
  margin: "4px 0 10px",
};

export default AssistantCenterPage;
