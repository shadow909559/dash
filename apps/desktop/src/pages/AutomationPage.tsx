import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  automation, workflows as workflowsApi, triggers as triggersApi, workflowWebhookUrl,
  type Workflow, type WorkflowNode, type WorkflowEdge,
  type WorkflowSchedule, type WorkflowWebhook, type WorkflowEventTrigger,
  type WorkflowExecutionSummary,
} from "@/lib/api";
import { getWsClient } from "@/lib/wsClient";
import { WorkflowCanvas, NODE_META } from "@/components/WorkflowCanvas";
import {
  Zap, Plus, Trash2, RefreshCw, Clock, ToggleLeft, ToggleRight, GitBranch,
  Play, Workflow as WorkflowIcon, Save, Copy, Layers, CheckCircle,
  Webhook, AlertCircle, Eye, EyeOff, CalendarClock, History, Pause,
} from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle, TabBar } from "@/components/ultron";

// ── Simple rule (existing backend) ──────────────────────────────────────────

interface Rule {
  id: string;
  name: string;
  trigger: string;
  action: string;
  enabled: boolean;
}

const WARNING_GLOW = "0 0 16px rgba(251,191,36,0.2)";

// ── Component ───────────────────────────────────────────────────────────────

export const AutomationPage: React.FC = () => {
  const [tab, setTab] = useState<"rules" | "builder" | "triggers">("rules");

  return (
    <PageShell glowColor="rgba(251, 191, 36, 0.05)">
      <PageHeader
        icon={<Zap size={22} color="var(--dash-warning)" />}
        iconColor="var(--dash-warning)"
        iconBg="rgba(251, 191, 36, 0.12)"
        title="Automation & Workflows"
        subtitle="Event rules, visual workflow builder, and schedule/webhook triggers"
        actions={
          <TabBar
            tabs={[
              { id: "rules", label: "Rules", icon: <Clock size={12} /> },
              { id: "builder", label: "Workflow Builder", icon: <WorkflowIcon size={12} /> },
              { id: "triggers", label: "Triggers", icon: <CalendarClock size={12} /> },
            ]}
            activeTab={tab}
            onTabChange={(id) => setTab(id as "rules" | "builder" | "triggers")}
          />
        }
      />

      <div className="dash-page-content">
        {tab === "rules" ? <RulesTab /> : tab === "builder" ? <BuilderTab /> : <TriggersTab />}
      </div>
    </PageShell>
  );
};

export default AutomationPage;

// ── Tab 1: Simple rules (unchanged behavior) ───────────────────────────────

const RulesTab: React.FC = () => {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("");
  const [action, setAction] = useState("");

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      setRules(await automation.getRules());
    } catch {}
    setLoading(false);
  }, []);

  const createRule = async () => {
    if (!name.trim()) return;
    try {
      await automation.createRule({ name, trigger, action, enabled: true });
      setName("");
      setTrigger("");
      setAction("");
      setShowCreate(false);
      fetchRules();
    } catch {}
  };

  const toggleRule = async (id: string, enabled: boolean) => {
    try {
      await automation.toggleRule(id, !enabled);
      fetchRules();
    } catch {}
  };

  const deleteRule = async (id: string) => {
    try {
      await automation.deleteRule(id);
      fetchRules();
    } catch {}
  };

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const enabledCount = rules.filter((r) => r.enabled).length;

  return (
    <>
      <SectionTitle
        count={rules.length}
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="dash-btn-primary"
              style={{ background: "var(--dash-warning)", boxShadow: WARNING_GLOW }}
            >
              <Plus size={14} /> New Rule
            </button>
            <button onClick={fetchRules} className="dash-btn-ghost" aria-label="Refresh rules">
              <RefreshCw size={14} />
            </button>
          </div>
        }
      >
        Active Rules — {enabledCount}/{rules.length} enabled
      </SectionTitle>

      {showCreate && (
        <GlassCard glow padding={18}>
          <SectionTitle>Create Automation Rule</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-label="Rule name"
              placeholder="Rule name"
              className="dash-input-ultron"
              style={{ width: "100%", boxSizing: "border-box" }}
            />
            <input
              value={trigger}
              onChange={(e) => setTrigger(e.target.value)}
              aria-label="Trigger"
              placeholder="Trigger (e.g. daily at 9am)"
              className="dash-input-ultron"
              style={{ width: "100%", boxSizing: "border-box" }}
            />
            <input
              value={action}
              onChange={(e) => setAction(e.target.value)}
              aria-label="Action"
              placeholder="Action (e.g. summarize tasks)"
              className="dash-input-ultron"
              style={{ width: "100%", boxSizing: "border-box" }}
            />
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => setShowCreate(false)} className="dash-btn-ghost">
                Cancel
              </button>
              <button onClick={createRule} className="dash-btn-primary" style={{ background: "var(--dash-warning)", boxShadow: WARNING_GLOW }}>
                <Zap size={12} /> Create Rule
              </button>
            </div>
          </div>
        </GlassCard>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 48, color: "var(--dash-text-muted)" }}>
          <RefreshCw size={18} className="animate-rotate" style={{ marginBottom: 10 }} />
          <div>Loading rules...</div>
        </div>
      ) : rules.length === 0 ? (
        <EmptyState
          icon={<Zap size={28} style={{ color: "var(--dash-warning)" }} />}
          title="No automation rules"
          description="Create rules to automate repetitive tasks, or switch to the Workflow Builder for visual if/else flows."
          action={
            <button
              onClick={() => setShowCreate(true)}
              className="dash-btn-primary"
              style={{ background: "var(--dash-warning)", boxShadow: WARNING_GLOW }}
            >
              <Plus size={14} /> Create Rule
            </button>
          }
        />
      ) : (
        <div className="dash-stagger">
          {rules.map((r) => (
            <GlassCard key={r.id} padding={0} className="dash-card-glow">
              <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 18px" }}>
                <button
                  onClick={() => toggleRule(r.id, r.enabled)}
                  aria-label={r.enabled ? `Disable ${r.name}` : `Enable ${r.name}`}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 0, color: r.enabled ? "var(--dash-warning)" : "var(--dash-text-muted)" }}
                >
                  {r.enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
                </button>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: r.enabled ? "var(--dash-text)" : "var(--dash-text-secondary)" }}>
                    {r.name}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--dash-text-muted)",
                      fontFamily: "'JetBrains Mono', monospace",
                      marginTop: 3,
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <span style={{ color: "var(--dash-warning)" }}>{r.trigger || "*"}</span>
                    <span style={{ opacity: 0.4 }}>{">"}</span>
                    <span>{r.action || "*"}</span>
                  </div>
                </div>
                <button onClick={() => deleteRule(r.id)} className="dash-btn-ghost" aria-label={`Delete ${r.name}`} style={{ padding: 6 }}>
                  <Trash2 size={13} />
                </button>
              </div>
            </GlassCard>
          ))}
        </div>
      )}
    </>
  );
};

// ── Tab 2: Visual workflow builder ──────────────────────────────────────────

const PALETTE: Array<{ type: WorkflowNode["type"]; hint: string }> = [
  { type: "trigger", hint: "Schedule or event that starts the flow" },
  { type: "action", hint: "Run a tool or step" },
  { type: "condition", hint: "Branch TRUE / FALSE paths" },
  { type: "delay", hint: "Wait before continuing" },
];

