import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import {
  Play, Plus, Copy, Clock, Webhook, ChevronDown, ChevronRight,
  CheckCircle, Settings, GitBranch, Zap, History, XCircle, Timer, Sparkles
} from "lucide-react";

interface WorkflowNode {
  id: string;
  type: "trigger" | "action" | "condition" | "delay";
  config: Record<string, string>;
  x: number;
  y: number;
}

interface WorkflowExecution {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: "running" | "completed" | "failed";
  started_at: string;
  completed_at: string | null;
  nodes_executed: string[];
  condition_results?: Record<string, boolean>;
  duration_ms: number;
  error: string | null;
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  category: string;
  nodes: WorkflowNode[];
  edges: { from: string; to: string; condition?: string }[];
  enabled: boolean;
  run_count: number;
  last_run: string | null;
  is_template: boolean;
}

const NODE_COLORS: Record<string, string> = {
  trigger: "#22c55e", action: "#3b82f6", condition: "#f59e0b", delay: "#8b5cf6",
};
const NODE_ICONS: Record<string, typeof Play> = { trigger: Zap, action: Play, condition: GitBranch, delay: Clock };

export default function WorkflowBuilderPage() {
  const { addNotification } = useNotifier();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [templates, setTemplates] = useState<Workflow[]>([]);
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ templates: true, custom: true });
  const [instantiating, setInstantiating] = useState<string | null>(null);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [wfRes, tplRes] = await Promise.all([
        authFetch("/enhanced/workflows"),
        authFetch("/enhanced/workflows/templates"),
      ]);
      if (wfRes?.ok) { const d = await wfRes.json(); setWorkflows(d.workflows || []); }
      if (tplRes?.ok) { const d = await tplRes.json(); setTemplates(d.templates || []); }
    } catch {
      setTemplates([
        { id: "daily_briefing", name: "Daily Morning Briefing", description: "Summarize goals and tasks", category: "productivity", nodes: [{ id: "n1", type: "trigger", config: { schedule: "0 8 * * *" }, x: 0, y: 0 }, { id: "n2", type: "action", config: { tool: "memory.search" }, x: 200, y: 0 }], edges: [{ from: "n1", to: "n2" }], enabled: true, run_count: 0, last_run: null, is_template: true },
        { id: "backup_memories", name: "Backup Memories", description: "Export memories daily", category: "data", nodes: [{ id: "n1", type: "trigger", config: { schedule: "0 2 * * *" }, x: 0, y: 0 }], edges: [], enabled: true, run_count: 0, last_run: null, is_template: true },
        { id: "code_review", name: "Code Review Assistant", description: "Review code changes", category: "development", nodes: [{ id: "n1", type: "trigger", config: { event: "file.changed" }, x: 0, y: 0 }], edges: [], enabled: true, run_count: 0, last_run: null, is_template: true },
        { id: "weekly_report", name: "Weekly Report", description: "Productivity summary every Friday", category: "analytics", nodes: [], edges: [], enabled: true, run_count: 0, last_run: null, is_template: true },
        { id: "smart_reminder", name: "Smart Reminder", description: "Context-aware reminders", category: "productivity", nodes: [], edges: [], enabled: true, run_count: 0, last_run: null, is_template: true },
        { id: "email_to_memory", name: "Email to Memory", description: "Save important emails", category: "communication", nodes: [], edges: [], enabled: true, run_count: 0, last_run: null, is_template: true },
      ]);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const loadHistory = useCallback(async (wfId: string) => {
    setHistoryLoading(true);
    try {
      const res = await authFetch(`/enhanced/workflows/${wfId}/executions?limit=20`);
      if (res?.ok) {
        const d = await res.json();
        setExecutions(d.executions || []);
      } else {
        setExecutions([]);
      }
    } catch {
      setExecutions([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const selectWorkflow = (wf: Workflow) => {
    setSelected(wf);
    if (showHistory) loadHistory(wf.id);
  };

  const executeWorkflow = async (id: string) => {
    try { await authFetch(`/enhanced/workflows/${id}/execute`, { method: "POST" }); } catch {}
    addNotification({ type: "success", title: "Workflow Executed", message: "Workflow ran successfully" });
    fetchData();
    if (selected?.id === id && showHistory) loadHistory(id);
  };

  const createWorkflow = async () => {
    if (!newName.trim()) return;
    try {
      await authFetch("/enhanced/workflows/create", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, description: newDesc, nodes: [], edges: [] }),
      });
    } catch {}
    addNotification({ type: "success", title: "Created", message: `Workflow "${newName}" created` });
    setShowCreate(false); setNewName(""); setNewDesc(""); fetchData();
  };

  const instantiateTemplate = async (t: Workflow) => {
    setInstantiating(t.id);
    try {
      const res = await authFetch(`/enhanced/workflows/templates/${t.id}/instantiate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
      });
      if (res?.ok) {
        const d = await res.json();
        if (d.ok && d.workflow) {
          addNotification({ type: "success", title: "Template Added", message: `"${d.workflow.name}" is ready to edit in My Workflows` });
          setSelected(d.workflow);
          await fetchData();
          return;
        }
      }
      addNotification({ type: "error", title: "Instantiation failed", message: "Could not create an editable copy of this template" });
    } catch {
      addNotification({ type: "error", title: "Instantiation failed", message: "Backend unreachable — template not copied" });
    } finally {
      setInstantiating(null);
    }
  };

  const renderNode = (node: WorkflowNode) => {
    const Icon = NODE_ICONS[node.type] || Play;
    const color = NODE_COLORS[node.type] || "#666";
    return (
      <div key={node.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: "var(--bg-secondary, #1a1a2e)", border: `1px solid ${color}33`, borderRadius: 6, minWidth: 160 }}>
        <div style={{ width: 32, height: 32, borderRadius: 6, background: `${color}20`, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon size={16} style={{ color }} />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, textTransform: "capitalize" }}>{node.type}</div>
          <div style={{ fontSize: 11, color: "var(--text-muted, #666)", fontFamily: "monospace" }}>{Object.values(node.config).join(" → ")}</div>
        </div>
      </div>
    );
  };

  return (
    <PageShell>
      <PageHeader icon={<GitBranch size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Workflow Builder" subtitle="Create automated workflows with triggers, conditions, and actions." />
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <button className="btn btn--primary" onClick={() => setShowCreate(true)} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Plus size={14} /> New Workflow
        </button>
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1, 2, 3].map((i) => <div key={i} style={{ height: 60, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 8, opacity: 0.5 }} />)}
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <GlassCard>
              <button onClick={() => setExpanded(p => ({ ...p, templates: !p.templates }))} style={{ width: "100%", padding: "12px 14px", background: "none", border: "none", display: "flex", alignItems: "center", gap: 8, cursor: "pointer", color: "var(--text)", fontWeight: 600, fontSize: 13 }}>
                {expanded.templates ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                Templates ({templates.length})
              </button>
              {expanded.templates && (
                <div style={{ padding: "0 14px 12px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {templates.map(t => (
                    <div
                      key={t.id}
                      role="button"
                      tabIndex={0}
                      aria-label={`Template: ${t.name}. ${t.description}. Press to select.`}
                      onClick={() => selectWorkflow(t)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectWorkflow(t); } }}
                      style={{ padding: "10px 12px", borderRadius: 8, border: `1px solid ${selected?.id === t.id ? "var(--accent, #22c55e)" : "var(--border, #333)"}`, background: selected?.id === t.id ? "rgba(34,197,94,0.1)" : "var(--bg-secondary, #1a1a2e)", cursor: "pointer", display: "flex", flexDirection: "column", gap: 6, minHeight: 92 }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
                        <span style={{ fontSize: 12, fontWeight: 600 }}>{t.name}</span>
                        <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(34,197,94,0.15)", color: "var(--accent, #22c55e)", whiteSpace: "nowrap" }}>{t.category}</span>
                      </div>
                      <p style={{ fontSize: 11, color: "var(--text-muted, #666)", margin: 0, flex: 1 }}>{t.description}</p>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>{t.nodes.length} node{t.nodes.length === 1 ? "" : "s"}</span>
                        <button
                          onClick={(e) => { e.stopPropagation(); instantiateTemplate(t); }}
                          disabled={instantiating !== null}
                          aria-label={`Use template ${t.name}: create an editable copy in My Workflows`}
                          title="Create an editable copy in My Workflows"
                          style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, padding: "4px 8px", borderRadius: 5, border: "none", cursor: instantiating ? "wait" : "pointer", background: "var(--accent, #22c55e)", color: "#0b0b10", opacity: instantiating && instantiating !== t.id ? 0.5 : 1, fontWeight: 600 }}
                        >
                          <Sparkles size={11} /> {instantiating === t.id ? "Adding…" : "Use"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>
            <GlassCard>
              <button onClick={() => setExpanded(p => ({ ...p, custom: !p.custom }))} style={{ width: "100%", padding: "12px 14px", background: "none", border: "none", display: "flex", alignItems: "center", gap: 8, cursor: "pointer", color: "var(--text)", fontWeight: 600, fontSize: 13 }}>
                {expanded.custom ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                My Workflows ({workflows.length})
              </button>
              {expanded.custom && (
                <div style={{ padding: "0 14px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
                  {workflows.length === 0 ? (
                    <p style={{ fontSize: 12, color: "var(--text-muted, #666)", textAlign: "center", padding: 16 }}>No workflows yet</p>
                  ) : workflows.map(w => (
                    <div key={w.id} onClick={() => selectWorkflow(w)} style={{ padding: "8px 10px", borderRadius: 6, border: `1px solid ${selected?.id === w.id ? "var(--accent, #22c55e)" : "var(--border, #333)"}`, cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div><span style={{ fontSize: 13, fontWeight: 500 }}>{w.name}</span><div style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>Ran {w.run_count}x</div></div>
                      <button onClick={(e) => { e.stopPropagation(); executeWorkflow(w.id); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--accent, #22c55e)" }}><Play size={14} /></button>
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>
          </div>

          <GlassCard>
            {selected ? (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                  <div><h3 style={{ margin: 0, fontSize: 16 }}>{selected.name}</h3><p style={{ fontSize: 12, color: "var(--text-muted, #666)", margin: "3px 0 0" }}>{selected.description}</p></div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {!selected.is_template && (
                      <>
                        <button className="btn btn--primary" onClick={() => executeWorkflow(selected.id)} style={{ fontSize: 12, padding: "6px 12px" }}><Play size={12} /> Run</button>
                        <button
                          onClick={() => { setShowHistory(v => !v); if (!showHistory) loadHistory(selected.id); }}
                          aria-expanded={showHistory}
                          aria-label="Toggle execution history"
                          title="Execution history"
                          style={{ background: showHistory ? "rgba(34,197,94,0.12)" : "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 10px", cursor: "pointer", color: showHistory ? "var(--accent, #22c55e)" : "var(--text)", display: "flex", alignItems: "center", gap: 4 }}
                        >
                          <History size={12} /> History
                        </button>
                      </>
                    )}
                    {selected.is_template && (
                      <button
                        className="btn btn--primary"
                        onClick={() => instantiateTemplate(selected)}
                        disabled={instantiating !== null}
                        style={{ fontSize: 12, padding: "6px 12px", display: "flex", alignItems: "center", gap: 4 }}
                      >
                        <Sparkles size={12} /> {instantiating === selected.id ? "Adding…" : "Use Template"}
                      </button>
                    )}
                    {!selected.is_template && <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 10px", cursor: "pointer", color: "var(--text)" }}><Copy size={12} /></button>}
                  </div>
                </div>
                {selected.nodes.length > 0 ? (
                  <div>
                    <div style={{ fontSize: 11, color: "var(--text-muted, #666)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.08em" }}>Flow ({selected.nodes.length} nodes)</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {selected.nodes.map((node, i) => (
                        <div key={node.id} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          {renderNode(node)}
                          {i < selected.nodes.length - 1 && <span style={{ color: "var(--text-muted, #666)" }}>→</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted, #666)" }}>
                    <Zap size={28} style={{ marginBottom: 10, opacity: 0.3 }} />
                    <p style={{ fontSize: 13 }}>No nodes. Add one to start building.</p>
                  </div>
                )}
                {showHistory && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 11, color: "var(--text-muted, #666)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Execution History
                    </div>
                    {historyLoading ? (
                      <div style={{ padding: 14, fontSize: 12, color: "var(--text-muted, #666)" }}>Loading history…</div>
                    ) : executions.length === 0 ? (
                      <div style={{ padding: 14, fontSize: 12, color: "var(--text-muted, #666)", textAlign: "center" }}>
                        No runs recorded yet. Click Run to execute this workflow.
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {executions.map(ex => (
                          <div key={ex.id} style={{ padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 500 }}>
                                {ex.status === "completed" ? (
                                  <CheckCircle size={13} style={{ color: "var(--accent, #22c55e)" }} />
                                ) : ex.status === "failed" ? (
                                  <XCircle size={13} style={{ color: "#ef4444" }} />
                                ) : (
                                  <Timer size={13} style={{ color: "#f59e0b" }} />
                                )}
                                <span style={{ textTransform: "capitalize", color: ex.status === "failed" ? "#ef4444" : "var(--text)" }}>{ex.status}</span>
                              </span>
                              <span style={{ fontSize: 11, color: "var(--text-muted, #666)", fontFamily: "monospace" }}>
                                {ex.duration_ms} ms
                              </span>
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 10, color: "var(--text-muted, #666)" }}>
                              <span>
                                {new Date(ex.started_at).toLocaleString()} · {ex.nodes_executed.length} node{ex.nodes_executed.length === 1 ? "" : "s"}
                              </span>
                              <span style={{ fontFamily: "monospace" }}>
                                {ex.nodes_executed.join(" → ") || "—"}
                              </span>
                            </div>
                            {ex.condition_results && Object.keys(ex.condition_results).length > 0 && (
                              <div style={{ display: "flex", gap: 4, marginTop: 4, flexWrap: "wrap" }}>
                                {Object.entries(ex.condition_results).map(([id, v]) => (
                                  <span
                                    key={id}
                                    title={`Condition ${id} evaluated to ${v ? "TRUE" : "FALSE"}`}
                                    style={{ fontSize: 10, padding: "1px 6px", borderRadius: 4, fontFamily: "monospace", background: v ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", color: v ? "var(--accent, #22c55e)" : "#ef4444" }}
                                  >
                                    {id}: {v ? "TRUE" : "FALSE"}
                                  </span>
                                ))}
                              </div>
                            )}
                            {ex.error && (
                              <div style={{ marginTop: 4, fontSize: 11, color: "#ef4444", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={ex.error}>
                                {ex.error}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                  {[{ l: "Status", v: selected.enabled ? "Active" : "Paused", c: selected.enabled ? "var(--accent, #22c55e)" : "#666" }, { l: "Runs", v: String(selected.run_count), c: "var(--text)" }, { l: "Category", v: selected.category, c: "var(--text-muted, #999)" }].map(s => (
                    <div key={s.l} style={{ padding: 8, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>{s.l}</div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: s.c }}>{s.v}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: 50, color: "var(--text-muted, #666)" }}>
                <GitBranch size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
                <p style={{ fontSize: 13 }}>Select a workflow to view details</p>
              </div>
            )}
          </GlassCard>
        </div>
      )}

      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
          <GlassCard style={{ maxWidth: 420, width: "100%" }}>
            <h3 style={{ margin: "0 0 14px", fontSize: 16 }}>New Workflow</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", fontSize: 12, marginBottom: 4, color: "var(--text-muted, #999)" }}>Name</label>
              <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="My Workflow" style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 13 }} />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 12, marginBottom: 4, color: "var(--text-muted, #999)" }}>Description</label>
              <textarea value={newDesc} onChange={e => setNewDesc(e.target.value)} rows={3} placeholder="What does this do?" style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 13, resize: "vertical" }} />
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => setShowCreate(false)} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "8px 14px", color: "var(--text)", cursor: "pointer", fontSize: 13 }}>Cancel</button>
              <button className="btn btn--primary" onClick={createWorkflow} style={{ fontSize: 13 }}>Create</button>
            </div>
          </GlassCard>
        </div>
      )}
    </PageShell>
  );
}
