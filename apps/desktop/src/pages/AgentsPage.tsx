import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import {
  Bot, RefreshCw, Cpu, Activity, Zap, ListTodo, Pause, Play, X, Check,
  ShieldAlert, Circle, CircleDot, CheckCircle2, XCircle, SkipForward,
} from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle, StatusIndicator } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Agent {
  id: string;
  name: string;
  status: string;
  task?: string;
  model?: string;
}

interface TaskStepUI {
  id: string;
  description: string;
  tool: string | null;
  status: string;
  risk: string;
  attempts: number;
  verification: { status: string; detail?: string };
}

interface OrchestratorTask {
  id: string;
  goal: string;
  status: string;
  steps: TaskStepUI[];
  progress: { completed: number; total: number };
  pending_confirmation: {
    step_id: string;
    description: string;
    tool?: string;
    risk?: string;
  } | null;
  final_report?: {
    failed_steps?: { step: string; error: string }[];
    not_executed_steps?: string[];
    skipped_steps?: string[];
  } | null;
}

const TASK_STATUS_MAP: Record<string, "online" | "offline" | "warning" | "processing"> = {
  completed: "online",
  failed: "offline",
  cancelled: "offline",
  paused: "warning",
  waiting_confirmation: "warning",
  running: "processing",
  verifying: "processing",
  planning: "processing",
  pending: "warning",
};

function StepIcon({ status }: { status: string }) {
  const size = 13;
  switch (status) {
    case "completed":
      return <CheckCircle2 size={size} style={{ color: "var(--dash-success)" }} />;
    case "failed":
      return <XCircle size={size} style={{ color: "var(--dash-danger, #ef4444)" }} />;
    case "skipped":
      return <SkipForward size={size} style={{ color: "var(--dash-text-muted)" }} />;
    case "running":
    case "awaiting_confirmation":
      return <CircleDot size={size} style={{ color: "var(--dash-warning)" }} />;
    default:
      return <Circle size={size} style={{ color: "var(--dash-text-muted)" }} />;
  }
}