const BuilderTab: React.FC = () => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<WorkflowNode[]>([]);
  const [edges, setEdges] = useState<WorkflowEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [runResult, setRunResult] = useState<string | null>(null);

  const active = useMemo(() => workflows.find((w) => w.id === activeId) ?? null, [workflows, activeId]);
  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedNodeId) ?? null, [nodes, selectedNodeId]);
  const isCustom = !!active && !active.is_template;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [wfRes, tplRes] = await Promise.all([workflowsApi.list(), workflowsApi.listTemplates()]);
      const all = [...(wfRes.workflows || []), ...(tplRes.templates || [])];
      setWorkflows(all);
      setActiveId((prev) => prev ?? all[0]?.id ?? null);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Load canvas when switching workflows
  useEffect(() => {
    if (!active) return;
    setNodes(active.nodes.map((n) => ({ ...n, config: { ...n.config } })));
    setEdges(active.edges.map((e) => ({ ...e })));
    setSelectedNodeId(null);
    setDirty(false);
    setRunResult(null);
  }, [activeId]); // eslint-disable-line react-hooks/exhaustive-deps

  const mutate = (nextNodes: WorkflowNode[], nextEdges: WorkflowEdge[]) => {
    // Templates are read-only previews (enforced inside WorkflowCanvas via
    // editable={isCustom}); this guard is a second line of defense so no
    // canvas change can ever dirty/save a template.
    if (!isCustom) return;
    setNodes(nextNodes);
    setEdges(nextEdges);
    setDirty(true);
  };

  const createWorkflow = async () => {
    if (!newName.trim()) return;
    try {
      const res = await workflowsApi.create({ name: newName.trim(), nodes: [], edges: [] });
      setShowCreate(false);
      setNewName("");
      await fetchData();
      if (res.workflow?.id) setActiveId(res.workflow.id);
    } catch {}
  };

  const saveWorkflow = async () => {
    if (!active || !isCustom) return;
    setSaving(true);
    try {
      await workflowsApi.update(active.id, { nodes, edges });
      setWorkflows((prev) => prev.map((w) => (w.id === active.id ? { ...w, nodes, edges } : w)));
      setDirty(false);
      setRunResult("Saved");
    } catch {
      setRunResult("Save failed");
    }
    setSaving(false);
  };

  const runWorkflow = async () => {
    if (!active) return;
    setRunResult(null);
    try {
      const res = await workflowsApi.execute(active.id);
      if (res.execution) {
        // Surface branch outcomes so users see which path the if/else took.
        const conds = (res.execution as { condition_results?: Record<string, boolean> }).condition_results;
        const condText = conds && Object.keys(conds).length
          ? " · " + Object.entries(conds).map(([id, v]) => `${id}: ${v ? "TRUE" : "FALSE"}`).join(", ")
          : "";
        setRunResult(`Run ${res.execution.status} (${res.execution.duration_ms}ms, ${res.execution.nodes_executed.length} nodes)${condText}`);
      } else {
        setRunResult("Triggered");
      }
    } catch {
      setRunResult("Run failed");
    }
    fetchData();
  };

  const duplicateWorkflow = async () => {
    if (!active) return;
    try {
      const res = await workflowsApi.duplicate(active.id);
      await fetchData();
      if (res.workflow?.id) setActiveId(res.workflow.id);
    } catch {}
  };

  const deleteWorkflow = async () => {
    if (!active || !isCustom) return;
    try {
      await workflowsApi.delete(active.id);
      // Clear the canvas too — it kept rendering the deleted workflow's
      // nodes with a dead activeId (bug found in live preview).
      setActiveId(null);
      setNodes([]);
      setEdges([]);
      setSelectedNodeId(null);
      setDirty(false);
      setRunResult(null);
      fetchData();
    } catch {}
  };

  const updateNodeConfig = (key: string, value: string) => {
    if (!selectedNode) return;
    mutate(
      nodes.map((n) => (n.id === selectedNode.id ? { ...n, config: { ...n.config, [key]: value } } : n)),
      edges
    );
  };

  const configFields: Array<{ key: string; label: string }> = useMemo(() => {
    if (!selectedNode) return [];
    switch (selectedNode.type) {
      case "trigger":
        return [
          { key: "schedule", label: "Cron schedule" },
          { key: "event", label: "Event name" },
        ];
      case "condition":
        return [
          { key: "field", label: "Field" },
          { key: "op", label: "Operator (eq, gte, contains…)" },
          { key: "value", label: "Value" },
        ];
      case "delay":
        return [{ key: "seconds", label: "Seconds to wait" }];
      default:
        return [
          { key: "tool", label: "Tool (e.g. notification.send)" },
          { key: "title", label: "Title / message" },
        ];
    }
  }, [selectedNode]);

  const hasCycle = useMemo(() => {
    // Simple DFS cycle check so users see why a save might be odd
    const adj = new Map<string, string[]>();
    for (const e of edges) adj.set(e.from, [...(adj.get(e.from) ?? []), e.to]);
    const visiting = new Set<string>();
    const visited = new Set<string>();
    const dfs = (id: string): boolean => {
      if (visiting.has(id)) return true;
      if (visited.has(id)) return false;
      visiting.add(id);
      for (const nxt of adj.get(id) ?? []) if (dfs(nxt)) return true;
      visiting.delete(id);
      visited.add(id);
      return false;
    };
    return nodes.some((n) => dfs(n.id));
  }, [edges, nodes]);

  return (
    <>
      {/* Workflow selector + actions */}
      <GlassCard padding={12}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Layers size={16} color="var(--dash-warning)" />
          <select
            value={activeId ?? ""}
            onChange={(e) => setActiveId(e.target.value || null)}
            aria-label="Select workflow"
            className="dash-input-ultron"
            style={{ flex: "1 1 220px", maxWidth: 320 }}
          >
            <optgroup label="My workflows">
              {workflows.filter((w) => !w.is_template).map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </optgroup>
            <optgroup label="Templates (read-only)">
              {workflows.filter((w) => w.is_template).map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </optgroup>
          </select>

          <button onClick={() => setShowCreate(true)} className="dash-btn-primary" style={{ background: "var(--dash-warning)", boxShadow: WARNING_GLOW }}>
            <Plus size={13} /> New
          </button>
          <button onClick={runWorkflow} className="dash-btn-ghost" disabled={!active} aria-label="Run workflow">
            <Play size={13} /> Run
          </button>
          {isCustom ? (
            <button
              onClick={saveWorkflow}
              className="dash-btn-primary"
              disabled={saving || !dirty}
              style={{ background: dirty ? "var(--dash-accent)" : "var(--dash-surface-active)", boxShadow: dirty ? "0 0 16px rgba(63,169,245,0.25)" : "none" }}
            >
              <Save size={13} /> {saving ? "Saving…" : dirty ? "Save" : "Saved"}
            </button>
          ) : (
            <button onClick={duplicateWorkflow} className="dash-btn-ghost" disabled={!active}>
              <Copy size={13} /> Duplicate to edit
            </button>
          )}
          {isCustom && (
            <button onClick={deleteWorkflow} className="dash-btn-ghost" aria-label="Delete workflow" style={{ marginLeft: "auto" }}>
              <Trash2 size={13} color="var(--dash-danger)" />
            </button>
          )}
          {runResult && (
            <span
              role="status"
              style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: runResult.includes("fail") ? "var(--dash-danger)" : "var(--dash-success)" }}
            >
              <CheckCircle size={11} /> {runResult}
            </span>
          )}
        </div>
      </GlassCard>

      {/* Main builder area — responsive: 3 columns ≥900px, stacked below */}
      <div className="wf-builder-grid">
        {/* Palette */}
        <GlassCard padding={12}>
          <div className="dash-section-title" style={{ marginBottom: 10 }}>Node Palette</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {PALETTE.map(({ type, hint }) => {
              const meta = NODE_META[type];
              const { Icon } = meta;
              return (
                <div
                  key={type}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData("application/dash-node-type", type);
                    e.dataTransfer.effectAllowed = "copy";
                  }}
                  title={hint}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 9,
                    padding: "9px 10px",
                    borderRadius: "var(--dash-radius-sm)",
                    background: "var(--dash-elevated)",
                    border: `1px solid ${meta.color}44`,
                    cursor: "grab",
                    userSelect: "none",
                  }}
                >
                  <div style={{ width: 26, height: 26, borderRadius: 6, background: `${meta.color}20`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <Icon size={13} color={meta.color} />
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--dash-text)" }}>{meta.label}</div>
                </div>
              );
            })}
          </div>
          <p style={{ fontSize: 10.5, color: "var(--dash-text-muted)", marginTop: 12, lineHeight: 1.5 }}>
            Drag onto the canvas. Pull from a node's edge port to another's input port to wire the flow. If/Else nodes have green TRUE and red FALSE ports.
          </p>
        </GlassCard>

        {/* Canvas */}
        <div className="wf-builder-canvas-wrap" style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <WorkflowCanvas
            nodes={nodes}
            edges={edges}
            onChange={mutate}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            editable={isCustom}
          />
          {hasCycle && (
            <div role="alert" style={{ marginTop: 6, fontSize: 11.5, color: "var(--dash-warning)", fontFamily: "'JetBrains Mono', monospace" }}>
              ⚠ Loop detected in this flow — execution may never finish.
            </div>
          )}
        </div>

        {/* Config panel */}
        <GlassCard padding={12}>
          <div className="dash-section-title" style={{ marginBottom: 10 }}>Properties</div>
          {!selectedNode ? (
            <p style={{ fontSize: 12, color: "var(--dash-text-muted)", lineHeight: 1.6 }}>
              Select a node on the canvas to edit its configuration.
              <br />
              <br />
              • Drag node body to move (snaps to grid)
              <br />• Drag port → port to connect
              <br />• <kbd>Delete</kbd> removes the selected node
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {(() => {
                  const meta = NODE_META[selectedNode.type];
                  const { Icon } = meta;
                  return <Icon size={14} color={meta.color} />;
                })()}
                <span style={{ fontSize: 13, fontWeight: 600, textTransform: "capitalize", color: "var(--dash-text)" }}>
                  {NODE_META[selectedNode.type].label}
                </span>
                <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: "var(--dash-text-muted)" }}>{selectedNode.id}</span>
              </div>
              {configFields.map((f) => (
                <div key={f.key}>
                  <label style={{ display: "block", fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 4 }}>{f.label}</label>
                  <input
                    value={String(selectedNode.config[f.key] ?? "")}
                    onChange={(e) => updateNodeConfig(f.key, e.target.value)}
                    disabled={!isCustom}
                    title={isCustom ? undefined : "Templates are read-only — duplicate to edit"}
                    aria-label={f.label}
                    className="dash-input-ultron"
                    style={{ width: "100%", boxSizing: "border-box" }}
                  />
                </div>
              ))}
              {isCustom && (
                <button
                  onClick={() => {
                    const nextNodes = nodes.filter((n) => n.id !== selectedNode.id);
                    const nextEdges = edges.filter((ed) => ed.from !== selectedNode.id && ed.to !== selectedNode.id);
                    mutate(nextNodes, nextEdges);
                    setSelectedNodeId(null);
                  }}
                  className="dash-btn-ghost"
                  style={{ color: "var(--dash-danger)", justifyContent: "center" }}
                >
                  <Trash2 size={12} /> Delete node
                </button>
              )}
            </div>
          )}
        </GlassCard>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Create workflow"
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}
        >
          <GlassCard style={{ maxWidth: 420, width: "100%" }}>
            <h3 style={{ margin: "0 0 14px", fontSize: 16 }}>New Workflow</h3>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createWorkflow()}
              placeholder="Workflow name"
              aria-label="Workflow name"
              className="dash-input-ultron"
              style={{ width: "100%", boxSizing: "border-box", marginBottom: 14 }}
              // eslint-disable-next-line jsx-a11y/no-autofocus
              autoFocus
            />
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => setShowCreate(false)} className="dash-btn-ghost">Cancel</button>
              <button onClick={createWorkflow} className="dash-btn-primary" style={{ background: "var(--dash-warning)", boxShadow: WARNING_GLOW }}>
                <GitBranch size={12} /> Create
              </button>
            </div>
          </GlassCard>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: "center", padding: 20, color: "var(--dash-text-muted)" }}>
          <RefreshCw size={16} className="animate-rotate" style={{ marginBottom: 8 }} />
          <div style={{ fontSize: 12 }}>Loading workflows…</div>
        </div>
      )}
    </>
  );
};

