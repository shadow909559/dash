import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { Database, Clock, Archive, Trash2, RotateCcw, Layers } from "lucide-react";

export default function DataManagementPage() {
  const { addNotification } = useNotifier();
  const [policies, setPolicies] = useState<Record<string, any>>({});
  const [archives, setArchives] = useState<any[]>([]);
  const [deleted, setDeleted] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const [pRes, aRes, dRes] = await Promise.all([
        authFetch("/phase3/retention/policies"),
        authFetch("/phase3/archives"),
        authFetch("/phase3/soft-delete"),
      ]);
      if (pRes?.ok) setPolicies(await pRes.json());
      if (aRes?.ok) setArchives((await aRes.json()).archives || []);
      if (dRes?.ok) setDeleted((await dRes.json()).deleted || []);
    } catch {
      setPolicies({
        memories: { retention_days: 365, auto_delete: false, archive_before_delete: true },
        conversations: { retention_days: 90, auto_delete: false, archive_before_delete: true },
        notifications: { retention_days: 30, auto_delete: true, archive_before_delete: false },
        audit_logs: { retention_days: 365, auto_delete: false, archive_before_delete: true },
        error_logs: { retention_days: 14, auto_delete: true, archive_before_delete: false },
      });
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return (
    <PageShell>
      <PageHeader icon={<Database size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Data Management" subtitle="Retention, versioning, archiving, and soft delete" />

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{[1, 2, 3].map(i => <div key={i} style={{ height: 80, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 8, opacity: 0.5 }} />)}</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Retention Policies */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 6 }}><Clock size={14} /> Retention Policies</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {Object.entries(policies).map(([type, pol]: [string, any]) => (
                <div key={type} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 12, fontWeight: 500, textTransform: "capitalize" }}>{type.replace(/_/g, " ")}</span>
                    <span style={{ fontSize: 11, color: "var(--text-muted, #666)" }}>{pol.retention_days}d</span>
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                    <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: pol.auto_delete ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)", color: pol.auto_delete ? "#ef4444" : "var(--accent, #22c55e)" }}>{pol.auto_delete ? "AUTO-DELETE" : "MANUAL"}</span>
                    {pol.archive_before_delete && <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: "rgba(59,130,246,0.15)", color: "#3b82f6" }}>ARCHIVE</span>}
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* Archives */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 6 }}><Archive size={14} /> Archives ({archives.length})</h4>
            {archives.length === 0 ? (
              <div style={{ textAlign: "center", padding: 20, color: "var(--text-muted, #666)" }}>
                <Archive size={24} style={{ marginBottom: 8, opacity: 0.3 }} />
                <p style={{ fontSize: 12 }}>No archives yet</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {archives.map(a => (
                  <div key={a.id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span style={{ fontSize: 12, fontWeight: 500, textTransform: "capitalize" }}>{a.data_type}</span>
                      <div style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>{a.count} items • {a.reason}</div>
                    </div>
                    <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 4, padding: "3px 8px", cursor: "pointer", color: "var(--text-muted, #666)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}><RotateCcw size={10} /> Restore</button>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          {/* Soft Deleted */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 6 }}><Trash2 size={14} /> Soft Deleted ({deleted.length})</h4>
            {deleted.length === 0 ? (
              <div style={{ textAlign: "center", padding: 20, color: "var(--text-muted, #666)" }}>
                <p style={{ fontSize: 12 }}>No deleted items</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {deleted.slice(0, 10).map((d, i) => (
                  <div key={i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span style={{ fontSize: 12 }}>{d.entity_type}: {d.entity_id}</span>
                      <div style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>Deleted by {d.deleted_by}</div>
                    </div>
                    <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 4, padding: "3px 8px", cursor: "pointer", color: "var(--accent, #22c55e)", fontSize: 10 }}>Recover</button>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          {/* Data Overview */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 6 }}><Layers size={14} /> Data Overview</h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[{ l: "Policies", v: String(Object.keys(policies).length) }, { l: "Archives", v: String(archives.length) }, { l: "Deleted", v: String(deleted.length) }, { l: "Auto-delete", v: String(Object.values(policies).filter((p: any) => p.auto_delete).length) }].map(s => (
                <div key={s.l} style={{ padding: 8, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 4, textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>{s.l}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "monospace" }}>{s.v}</div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      )}
    </PageShell>
  );
}
