import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard, EmptyState } from "@/components/ultron";
import { Users, Plus, MessageSquare, Activity, Settings, Shield, UserPlus, RefreshCw, Trash2 } from "lucide-react";

export default function CollaborationPage() {
  const { addNotification } = useNotifier();
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  const [feed, setFeed] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const wsRes = await authFetch("/features/workspaces");
      if (wsRes?.ok) setWorkspaces((await wsRes.json()).workspaces || []);
      else setError("Collaboration service unavailable.");
    } catch {
      setError("Collaboration service unreachable — is the backend running?");
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const createWorkspace = async () => {
    if (!newName.trim()) return;
    try {
      const r = await authFetch("/features/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: newName.trim(), description: newDescription.trim() }) });
      if (r?.ok) addNotification({ type: "success", title: "Created", message: `Workspace "${newName.trim()}" created` });
      else addNotification({ type: "error", title: "Failed", message: "Could not create workspace" });
    } catch { addNotification({ type: "error", title: "Failed", message: "Backend unreachable" }); }
    setShowCreate(false); setNewName(""); setNewDescription(""); fetch();
  };

  const deleteWorkspace = async (wsId: string, name: string) => {
    try {
      const r = await authFetch(`/features/workspaces/${wsId}`, { method: "DELETE" });
      if (r?.ok) { addNotification({ type: "info", title: "Deleted", message: name }); fetch(); }
    } catch {}
  };

  return (
    <PageShell>
      <PageHeader icon={<Users size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Collaboration" subtitle={`${workspaces.length} workspaces`} actions={<div style={{ display: "flex", gap: 6 }}><button onClick={() => setShowCreate(true)} style={{ background: "var(--accent, #22c55e)", border: "none", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "#000", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}><Plus size={12} /> New Workspace</button><button onClick={fetch} className="dash-btn-ghost" title="Refresh" aria-label="Refresh workspaces"><RefreshCw size={14} className={loading ? "animate-rotate" : undefined} /></button></div>} />

      {error && (
        <div role="alert" style={{ padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, marginBottom: 14, fontSize: 12, color: "#ef4444" }}>
          {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Workspaces */}
        <GlassCard>
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Workspaces</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {loading ? (
              [1, 2].map(i => <div key={i} style={{ height: 64, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 6, opacity: 0.5 }} />)
            ) : workspaces.length === 0 ? (
              <EmptyState icon={<Users size={26} style={{ color: "var(--dash-text-muted)" }} />} title="No workspaces" description="Create your first workspace to collaborate." />
            ) : workspaces.map(ws => (
              <div key={ws.id} style={{ padding: "10px 12px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", borderLeft: "3px solid var(--accent, #22c55e)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{ws.name}</span>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button
                      onClick={() => addNotification({ type: "info", title: "Members", message: `${ws.members?.length ?? 0} member(s) — invite via API in this release` })}
                      title="Members"
                      aria-label={`Members of ${ws.name}`}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted, #666)" }}><UserPlus size={12} /></button>
                    <button
                      onClick={() => deleteWorkspace(ws.id, ws.name)}
                      title="Delete workspace"
                      aria-label={`Delete ${ws.name}`}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "#ef4444" }}><Trash2 size={12} /></button>
                  </div>
                </div>
                {ws.description && <p style={{ fontSize: 11, color: "var(--text-muted, #666)", margin: "3px 0 0" }}>{ws.description}</p>}
                <div style={{ display: "flex", gap: 6, marginTop: 6, alignItems: "center" }}>
                  <span style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>Owner: {String(ws.owner_id || ws.owner || "—").slice(0, 8)}</span>
                  <span style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>• {ws.members?.length ?? 0} member(s)</span>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Activity Feed */}
        <GlassCard style={{ overflow: "auto" }}>
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Activity Feed</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {feed.map(item => (
              <div key={item.id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <div style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--accent, #22c55e)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, color: "#000" }}>{item.author_id?.slice(-1)?.toUpperCase()}</div>
                  <span style={{ fontSize: 11, fontWeight: 500 }}>{item.author_id}</span>
                  <span style={{ fontSize: 10, color: "var(--text-muted, #666)", marginLeft: "auto" }}>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
                <p style={{ fontSize: 12, color: "var(--text-secondary, #aaa)", margin: 0, lineHeight: 1.5 }}>{item.content}</p>
              </div>
            ))}
            {feed.length === 0 && <p style={{ fontSize: 12, color: "var(--text-muted, #666)", textAlign: "center", padding: 20 }}>No activity yet</p>}
          </div>
        </GlassCard>
      </div>

      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
          <GlassCard style={{ maxWidth: 380, width: "100%" }}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15 }}>New Workspace</h3>
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Workspace name" aria-label="Workspace name" style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 13, marginBottom: 10 }} />
            <input value={newDescription} onChange={e => setNewDescription(e.target.value)} placeholder="Description (optional)" aria-label="Workspace description" style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 12, marginBottom: 14 }} />
            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
              <button onClick={() => setShowCreate(false)} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", color: "var(--text)", cursor: "pointer", fontSize: 12 }}>Cancel</button>
              <button onClick={createWorkspace} style={{ background: "var(--accent, #22c55e)", border: "none", borderRadius: 6, padding: "6px 12px", color: "#000", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>Create</button>
            </div>
          </GlassCard>
        </div>
      )}
    </PageShell>
  );
}