// ── Tab 3: Triggers — schedules + webhooks (decisions.md #56) ────────────────

const CRON_PRESETS: Array<{ label: string; cron: string }> = [
  { label: "Every minute", cron: "* * * * *" },
  { label: "Every 15 min", cron: "*/15 * * * *" },
  { label: "Daily 08:00", cron: "0 8 * * *" },
  { label: "Daily 20:00", cron: "0 20 * * *" },
  { label: "Weekly Fri 18:00", cron: "0 18 * * 5" },
];

/** Client-side cron preview — mirrors the backend's honest rejection:
 * 5 fields, each "*", "* / N" step, a-b range, list, or value; numeric
 * bounds enforced. The BACKEND stays the source of truth; this only gives
 * instant feedback. */
function cronClientError(expr: string): string | null {
  const fields = expr.trim().split(/\s+/);
  if (fields.length !== 5) return `Expected 5 fields (minute hour day month weekday), got ${fields.length}`;
  const bounds: Array<[number, number, string]> = [
    [0, 59, "minute"], [0, 23, "hour"], [1, 31, "day"], [1, 12, "month"], [0, 6, "weekday"],
  ];
  for (let i = 0; i < 5; i++) {
    const [lo, hi, name] = bounds[i];
    for (const part of fields[i].split(",")) {
      const m = part.match(/^(\*|\d+)(?:-(\d+))?(?:\/(\d+))?$/);
      if (!m) return `${name}: unsupported token "${part}"`;
      const nums = [m[1], m[2]].filter(Boolean).map(Number);
      for (const n of nums) if (n < lo || n > hi) return `${name}: ${n} out of range (${lo}-${hi})`;
      if (m[3] && Number(m[3]) < 1) return `${name}: step must be ≥ 1`;
    }
  }
  return null;
}

