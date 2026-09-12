import React, { useState, useEffect, useCallback, useMemo } from "react";
import { automation, workflows as workflowsApi, type Workflow, type WorkflowNode, type WorkflowEdge } from "@/lib/api";
import { WorkflowCanvas, NODE_META } from "@/components/WorkflowCanvas";
import {
  Zap, Plus, Trash2, RefreshCw, Clock, ToggleLeft, ToggleRight, GitBranch,
  Play, Workflow as WorkflowIcon, Save, Copy, Layers, CheckCircle,
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
  const [tab, setTab] = useState<"rules" | "builder">("rules");

  return (
    <PageShell glowColor="rgba(251, 191, 36, 0.05)">
      <PageHeader
        icon={<Zap size={22} color="var(--dash-warning)" />}
        iconColor="var(--dash-warning)"
        iconBg="rgba(251, 191, 36, 0.12)"
        title="Automation & Workflows"
        subtitle="Event rules and visual drag-and-drop workflow builder"
        actions={
          <TabBar
            tabs={[
              { id: "rules", label: "Rules", icon: <Clock size={12} /> },
              { id: "builder", label: "Workflow Builder", icon: <WorkflowIcon size={12} /> },
            ]}
            activeTab={tab}
            onTabChange={(id) => setTab(id as "rules" | "builder")}
          />
        }
      />

      <div className="dash-page-content">
        {tab === "rules" ? <RulesTab /> : <BuilderTab />}
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