export const AgentsPage: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  // ── Orchestrated tasks (decisions.md #90) ─────────────────────────
  const [tasks, setTasks] = useState<OrchestratorTask[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [busyTask, setBusyTask] = useState<string | null>(null);
  const [newGoal, setNewGoal] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      const r = await authFetch(`${API}/agent/tasks`);
      if (r.ok) {
        const data = await r.json();
        setTasks(data.tasks || []);
      }
    } catch {}
    setTasksLoading(false);
  }, []);

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
    fetchTasks();
    // Live-ish updates: poll every 3 s. The backend ALSO pushes task.* events
    // over the main /ws socket; polling is the reconciliation fallback so the
    // panel can never show state a refresh would contradict.
    const iv = setInterval(fetchTasks, 3000);
    return () => clearInterval(iv);
  }, [fetchAgents, fetchTasks]);

  const taskAction = async (taskId: string, action: string, body?: object) => {
    setBusyTask(taskId);
    try {
      await authFetch(`${API}/agent/task/${taskId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      await fetchTasks();
    } catch {}
    setBusyTask(null);
  };

  const createTask = async () => {
    const goal = newGoal.trim();
    if (!goal) return;
    setCreating(true);
    setCreateError(null);
    try {
      const r = await authFetch(`${API}/agent/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        setCreateError(err.detail || `Rejected (${r.status})`);
      } else {
        setNewGoal("");
        await fetchTasks();
      }
    } catch (e: any) {
      setCreateError(e?.message || "Failed to create task");
    }
    setCreating(false);
  };

  const activeCount = agents.filter((a) => a.status === "running").length;
  const completedCount = agents.filter((a) => a.status === "completed").length;
  const openTasks = tasks.filter((t) =>
    !["completed", "failed", "cancelled"].includes(t.status)
  );

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
            {openTasks.length} task{openTasks.length === 1 ? "" : "s"} open
          </span>
        }
        actions={
          <button
            onClick={() => {
              fetchAgents();
              fetchTasks();
            }}
            className="dash-btn-ghost"
          >
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Summary cards */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          {[
            { label: "Total Agents", value: agents.length, icon: Bot, color: "var(--dash-success)" },
            { label: "Running", value: activeCount, icon: Zap, color: "var(--dash-warning)" },
            { label: "Completed", value: completedCount, icon: Cpu, color: "var(--dash-accent)" },
          ].map((stat) => {
            const Icon = stat.icon;
            return (
              <GlassCard key={stat.label} padding={14}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
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

        {/* ── Orchestrated tasks ─────────────────────────────────── */}
        <div className="dash-stagger" style={{ marginTop: 8 }}>
          <SectionTitle count={tasks.length}>Complex Tasks</SectionTitle>

          {/* Create a task */}
          <GlassCard padding={14}>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                value={newGoal}
                onChange={(e) => setNewGoal(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createTask()}
                placeholder='Give DASH a complex goal, e.g. "Organize my downloads folder by file type"'
                style={{
                  flex: 1,
                  background: "rgba(0,0,0,0.25)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "var(--dash-radius-sm)",
                  padding: "8px 12px",
                  fontSize: 12,
                  color: "var(--dash-text)",
                  outline: "none",
                }}
              />
              <button
                onClick={createTask}
                disabled={creating || !newGoal.trim()}
                className="dash-btn-ghost"
                style={{ opacity: creating || !newGoal.trim() ? 0.5 : 1 }}
              >
                <Zap size={13} /> {creating ? "Planning..." : "Run task"}
              </button>
            </div>
            {createError && (
              <div style={{ marginTop: 8, fontSize: 11, color: "var(--dash-danger, #ef4444)" }}>
                {createError}
              </div>
            )}
          </GlassCard>

          {tasksLoading ? (
            <div style={{ textAlign: "center", padding: 32, color: "var(--dash-text-muted)" }}>
              <RefreshCw size={16} className="animate-rotate" style={{ marginBottom: 8 }} />
              <div>Loading tasks...</div>
            </div>
          ) : tasks.length === 0 ? (
            <EmptyState
              icon={<ListTodo size={28} style={{ color: "var(--dash-success)" }} />}
              title="No complex tasks yet"
              description="Give DASH a multi-step goal above or in chat — he plans it, executes safe steps, and asks before anything risky."
            />
          ) : (
            tasks.map((t) => {
              const pct = t.progress.total > 0
                ? Math.round((t.progress.completed / t.progress.total) * 100)
                : 0;
              return (
                <GlassCard key={t.id} padding={0} className="dash-card-glow">
                  <div style={{ padding: "14px 18px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div
                        style={{
                          width: 34, height: 34, borderRadius: "var(--dash-radius-sm)",
                          background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.2)",
                          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                        }}
                      >
                        <ListTodo size={15} style={{ color: "var(--dash-success)" }} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)", marginBottom: 2 }}>
                          {t.goal}
                        </div>
                        <div
                          style={{
                            fontSize: 10, color: "var(--dash-text-muted)",
                            fontFamily: "'JetBrains Mono', monospace",
                          }}
                        >
                          task {t.id} · {t.progress.completed}/{t.progress.total} steps · {pct}%
                        </div>
                      </div>
                      <StatusIndicator status={TASK_STATUS_MAP[t.status] || "offline"} label={t.status.replace("_", " ")} />
                      <div style={{ display: "flex", gap: 4 }}>
                        {t.status === "paused" ? (
                          <button className="dash-btn-ghost" title="Resume"
                            disabled={busyTask === t.id}
                            onClick={() => taskAction(t.id, "resume")}>
                            <Play size={13} />
                          </button>
                        ) : (
                          ["running", "waiting_confirmation", "planning", "verifying"].includes(t.status) && (
                            <button className="dash-btn-ghost" title="Pause"
                              disabled={busyTask === t.id}
                              onClick={() => taskAction(t.id, "pause")}>
                              <Pause size={13} />
                            </button>
                          )
                        )}
                        {!["completed", "failed", "cancelled"].includes(t.status) && (
                          <button className="dash-btn-ghost" title="Cancel"
                            disabled={busyTask === t.id}
                            onClick={() => taskAction(t.id, "cancel")}>
                            <X size={13} />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Progress bar */}
                    <div
                      style={{
                        height: 4, marginTop: 12, borderRadius: 2,
                        background: "rgba(255,255,255,0.06)", overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%", width: `${pct}%`, borderRadius: 2,
                          background: "var(--dash-success)", transition: "width 0.4s ease",
                        }}
                      />
                    </div>

                    {/* Confirmation request — from REAL task state only */}
                    {t.status === "waiting_confirmation" && t.pending_confirmation && (
                      <div
                        style={{
                          marginTop: 12, padding: "10px 12px", borderRadius: "var(--dash-radius-sm)",
                          background: "rgba(250, 204, 21, 0.08)", border: "1px solid rgba(250, 204, 21, 0.3)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                          <ShieldAlert size={13} style={{ color: "var(--dash-warning)" }} />
                          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--dash-warning)", letterSpacing: "0.04em" }}>
                            ACTION REQUIRES APPROVAL
                          </span>
                        </div>
                        <div style={{ fontSize: 12, color: "var(--dash-text)", marginBottom: 3 }}>
                          {t.pending_confirmation.description}
                        </div>
                        <div style={{ fontSize: 10, color: "var(--dash-text-muted)", fontFamily: "'JetBrains Mono', monospace", marginBottom: 10 }}>
                          tool: {t.pending_confirmation.tool || "auto-select"} · risk: {t.pending_confirmation.risk || "high"}
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                          <button
                            className="dash-btn-ghost"
                            disabled={busyTask === t.id}
                            onClick={() => taskAction(t.id, "approve", { approved: true })}
                            style={{ color: "var(--dash-success)", borderColor: "rgba(34,197,94,0.4)" }}
                          >
                            <Check size={12} /> Approve
                          </button>
                          <button
                            className="dash-btn-ghost"
                            disabled={busyTask === t.id}
                            onClick={() => taskAction(t.id, "approve", { approved: false })}
                            style={{ color: "var(--dash-danger, #ef4444)", borderColor: "rgba(239,68,68,0.4)" }}
                          >
                            <X size={12} /> Reject
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Step checklist — every status from actual task state */}
                    <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
                      {t.steps.map((s) => (
                        <div key={s.id} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                          <div style={{ marginTop: 1, flexShrink: 0 }}>
                            <StepIcon status={s.status} />
                          </div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 12, color: "var(--dash-text)" }}>
                              {s.description}
                              {s.risk === "high" && (
                                <span
                                  style={{
                                    marginLeft: 6, fontSize: 9, padding: "1px 5px", borderRadius: 3,
                                    background: "rgba(239,68,68,0.12)", color: "var(--dash-danger, #ef4444)",
                                    border: "1px solid rgba(239,68,68,0.3)",
                                  }}
                                >
                                  HIGH RISK
                                </span>
                              )}
                              {s.attempts > 1 && (
                                <span style={{ marginLeft: 6, fontSize: 10, color: "var(--dash-text-muted)" }}>
                                  (attempt {s.attempts})
                                </span>
                              )}
                            </div>
                            {s.verification?.status && s.verification.status !== "not_run" && (
                              <div
                                style={{
                                  fontSize: 10, color: "var(--dash-text-muted)",
                                  fontFamily: "'JetBrains Mono', monospace", marginTop: 1,
                                }}
                              >
                                {s.verification.status === "verified" ? "✓ verified" : s.verification.status.replace("_", " ")}
                                {s.verification.detail ? ` — ${s.verification.detail}` : ""}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Honest failure summary */}
                    {t.status === "failed" && t.final_report && (
                      <div
                        style={{
                          marginTop: 10, padding: "8px 12px", borderRadius: "var(--dash-radius-sm)",
                          background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.25)",
                          fontSize: 11, color: "var(--dash-text-muted)",
                        }}
                      >
                        {(t.final_report.failed_steps || []).map((f, i) => (
                          <div key={i}>✗ {f.step}{f.error ? ` — ${f.error}` : ""}</div>
                        ))}
                        {(t.final_report.skipped_steps || []).map((s, i) => (
                          <div key={`s${i}`}>– skipped: {s}</div>
                        ))}
                        {(t.final_report.not_executed_steps || []).map((s, i) => (
                          <div key={`n${i}`}>○ never ran: {s}</div>
                        ))}
                      </div>
                    )}
                  </div>
                </GlassCard>
              );
            })
          )}
        </div>

        {/* ── Agent pool (existing) ───────────────────────────────── */}
        {loading ? (
          <div style={{ textAlign: "center", padding: 48, color: "var(--dash-text-muted)" }}>
            <RefreshCw size={18} className="animate-rotate" style={{ marginBottom: 10 }} />
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
              const statusMap: Record<string, "online" | "offline" | "warning" | "processing"> = {
                completed: "online",
                failed: "offline",
                running: "processing",
                pending: "warning",
              };
              return (
                <GlassCard key={a.id} padding={0} className="dash-card-glow">
                  <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 18px" }}>
                    <div
                      style={{
                        width: 36, height: 36, borderRadius: "var(--dash-radius-sm)",
                        background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.2)",
                        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                      }}
                    >
                      <Bot size={16} style={{ color: "var(--dash-success)" }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)", marginBottom: 3 }}>
                        {a.name}
                      </div>
                      {a.task && (
                        <div style={{ fontSize: 11, color: "var(--dash-text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                          {a.task}
                        </div>
                      )}
                    </div>
                    <StatusIndicator status={statusMap[a.status] || "offline"} label={a.status} />
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