function describeCron(expr: string): string {
  const f = expr.trim().split(/\s+/);
  if (f.length !== 5) return "";
  if (f.every((x) => x === "*")) return "every minute";
  if (f[0].startsWith("*/")) return `every ${f[0].slice(2)} minutes`;
  if (f.slice(1).every((x) => x === "*")) return `at minute ${f[0]} of every hour`;
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const dow = f[4] === "*" ? "" : days[Number(f[4])] ? `${days[Number(f[4])]}s ` : "";
  if (f[2] === "*" && f[3] === "*" && f[0] !== "*" && f[1] !== "*") {
    return `${dow ? `on ${dow}` : "daily"} at ${f[1].padStart(2, "0")}:${f[0].padStart(2, "0")}`;
  }
  return "custom schedule";
}

function formatWhen(iso: string | null): string {
  if (!iso) return "never";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

/** Compact recency for the recent-fires pills: "now", "2m ago", "3h ago",
 * falling back to the medium date once it's over a day old. */
function formatAgo(iso: string): string {
  try {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 10) return "now";
    if (s < 60) return `${Math.floor(s)}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return formatWhen(iso);
  } catch {
    return iso;
  }
}

/** Human duration: 0.4ms reads "0.4ms", 1250ms reads "1.3s". */
function formatDuration(ms: number): string {
  if (!Number.isFinite(ms)) return "?";
  if (ms < 1000) return `${Math.round(ms * 10) / 10}ms`;
  if (ms < 60000) return `${Math.round(ms / 100) / 10}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

const STATUS_COLOR: Record<string, string> = {
  completed: "var(--dash-success)",
  failed: "var(--dash-danger)",
  running: "var(--dash-accent)",
};

/** History filter options (#82) — "all" plus every source the engine records. */
const SOURCES = ["all", "scheduled", "webhook", "manual", "event"] as const;

const TriggersTab: React.FC = () => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [schedules, setSchedules] = useState<Record<string, WorkflowSchedule>>({});
  const [webhooks, setWebhooks] = useState<Record<string, WorkflowWebhook>>({});
  const [eventTriggers, setEventTriggers] = useState<Record<string, WorkflowEventTrigger>>({});
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null); // workflow id being edited
  const [cronDraft, setCronDraft] = useState("");
  const [savingCron, setSavingCron] = useState(false);
  const [cronMsg, setCronMsg] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState<string | null>(null);
  const [execs, setExecs] = useState<Record<string, WorkflowExecutionSummary[]>>({});
  const [openExec, setOpenExec] = useState<string | null>(null);
  // History source filter (#82): client-side slice of the already-fetched
  // runs — survives the live poll refresh, resets when another panel opens.
  const [historyFilter, setHistoryFilter] = useState<"all" | "scheduled" | "webhook" | "manual" | "event">("all");
  // Inline failed-run error detail (#82): run id whose error is expanded.
  const [expandedError, setExpandedError] = useState<string | null>(null);
  // Mirror for fetchLive (stable closure): the open panel re-fetches on
  // every poll tick, so an open History keeps up with new fires.
  const openExecRef = React.useRef<string | null>(null);
  const [execLoading, setExecLoading] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<{ key: string; msg: string } | null>(null);
  // Live updates (#76): silent poll keeps trigger_count / last-fired fresh
  // without the Refresh button. `liveState` is the honest indicator:
  // "live" while polls succeed, "stale" once one fails, "initial" before
  // the first successful poll.
  const liveGenerationRef = React.useRef(0);
  const [liveState, setLiveState] = useState<"initial" | "live" | "stale">("initial");
  // Recent fires per workflow (decisions.md #77): the newest executions
  // across all workflows, refreshed by the same live poll. Only rows with
  // actual runs show the line — an empty map entry renders nothing.
  const [recentFires, setRecentFires] = useState<Record<string, WorkflowExecutionSummary[]>>({});
  // Run-now (decisions.md #78): per-row state so two rows can run at once
  // without clobbering each other, and the inline result stays until the
  // next run of that row (or another action on it) replaces it.
  const [runState, setRunState] = useState<
    Record<string, { phase: "running" | "done"; msg: React.ReactNode; ok: boolean }>
  >({});

  // Runs shown in the open History panel: the source-filter slice (#82).
  // Filtering the already-fetched array keeps the live poll feed intact —
  // new runs still arrive while a filter is active, and just appear (or
  // don't) according to the selected source.
  const rawExecs = openExec ? execs[openExec] ?? [] : [];
  const filteredExecs =
    historyFilter === "all" ? rawExecs : rawExecs.filter((e) => e.source === historyFilter);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [wfRes, schedRes, hookRes, evRes] = await Promise.all([
        workflowsApi.list(),
        triggersApi.listSchedules(),
        triggersApi.listWebhooks(),
        triggersApi.listEventTriggers(),
      ]);
      setWorkflows(wfRes.workflows);
      setSchedules(schedRes.schedules);
      setWebhooks(hookRes.webhooks);
      setEventTriggers(evRes.triggers);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const fetchLive = useCallback(async () => {
    // Silent refresh: no loading spinner, counters and last-fired simply
    // become current. A stale response (one overtaken by a newer poll or
    // by a user edit) is dropped, not applied.
    const gen = ++liveGenerationRef.current;
    try {
      const [schedRes, hookRes, evRes, execRes] = await Promise.all([
        triggersApi.listSchedules(),
        triggersApi.listWebhooks(),
        triggersApi.listEventTriggers(),
        triggersApi.getAllExecutions(60),
      ]);
      if (liveGenerationRef.current !== gen) return; // overtaken
      setSchedules(schedRes.schedules);
      setWebhooks(hookRes.webhooks);
      setEventTriggers(evRes.triggers);
      // Group newest-first executions by workflow for the per-row line.
      const byWf: Record<string, WorkflowExecutionSummary[]> = {};
      for (const e of execRes.executions) {
        (byWf[e.workflow_id] ??= []).push(e);
      }
      setRecentFires(byWf);
      setLiveState("live");
      // An open History panel keeps itself current (decisions.md #77).
      const open = openExecRef.current;
      if (open) {
        try {
          const res = await triggersApi.getExecutions(open, 20);
          if (liveGenerationRef.current !== gen) return;
          setExecs((prev) => ({ ...prev, [open]: res.executions }));
        } catch {
          /* keep the last good list */
        }
      }
    } catch {
      if (liveGenerationRef.current !== gen) return;
      setLiveState("stale"); // keep showing the last good data
    }
  }, []);

  useEffect(() => {
    // Poll only while the tab is VISIBLE — a hidden window stops the
    // churn and catches up the moment it's seen again (the visibility
    // listener fires the same tick immediately). Since #80 this is a
    // RECONCILIATION fallback: the ws push loop below delivers fires and
    // pause changes the moment they happen; the poll self-heals anything
    // a push missed (reconnect, crash) and carries recentFires.
    const tick = () => {
      if (!document.hidden) void fetchLive();
    };
    tick();
    const interval = setInterval(tick, 5000);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [fetchLive]);

  // Server push (decisions.md #80): the backend sends trigger.update over
  // the EXISTING /ws connection the moment a trigger fires or is
  // paused/resumed. Each message carries the engine's own snapshot for
  // that workflow; merge it into the row state through the same
  // generation guard as polls (a push is always fresher than an in-flight
  // poll response, so bump the generation on arrival). Records the client
  // has not loaded yet are skipped — the 5 s poll establishes them.
  useEffect(() => {
    const ws = getWsClient();
    const onTriggerUpdate = (data: Record<string, unknown>) => {
      const trig = data.trigger as
        | {
            workflow_id?: string;
            schedule?: Partial<WorkflowSchedule>;
            webhook?: Partial<WorkflowWebhook>;
            event?: Partial<WorkflowEventTrigger>;
          }
        | undefined;
      const wfId = trig?.workflow_id;
      if (!wfId) return;
      liveGenerationRef.current++; // push wins over any in-flight poll
      if (trig.schedule) {
        setSchedules((prev) =>
          prev[wfId] ? { ...prev, [wfId]: { ...prev[wfId], ...trig.schedule! } } : prev
        );
      }
      if (trig.webhook) {
        setWebhooks((prev) =>
          prev[wfId] ? { ...prev, [wfId]: { ...prev[wfId], ...trig.webhook! } } : prev
        );
      }
      if (trig.event) {
        setEventTriggers((prev) =>
          prev[wfId] ? { ...prev, [wfId]: { ...prev[wfId], ...trig.event! } } : prev
        );
      }
    };
    ws.on("trigger.update", onTriggerUpdate);
    return () => ws.off("trigger.update", onTriggerUpdate);
  }, []);

  const openEditor = (wfId: string) => {
    setExpanded(wfId);
    setCronDraft(schedules[wfId]?.cron ?? "");
    setCronMsg(null);
  };

  const draftError = useMemo(() => cronClientError(cronDraft), [cronDraft]);

  // After a successful mutation, invalidate any in-flight silent poll so
  // its (older) response can't overwrite the just-saved state, then pull
  // fresh data as the live loop does — silent, spinner-free.
  const applyAfterMutation = useCallback(() => {
    liveGenerationRef.current++; // drop any in-flight poll response
    void fetchData();
  }, [fetchData]);

  const saveCron = async (wfId: string) => {
    if (draftError || !cronDraft.trim()) return;
    setSavingCron(true);
    try {
      const res = await triggersApi.setSchedule(wfId, cronDraft.trim());
      if (res.ok) {
        setCronMsg(null);
        setExpanded(null);
        applyAfterMutation();
      } else {
        // Backend is the source of truth — show ITS reason verbatim.
        setCronMsg(res.reason || "rejected by backend");
      }
    } catch {
      setCronMsg("could not reach the backend");
    }
    setSavingCron(false);
  };

  const removeSchedule = async (wfId: string) => {
    try {
      await triggersApi.removeSchedule(wfId);
      if (expanded === wfId) setExpanded(null);
      applyAfterMutation();
    } catch {}
  };

  const createWebhook = async (wfId: string) => {
    try {
      await triggersApi.createWebhook(wfId);
      applyAfterMutation();
    } catch {}
  };

  const removeWebhook = async (wfId: string) => {
    try {
      await triggersApi.removeWebhook(wfId);
      applyAfterMutation();
    } catch {}
  };

  const setSchedulePaused = async (wfId: string, enabled: boolean) => {
    setTriggerMsg(null);
    try {
      const res = await triggersApi.setScheduleEnabled(wfId, enabled);
      if (!res.ok) setTriggerMsg({ key: wfId, msg: res.reason || "could not change the schedule" });
      applyAfterMutation();
    } catch {
      setTriggerMsg({ key: wfId, msg: "could not reach the backend" });
    }
  };

  // Pause/resume a webhook (decisions.md #79). Same honest semantics as
  // the schedule toggle: the backend's reason is surfaced verbatim on a
  // refusal; config (secret, URL, count) is never touched.
  const setWebhookPaused = async (wfId: string, enabled: boolean) => {
    setTriggerMsg(null);
    try {
      const res = await triggersApi.setWebhookEnabled(wfId, enabled);
      if (!res.ok) setTriggerMsg({ key: wfId, msg: res.reason || "could not change the webhook" });
      applyAfterMutation();
    } catch {
      setTriggerMsg({ key: wfId, msg: "could not reach the backend" });
    }
  };

  // Pause/resume an event trigger (decisions.md #79). Paused = fire_event
  // skips it entirely: no run, no count bump, no last-fired update.
  const setEventPaused = async (wfId: string, enabled: boolean) => {
    setTriggerMsg(null);
    try {
      const res = await triggersApi.setEventTriggerEnabled(wfId, enabled);
      if (!res.ok) setTriggerMsg({ key: wfId, msg: res.reason || "could not change the event trigger" });
      applyAfterMutation();
    } catch {
      setTriggerMsg({ key: wfId, msg: "could not reach the backend" });
    }
  };

  // Run this workflow's flow right now (decisions.md #78). Honest result:
  // the backend's own execution record — status, duration, branch
  // outcomes, error — surfaced verbatim, not a generic "done".
  const runNow = async (wfId: string) => {
    setRunState((prev) => ({ ...prev, [wfId]: { phase: "running", msg: "Running…", ok: true } }));
    try {
      const res = await workflowsApi.execute(wfId);
      const ex = res.execution as
        | (WorkflowExecutionSummary & {
            condition_results?: Record<string, boolean>;
            error?: string | null;
            workflow_name?: string;
          })
        | undefined;
      let msg: React.ReactNode;
      let ok = true;
      if (!res.ok) {
        // Backend refused (disabled workflow, etc.) — its reason, verbatim.
        msg = res.reason || "run refused";
        ok = false;
      } else if (ex) {
        const conds = ex.condition_results;
        const condText =
          conds && Object.keys(conds).length
            ? " · " +
              Object.entries(conds)
                .map(([id, v]) => `${id}: ${v ? "TRUE" : "FALSE"}`)
                .join(", ")
            : "";
        ok = ex.status === "completed";
        msg = (
          <>
            {ex.status} · {formatDuration(ex.duration_ms)} · {ex.nodes_executed.length} node
            {ex.nodes_executed.length === 1 ? "" : "s"}
            {condText}
            {ex.error ? ` · ${ex.error}` : ""}
          </>
        );
      } else {
        msg = "triggered";
      }
      setRunState((prev) => ({ ...prev, [wfId]: { phase: "done", msg, ok } }));
    } catch {
      setRunState((prev) => ({ ...prev, [wfId]: { phase: "done", msg: "could not reach the backend", ok: false } }));
    }
    // Refresh triggers + history: the manual run just became an execution
    // (source=manual) and must show up in Recent fires / open History.
    applyAfterMutation();
  };

  const toggleHistory = async (wfId: string) => {
    if (openExec === wfId) {
      openExecRef.current = null;
      setOpenExec(null);
      setExpandedError(null);
      return;
    }
    openExecRef.current = wfId;
    setOpenExec(wfId);
    setHistoryFilter("all"); // a freshly opened panel starts unfiltered
    setExpandedError(null);
    setExecLoading(true);
    try {
      const res = await triggersApi.getExecutions(wfId, 20);
      setExecs((prev) => ({ ...prev, [wfId]: res.executions }));
    } catch {
      setExecs((prev) => ({ ...prev, [wfId]: [] }));
    }
    setExecLoading(false);
  };

  const copyText = async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied((c) => (c === key ? null : c)), 1500);
    } catch {}
  };

  const toggleReveal = (key: string) => {
    setRevealed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const customWorkflows = workflows.filter((w) => !w.is_template);

  const rows = customWorkflows.map((wf) => ({
    wf,
    schedule: schedules[wf.id],
    webhook: webhooks[wf.id],
    eventTrigger: eventTriggers[wf.id],
  }));

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 48, color: "var(--dash-text-muted)" }}>
        <RefreshCw size={18} className="animate-rotate" style={{ marginBottom: 10 }} />
        <div>Loading triggers…</div>
      </div>
    );
  }

  return (
    <>
      <SectionTitle
        count={rows.filter((r) => r.schedule || r.webhook).length}
        action={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {/* Live indicator (decisions.md #76): honest about its state —
                green pulse while polling succeeds, amber when the last
                poll failed (data may be old), nothing before the first
                successful poll. Hidden-tab polls resume on refocus. */}
            {liveState !== "initial" && (
              <span
                title={
                  liveState === "live"
                    ? "Live: refreshing every 5 s while this tab is visible"
                    : "Last refresh failed — the numbers below may be outdated; retrying every 5 s"
                }
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 10,
                  fontFamily: "'JetBrains Mono', monospace",
                  color: liveState === "live" ? "var(--dash-success)" : "var(--dash-warning, #f59e0b)",
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: liveState === "live" ? "var(--dash-success)" : "var(--dash-warning, #f59e0b)",
                    ...(liveState === "live"
                      ? { animation: "jarvis-pulse 2s ease-in-out infinite" }
                      : {}),
                  }}
                />
                {liveState === "live" ? "LIVE" : "STALE"}
              </span>
              )}
            <button onClick={fetchData} className="dash-btn-ghost" aria-label="Refresh triggers">
              <RefreshCw size={14} />
            </button>
          </div>
        }
      >
        Triggers — schedules fire on time, webhooks fire on call
      </SectionTitle>

      {rows.length === 0 ? (
        <EmptyState
          icon={<CalendarClock size={28} style={{ color: "var(--dash-warning)" }} />}
          title="No workflows yet"
          description="Create a workflow in the Builder tab, then attach a cron schedule or a webhook trigger here."
        />
      ) : (
        <div className="dash-stagger">
          {rows.map(({ wf, schedule, webhook, eventTrigger }) => {
            const isExpanded = expanded === wf.id;
            return (
              <GlassCard key={wf.id} padding={0} className="dash-card-glow">
                <div style={{ padding: "14px 18px", display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                    <div style={{ flex: "1 1 200px", minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{wf.name}</div>
                      {!schedule && !webhook && !eventTrigger && (
                        <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 2 }}>
                          No triggers attached
                        </div>
                      )}
                      {schedule && (
                        <div
                          style={{
                            fontSize: 11,
                            fontFamily: "'JetBrains Mono', monospace",
                            color: schedule.enabled === false ? "var(--dash-text-muted)" : "var(--dash-warning)",
                            marginTop: 3,
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <Clock size={11} />
                          <span>{schedule.cron}</span>
                          <span style={{ color: "var(--dash-text-muted)", fontFamily: "inherit" }}>
                            ({describeCron(schedule.cron)})
                          </span>
                          {schedule.enabled === false && (
                            <span
                              style={{
                                fontSize: 9,
                                padding: "1px 6px",
                                borderRadius: 8,
                                background: "var(--dash-surface-active)",
                                color: "var(--dash-text-muted)",
                                fontFamily: "inherit",
                              }}
                              title={schedule.paused_since ? `Paused since ${formatWhen(schedule.paused_since)}` : undefined}
                            >
                              paused{schedule.paused_since ? ` · ${formatAgo(schedule.paused_since)}` : ""}
                            </span>
                          )}
                        </div>
                      )}
                      {schedule && (
                        <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 2, display: "flex", gap: 10, flexWrap: "wrap" }}>
                          <span>
                            Last fired: {""}
                            <span
                              style={{
                                color:
                                  schedule.last_status === "completed"
                                    ? "var(--dash-success)"
                                    : schedule.last_status === "failed"
                                      ? "var(--dash-danger)"
                                      : "var(--dash-text-muted)",
                              }}
                            >
                              {formatWhen(schedule.last_fired_at)}
                              {schedule.last_status ? ` · ${schedule.last_status}` : ""}
                            </span>
                          </span>
                          {schedule.enabled === false && schedule.paused_since && (
                            <span title={`Fires whose cron matched but did not run because of the pause`}>
                              paused {formatAgo(schedule.paused_since)} ·{" "}
                              <span style={{ color: "var(--dash-warning)" }}>
                                {schedule.skipped_fires ?? 0} skipped
                              </span>
                            </span>
                          )}
                        </div>
                      )}
                      {webhook && (
                        <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 2, display: "flex", alignItems: "center", gap: 5 }}>
                          <Webhook size={11} /> {webhook.trigger_count} call{webhook.trigger_count === 1 ? "" : "s"}
                          {webhook.enabled === false && (
                            <span
                              style={{
                                fontSize: 9,
                                padding: "1px 6px",
                                borderRadius: 8,
                                background: "var(--dash-surface-active)",
                                color: "var(--dash-text-muted)",
                              }}
                            >
                              paused
                            </span>
                          )}
                        </div>
                      )}
                      {eventTrigger && (
                        <div style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: eventTrigger.enabled === false ? "var(--dash-text-muted)" : "var(--dash-success)", marginTop: 2, display: "flex", alignItems: "center", gap: 5 }}>
                          <Zap size={11} />
                          <span>on {eventTrigger.event}</span>
                          {Object.keys(eventTrigger.match ?? {}).length > 0 && (
                            <span style={{ color: "var(--dash-text-muted)" }}>
                              ({Object.entries(eventTrigger.match).map(([k, v]) => `${k}=${String(v)}`).join(", ")})
                            </span>
                          )}
                          <span style={{ color: "var(--dash-text-muted)", fontFamily: "inherit" }}>
                            · {eventTrigger.trigger_count} fire{eventTrigger.trigger_count === 1 ? "" : "s"}
                          </span>
                          {eventTrigger.enabled === false && (
                            <span
                              style={{
                                fontSize: 9,
                                padding: "1px 6px",
                                borderRadius: 8,
                                background: "var(--dash-surface-active)",
                                color: "var(--dash-text-muted)",
                                fontFamily: "inherit",
                              }}
                            >
                              paused
                            </span>
                          )}
                        </div>
                      )}
                      {runState[wf.id] && (
                        <div
                          role={runState[wf.id].phase === "running" ? "status" : runState[wf.id].ok ? "status" : "alert"}
                          aria-live="polite"
                          style={{
                            fontSize: 11,
                            marginTop: 2,
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                            color:
                              runState[wf.id].phase === "running"
                                ? "var(--dash-text-muted)"
                                : runState[wf.id].ok
                                  ? "var(--dash-success)"
                                  : "var(--dash-danger)",
                          }}
                        >
                          {runState[wf.id].phase === "running" ? (
                            <RefreshCw size={11} className="animate-rotate" />
                          ) : runState[wf.id].ok ? (
                            <CheckCircle size={11} />
                          ) : (
                            <AlertCircle size={11} />
                          )}
                          <span>{runState[wf.id].msg}</span>
                        </div>
                      )}
                    </div>

                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <button
                        onClick={() => (isExpanded ? setExpanded(null) : openEditor(wf.id))}
                        className="dash-btn-ghost"
                        aria-expanded={isExpanded}
                        aria-label={`Edit triggers for ${wf.name}`}
                      >
                        <CalendarClock size={12} /> {schedule ? "Edit schedule" : "Add schedule"}
                      </button>
                      {schedule && (
                        <button
                          onClick={() => void runNow(wf.id)}
                          className="dash-btn-ghost"
                          disabled={runState[wf.id]?.phase === "running"}
                          aria-label={`Run ${wf.name} now`}
                          title="Run this workflow immediately (manual run)"
                        >
                          <Play size={12} /> {runState[wf.id]?.phase === "running" ? "Running…" : "Run now"}
                        </button>
                      )}
                      {schedule && (
                        <button
                          onClick={() => setSchedulePaused(wf.id, schedule.enabled === false)}
                          className="dash-btn-ghost"
                          aria-label={
                            schedule.enabled === false
                              ? `Resume schedule for ${wf.name}`
                              : `Pause schedule for ${wf.name}`
                          }
                          aria-pressed={schedule.enabled === false}
                          title={schedule.enabled === false ? "Resume schedule" : "Pause schedule"}
                        >
                          {schedule.enabled === false ? <Play size={12} /> : <Pause size={12} />}
                          {schedule.enabled === false ? "Resume" : "Pause"}
                        </button>
                      )}
                      {eventTrigger && (
                        <button
                          onClick={() => setEventPaused(wf.id, eventTrigger.enabled === false)}
                          className="dash-btn-ghost"
                          aria-label={
                            eventTrigger.enabled === false
                              ? `Resume event trigger for ${wf.name}`
                              : `Pause event trigger for ${wf.name}`
                          }
                          aria-pressed={eventTrigger.enabled === false}
                          title={eventTrigger.enabled === false ? "Resume event trigger" : "Pause event trigger"}
                        >
                          {eventTrigger.enabled === false ? <Play size={12} /> : <Pause size={12} />}
                          {eventTrigger.enabled === false ? "Resume" : "Pause"}
                        </button>
                      )}
                      {!webhook ? (
                        <button onClick={() => createWebhook(wf.id)} className="dash-btn-ghost" aria-label={`Create webhook for ${wf.name}`}>
                          <Webhook size={12} /> Add webhook
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => setWebhookPaused(wf.id, webhook.enabled === false)}
                            className="dash-btn-ghost"
                            aria-label={
                              webhook.enabled === false
                                ? `Resume webhook for ${wf.name}`
                                : `Pause webhook for ${wf.name}`
                            }
                            aria-pressed={webhook.enabled === false}
                            title={webhook.enabled === false ? "Resume webhook" : "Pause webhook"}
                          >
                            {webhook.enabled === false ? <Play size={12} /> : <Pause size={12} />}
                            {webhook.enabled === false ? "Resume" : "Pause"}
                          </button>
                          <button
                            onClick={() => removeWebhook(wf.id)}
                            className="dash-btn-ghost"
                            aria-label={`Delete webhook for ${wf.name}`}
                            title="Delete webhook trigger"
                          >
                            <Trash2 size={12} color="var(--dash-danger)" />
                          </button>
                        </>
                      )}
                      {schedule && !isExpanded && (
                        <button
                          onClick={() => removeSchedule(wf.id)}
                          className="dash-btn-ghost"
                          aria-label={`Delete schedule for ${wf.name}`}
                          title="Delete schedule"
                        >
                          <Trash2 size={12} color="var(--dash-danger)" />
                        </button>
                      )}
                      <button
                        onClick={() => toggleHistory(wf.id)}
                        className="dash-btn-ghost"
                        aria-expanded={openExec === wf.id}
                        aria-label={`Execution history for ${wf.name}`}
                        title="Recent runs"
                      >
                        <History size={12} /> History
                      </button>
                    </div>
                  </div>

                  {/* Recent fires at a glance (decisions.md #77): the newest
                      runs of this workflow, refreshed live by the poll.
                      Only shown when the workflow has actually run. */}
                  {(recentFires[wf.id]?.length ?? 0) > 0 && !isExpanded && openExec !== wf.id && (
                    <div
                      style={{
                        borderTop: "1px solid var(--dash-border)",
                        paddingTop: 8,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        flexWrap: "wrap",
                        fontSize: 10,
                      }}
                    >
                      <span style={{ color: "var(--dash-text-muted)", fontWeight: 600 }}>
                        Recent fires
                      </span>
                      {recentFires[wf.id]!.slice(0, 4).map((e) => (
                        <span
                          key={e.id}
                          title={`${e.status} · via ${e.source} · ${formatDuration(e.duration_ms)} · ${formatWhen(e.started_at)}`}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "2px 7px",
                            borderRadius: "var(--dash-radius-full, 999px)",
                            background: "var(--dash-bg-subtle)",
                            fontFamily: "'JetBrains Mono', monospace",
                          }}
                        >
                          <span
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: "50%",
                              background: STATUS_COLOR[e.status] ?? "var(--dash-text-muted)",
                            }}
                          />
                          <span style={{ color: STATUS_COLOR[e.status] ?? "var(--dash-text-muted)" }}>
                            {e.source}
                          </span>
                          <span style={{ color: "var(--dash-text-muted)" }}>{formatAgo(e.started_at)}</span>
                        </span>
                      ))}
                      {(recentFires[wf.id]?.length ?? 0) > 4 && (
                        <button
                          onClick={() => void toggleHistory(wf.id)}
                          className="dash-btn-ghost"
                          style={{ fontSize: 10, padding: "2px 8px" }}
                        >
                          +{(recentFires[wf.id]?.length ?? 0) - 4} more
                        </button>
                      )}
                    </div>
                  )}

                  {isExpanded && (
                    <div
                      style={{
                        borderTop: "1px solid var(--dash-border)",
                        paddingTop: 10,
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                      }}
                    >
                      <input
                        value={cronDraft}
                        onChange={(e) => {
                          setCronDraft(e.target.value);
                          setCronMsg(null);
                        }}
                        onKeyDown={(e) => e.key === "Enter" && !draftError && saveCron(wf.id)}
                        placeholder="0 8 * * *"
                        aria-label="Cron expression"
                        className="dash-input-ultron"
                        style={{
                          width: "100%",
                          boxSizing: "border-box",
                          fontFamily: "'JetBrains Mono', monospace",
                          borderColor: cronDraft && draftError ? "var(--dash-danger)" : undefined,
                        }}
                      />
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {CRON_PRESETS.map((p) => (
                          <button
                            key={p.cron}
                            onClick={() => {
                              setCronDraft(p.cron);
                              setCronMsg(null);
                            }}
                            className="dash-btn-ghost"
                            style={{ fontSize: 10, padding: "4px 8px" }}
                          >
                            {p.label}
                          </button>
                        ))}
                      </div>
                      {cronDraft && (
                        <div
                          role={draftError ? "alert" : "status"}
                          style={{
                            fontSize: 11,
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                            color: draftError ? "var(--dash-danger)" : "var(--dash-text-secondary)",
                          }}
                        >
                          {draftError ? <AlertCircle size={11} /> : <CheckCircle size={11} />}
                          {draftError ? draftError : `Valid cron — ${describeCron(cronDraft)}`}
                        </div>
                      )}
                      {cronMsg && (
                        <div role="alert" style={{ fontSize: 11, color: "var(--dash-danger)", display: "flex", alignItems: "center", gap: 5 }}>
                          <AlertCircle size={11} /> {cronMsg}
                        </div>
                      )}
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                        <button onClick={() => setExpanded(null)} className="dash-btn-ghost">Cancel</button>
                        <button
                          onClick={() => saveCron(wf.id)}
                          className="dash-btn-primary"
                          disabled={savingCron || !!draftError || !cronDraft.trim()}
                          style={{
                            background: draftError || !cronDraft.trim() ? "var(--dash-surface-active)" : "var(--dash-warning)",
                            boxShadow: draftError || !cronDraft.trim() ? "none" : WARNING_GLOW,
                          }}
                        >
                          <Save size={12} /> {savingCron ? "Saving…" : "Save schedule"}
                        </button>
                      </div>
                    </div>
                  )}

                  {triggerMsg?.key === wf.id && (
                    <div role="alert" style={{ fontSize: 11, color: "var(--dash-danger)", display: "flex", alignItems: "center", gap: 5 }}>
                      <AlertCircle size={11} /> {triggerMsg.msg}
                    </div>
                  )}

                  {openExec === wf.id && (
                    <div
                      style={{
                        borderTop: "1px solid var(--dash-border)",
                        paddingTop: 10,
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--dash-text-secondary)" }}>
                          Recent runs{execs[wf.id] ? ` (${execs[wf.id].length})` : ""}
                        </div>
                        {(execs[wf.id]?.length ?? 0) > 0 && (
                          <div style={{ display: "flex", gap: 4, marginLeft: "auto", flexWrap: "wrap" }}>
                            {(SOURCES.map((s) => (
                              <button
                                key={s}
                                onClick={() => setHistoryFilter(s)}
                                className="dash-btn-ghost"
                                style={{
                                  fontSize: 10,
                                  padding: "2px 8px",
                                  fontFamily: "'JetBrains Mono', monospace",
                                  color: historyFilter === s ? "var(--dash-text)" : "var(--dash-text-muted)",
                                  background:
                                    historyFilter === s
                                      ? "rgba(255,255,255,0.08)"
                                      : "transparent",
                                  borderColor:
                                    historyFilter === s
                                      ? "var(--dash-accent)"
                                      : "var(--dash-border)",
                                }}
                              >
                                {s}
                              </button>
                            )))}
                          </div>
                        )}
                      </div>
                      {execLoading ? (
                        <div style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>Loading…</div>
                      ) : (execs[wf.id]?.length ?? 0) === 0 ? (
                        <div style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>
                          No runs recorded for this workflow yet — fire the schedule or webhook to see history here.
                        </div>
                      ) : filteredExecs.length === 0 ? (
                        <div style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>
                          No {historyFilter === "all" ? "" : historyFilter + " "}runs recorded{historyFilter !== "all" ? " for this filter" : " yet"}.
                        </div>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          {filteredExecs.slice(0, 10).map((e) => (
                            <div
                              key={e.id}
                              style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 10, flexWrap: "wrap" }}
                            >
                              <span
                                style={{
                                  color:
                                    e.status === "completed"
                                      ? "var(--dash-success)"
                                      : e.status === "failed"
                                        ? "var(--dash-danger)"
                                        : "var(--dash-text-muted)",
                                }}
                              >
                                {e.status}
                              </span>
                              <span style={{ color: "var(--dash-text-muted)" }}>
                                {formatWhen(e.started_at)} · via {e.source} ·{" "}
                                {formatDuration(e.duration_ms)} · {e.nodes_executed.length} nodes
                              </span>
                              {e.error && (
                                <span
                                  onClick={() =>
                                    setExpandedError((prev) => (prev === e.id ? null : e.id))
                                  }
                                  style={{
                                    color: "var(--dash-danger)",
                                    cursor: "pointer",
                                    fontFamily: "'JetBrains Mono', monospace",
                                    fontSize: 9,
                                    border: "1px solid var(--dash-danger)",
                                    borderRadius: 4,
                                    padding: "1px 6px",
                                    userSelect: "none",
                                  }}
                                  title="Show full error"
                                >
                                  error
                                </span>
                              )}
                            </div>
                          ))}
                          {expandedError && (
                            <div
                              style={{
                                fontSize: 10,
                                fontFamily: "'JetBrains Mono', monospace",
                                color: "var(--dash-danger)",
                                background: "rgba(63,169,245,0.08)",
                                border: "1px solid var(--dash-border)",
                                borderRadius: "var(--dash-radius-sm)",
                                padding: "8px 10px",
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                              }}
                            >
                              {rawExecs.find((x) => x.id === expandedError)?.error}
                            </div>
                          )}
                          {filteredExecs.length > 10 && (
                            <div style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>
                              …and {filteredExecs.length - 10} more earlier runs
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {webhook && (
                    <div
                      style={{
                        borderTop: "1px solid var(--dash-border)",
                        paddingTop: 10,
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                        <code
                          style={{
                            flex: "1 1 260px",
                            fontSize: 10,
                            fontFamily: "'JetBrains Mono', monospace",
                            background: "var(--dash-surface-active)",
                            padding: "6px 8px",
                            borderRadius: 6,
                            overflowWrap: "anywhere",
                            userSelect: "all",
                          }}
                        >
                          {workflowWebhookUrl(webhook.webhook_id)}
                        </code>
                        <button
                          onClick={() => copyText(workflowWebhookUrl(webhook.webhook_id), `url-${wf.id}`)}
                          className="dash-btn-ghost"
                          aria-label="Copy webhook URL"
                        >
                          {copied === `url-${wf.id}` ? <CheckCircle size={12} color="var(--dash-success)" /> : <Copy size={12} />}
                          {copied === `url-${wf.id}` ? "Copied" : "Copy URL"}
                        </button>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                        <code
                          style={{
                            flex: "1 1 260px",
                            fontSize: 10,
                            fontFamily: "'JetBrains Mono', monospace",
                            background: "var(--dash-surface-active)",
                            padding: "6px 8px",
                            borderRadius: 6,
                            overflowWrap: "anywhere",
                            userSelect: "all",
                          }}
                        >
                          {revealed.has(`sec-${wf.id}`) ? webhook.secret : "•".repeat(Math.min(32, Math.max(8, webhook.secret.length)))}
                        </code>
                        <button
                          onClick={() => toggleReveal(`sec-${wf.id}`)}
                          className="dash-btn-ghost"
                          aria-label={revealed.has(`sec-${wf.id}`) ? "Hide webhook secret" : "Reveal webhook secret"}
                        >
                          {revealed.has(`sec-${wf.id}`) ? <EyeOff size={12} /> : <Eye size={12} />}
                          {revealed.has(`sec-${wf.id}`) ? "Hide" : "Reveal"}
                        </button>
                        <button
                          onClick={() => copyText(webhook.secret, `sec-${wf.id}`)}
                          className="dash-btn-ghost"
                          aria-label="Copy webhook secret"
                        >
                          {copied === `sec-${wf.id}` ? <CheckCircle size={12} color="var(--dash-success)" /> : <Copy size={12} />}
                          {copied === `sec-${wf.id}` ? "Copied" : "Copy"}
                        </button>
                      </div>
                      <div style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>
                        Call this URL with header <code>X-Webhook-Secret</code> (or <code>?secret=</code>) to run the workflow.
                      </div>
                    </div>
                  )}
                </div>
              </GlassCard>
            );
          })}
        </div>
      )}
    </>
  );
};
