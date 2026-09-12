import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { PageShell, PageHeader, GlassCard, SectionTitle } from "@/components/ultron";
import { Inbox, Layers3, History, Bell, Scale, ShieldCheck, RefreshCw, Loader2, Mail } from "lucide-react";

interface Digest {
  id: string;
  title?: string;
  summary?: string;
  item_count?: number;
  created_at?: string;
}
interface BatchJob {
  id: string;
  name?: string;
  status?: string;
  total?: number;
  completed?: number;
  created_at?: string;
}
interface BulkOp {
  id: string;
  operation?: string;
  entity_type?: string;
  status?: string;
  affected?: number;
  created_at?: string;
}
interface RouterRule {
  id?: string;
  name?: string;
  channel?: string;
  priority?: string;
  enabled?: boolean;
}
interface Backend {
  id?: string;
  name?: string;
  healthy?: boolean;
  weight?: number;
  requests?: number;
}
interface IpList {
  id?: string;
  name?: string;
  ips?: string[];
  mode?: string;
}

export default function Phase3OpsPage() {
  const [digests, setDigests] = useState<Digest[]>([]);
  const [jobs, setJobs] = useState<BatchJob[]>([]);
  const [ops, setOps] = useState<BulkOp[]>([]);
  const [rules, setRules] = useState<RouterRule[]>([]);
  const [backends, setBackends] = useState<Backend[]>([]);
  const [ipLists, setIpLists] = useState<IpList[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const safe = async <T,>(url: string, pick: (j: any) => T[], fallback: T[]): Promise<T[]> => {
      try {
        const r = await authFetch(url);
        if (r?.ok) return pick(await r.json());
      } catch { /* fall through */ }
      return fallback;
    };
    const [d, j, o, ru, lb, ip] = await Promise.all([
      safe("/phase3/digest/history", (x) => x.digests ?? [], []),
      safe("/phase3/batch/jobs", (x) => x.jobs ?? [], []),
      safe("/phase3/bulk/operations", (x) => x.operations ?? [], []),
      safe("/phase3/notifications/router/rules", (x) => x.rules ?? [], []),
      safe("/phase3/load-balancer/backends", (x) => x.backends ?? [], []),
      safe("/phase3/ip-allowlist", (x) => x.allowlist ?? x.blocklist ?? x.lists ?? [], []),
    ]);
    setDigests(d); setJobs(j); setOps(o); setRules(ru); setBackends(lb); setIpLists(ip);
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const fmtTime = (t?: string) => (t ? new Date(t).toLocaleString() : "—");
  const iconSpan = { display: "inline-flex", alignItems: "center", gap: 6 } as const;

  return (
    <PageShell>
      <PageHeader
        icon={<Layers3 size={18} />}
        title="Operations Hub"
        subtitle="Digests • Batch jobs • Bulk ops • Notification routing • Load balancer • IP lists"
        actions={
          <button onClick={fetchAll} aria-label="Refresh operations data" style={{ display: "flex", alignItems: "center", gap: 6, background: "var(--dash-surface)", border: "1px solid var(--dash-border)", color: "var(--dash-text)", borderRadius: 8, padding: "8px 12px", cursor: "pointer" }}>
            <RefreshCw size={14} /> Refresh
          </button>
        }
      />

      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 20 }}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--dash-text-muted)", padding: 24 }} role="status">
            <Loader2 size={16} className="spin" /> Loading operations…
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16 }}>
            {/* Message Digests */}
            <GlassCard>
              <SectionTitle count={digests.length}><span style={iconSpan}><Inbox size={14} /> Message Digests</span></SectionTitle>
              {digests.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No digests generated yet. DASH batches low-priority messages automatically.</p>
              ) : (
                digests.slice(0, 8).map((d) => (
                  <div key={d.id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.title || d.id}</div>
                      <div style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>{fmtTime(d.created_at)}</div>
                    </div>
                    {typeof d.item_count === "number" && (
                      <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 10, background: "rgba(63,169,245,0.12)", color: "#3fa9f5", height: "fit-content" }}>{d.item_count} items</span>
                    )}
                  </div>
                ))
              )}
            </GlassCard>

            {/* Batch Jobs */}
            <GlassCard>
              <SectionTitle count={jobs.length}><span style={iconSpan}><Mail size={14} /> Batch Jobs</span></SectionTitle>
              {jobs.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No batch jobs recorded.</p>
              ) : (
                jobs.slice(0, 8).map((j) => {
                  const pct = j.total && j.completed != null ? Math.round((j.completed / j.total) * 100) : null;
                  return (
                    <div key={j.id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span style={{ fontWeight: 600 }}>{j.name || j.id}</span>
                        <span style={{ color: j.status === "completed" ? "var(--accent, #22c55e)" : j.status === "failed" ? "#ef4444" : "#f59e0b" }}>{j.status || "pending"}</span>
                      </div>
                      {pct != null && (
                        <div style={{ height: 4, background: "var(--dash-bg)", borderRadius: 2, marginTop: 6, overflow: "hidden" }}>
                          <div style={{ height: "100%", width: `${pct}%`, background: "#3fa9f5" }} />
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </GlassCard>

            {/* Bulk Operations */}
            <GlassCard>
              <SectionTitle count={ops.length}><span style={iconSpan}><History size={14} /> Bulk Operations</span></SectionTitle>
              {ops.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No bulk operations logged.</p>
              ) : (
                ops.slice(0, 8).map((o) => (
                  <div key={o.id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12, display: "flex", justifyContent: "space-between" }}>
                    <span>{o.operation || "op"} <span style={{ color: "var(--dash-text-muted)" }}>· {o.entity_type || ""}</span></span>
                    <span style={{ color: "var(--dash-text-muted)" }}>{o.affected ?? 0} affected · {o.status || "—"}</span>
                  </div>
                ))
              )}
            </GlassCard>

            {/* Notification Router */}
            <GlassCard>
              <SectionTitle><span style={iconSpan}><Bell size={14} /> Notification Router ({rules.length} rules)</span></SectionTitle>
              {rules.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No routing rules configured.</p>
              ) : (
                rules.slice(0, 8).map((r, i) => (
                  <div key={r.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 500 }}>{r.name || r.id}</span>
                    <span style={{ display: "flex", gap: 8, color: "var(--dash-text-muted)" }}>
                      <span>{r.channel || "—"}</span>
                      <span style={{ padding: "1px 6px", borderRadius: 4, background: "rgba(63,169,245,0.12)", color: "#3fa9f5" }}>{r.priority || "normal"}</span>
                    </span>
                  </div>
                ))
              )}
            </GlassCard>

            {/* Load Balancer */}
            <GlassCard>
              <SectionTitle count={backends.length}><span style={iconSpan}><Scale size={14} /> Load Balancer</span></SectionTitle>
              {backends.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No backends registered with the pool.</p>
              ) : (
                backends.map((b, i) => (
                  <div key={b.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12, display: "flex", justifyContent: "space-between" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: b.healthy ? "var(--accent, #22c55e)" : "#ef4444" }} aria-hidden />
                      {b.name || b.id}
                    </span>
                    <span style={{ color: "var(--dash-text-muted)" }}>{b.requests ?? 0} req · w={b.weight ?? 1}</span>
                  </div>
                ))
              )}
            </GlassCard>

            {/* IP Allowlist */}
            <GlassCard>
              <SectionTitle count={ipLists.length}><span style={iconSpan}><ShieldCheck size={14} /> IP Access Lists</span></SectionTitle>
              {ipLists.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No IP lists configured — all local access allowed by default.</p>
              ) : (
                ipLists.map((l, i) => (
                  <div key={l.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontWeight: 500 }}>{l.name || l.id}</span>
                      <span style={{ padding: "1px 6px", borderRadius: 4, background: "rgba(34,197,94,0.12)", color: "var(--accent, #22c55e)" }}>{l.mode || "allow"}</span>
                    </div>
                    <div style={{ color: "var(--dash-text-muted)", marginTop: 2 }}>{(l.ips || []).join(", ") || "empty"}</div>
                  </div>
                ))
              )}
            </GlassCard>
          </div>
        )}
      </div>
    </PageShell>
  );
}
