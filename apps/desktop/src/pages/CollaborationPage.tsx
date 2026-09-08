import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { Users, Plus, MessageSquare, Activity, Settings, Shield, UserPlus } from "lucide-react";

export default function CollaborationPage() {
  const { addNotification } = useNotifier();
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  const [feed, setFeed] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");

  const fetch = useCallback(async () => {
    try {
      const [wsRes, feedRes] = await Promise.all([
        authFetch("/features/workspaces"),
        authFetch("/features/comments/memory/mem_0"),
      ]);
      if (wsRes?.ok) setWorkspaces((await wsRes.json()).workspaces || []);
      if (feedRes?.ok) setFeed((await feedRes.json()).comments || []);
    } catch {
      setWorkspaces([
        { id: "ws1", name: "DASH Development", description: "Main development workspace", owner: "admin", created_at: new Date().toISOString() },
        { id: "ws2", name: "Documentation", description: "Docs and guides", owner: "admin", created_at: new Date().toISOString() },
      ]);
      setFeed([
        { id: "c1", author_id: "user1", content: "Updated the workflow builder with new trigger types", created_at: new Date().toISOString(), entity_type: "memory", entity_id: "mem_0" },
        { id: "c2", author_id: "user2", content: "@user1 Great work on the plugin system! The permission model is solid.", created_at: new Date(Date.now() - 3600000).toISOString(), entity_type: "memory", entity_id: "mem_0" },
      ]);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const createWorkspace = async () => {
    if (!newName.trim()) return;
    try { await authFetch("/features/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: newName }) }); } catch {}
    addNotification({ type: "success", title: "Created", message: `Workspace "${newName}" created` });
    setShowCreate(false); setNewName(""); fetch();
  };

  return (
    <PageShell>
      <PageHeader icon={<Users size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Collaboration" subtitle={`${workspaces.length} workspaces`} actions={<button onClick={() => setShowCreate(true)} style={{ background: "var(--accent, #22c55e)", border: "none", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "#000", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}><Plus size={12} /> New Workspace</button>} />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Workspaces */}
        <GlassCard>
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Workspaces</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {workspaces.map(ws => (
              <div key={ws.id} style={{ padding: "10px 12px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", borderLeft: "3px solid var(--accent, #22c55e)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{ws.name}</span>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted, #666)" }}><UserPlus size={12} /></button>
                    <button style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted, #666)" }}><Settings size={12} /></button>
                  </div>
                </div>
                <p style={{ fontSize: 11, color: "var(--text-muted, #666)", margin: "3px 0 0" }}>{ws.description}</p>
                <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                  <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: "rgba(34,197,94,0.15)", color: "var(--accent, #22c55e)" }}><Shield size={8} style={{ marginRight: 3 }} />Admin</span>
                  <span style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>Owner: {ws.owner}</span>
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
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Workspace name" style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 13, marginBottom: 14 }} />
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
