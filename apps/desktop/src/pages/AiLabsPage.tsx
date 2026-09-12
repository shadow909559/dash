import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { PageShell, PageHeader, GlassCard, SectionTitle } from "@/components/ultron";
import { FlaskConical, RefreshCw, Loader2, Network, Users, GraduationCap, Database, Eye, GitBranch } from "lucide-react";

interface Relationship {
  id?: string;
  cause?: string;
  effect?: string;
  strength?: number;
  confidence?: number;
}
interface Pattern {
  id?: string;
  type?: string;
  description?: string;
  confidence?: number;
  source?: string;
}
interface Curriculum {
  id?: string;
  name?: string;
  level?: string;
  progress?: number;
  modules?: number;
}
interface Query {
  id?: string;
  question?: string;
  sql?: string;
  status?: string;
  created_at?: string;
}
interface Processed {
  id?: string;
  modality?: string;
  summary?: string;
  created_at?: string;
}
interface Chain {
  id?: string;
  query?: string;
  steps?: number;
  conclusion?: string;
}

const iconSpan = { display: "inline-flex", alignItems: "center", gap: 6 } as const;

export default function AiLabsPage() {
  const [rels, setRels] = useState<Relationship[]>([]);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [queries, setQueries] = useState<Query[]>([]);
  const [processed, setProcessed] = useState<Processed[]>([]);
  const [chains, setChains] = useState<Chain[]>([]);
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
    const [c, f, cu, q, m, r] = await Promise.all([
      safe("/phase4/causal/relationships", (x) => x.relationships ?? [], []),
      safe("/phase4/federated/patterns", (x) => x.patterns ?? [], []),
      safe("/phase4/curriculum", (x) => x.curricula ?? [], []),
      safe("/phase4/nl-sql/queries", (x) => x.queries ?? [], []),
      safe("/phase4/multi-modal/processed", (x) => x.processed ?? [], []),
      safe("/phase4/reasoning/chains", (x) => x.chains ?? [], []),
    ]);
    setRels(c); setPatterns(f); setCurricula(cu); setQueries(q); setProcessed(m); setChains(r);
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  return (
    <PageShell>
      <PageHeader
        icon={<FlaskConical size={18} />}
        title="AI Labs"
        subtitle="Causal inference • Federated patterns • Curriculum learning • NL→SQL • Multi-modal • Reasoning chains"
        actions={
          <button onClick={fetchAll} aria-label="Refresh AI labs data" style={{ display: "flex", alignItems: "center", gap: 6, background: "var(--dash-surface)", border: "1px solid var(--dash-border)", color: "var(--dash-text)", borderRadius: 8, padding: "8px 12px", cursor: "pointer" }}>
            <RefreshCw size={14} /> Refresh
          </button>
        }
      />

      <div style={{ padding: 20 }}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--dash-text-muted)", padding: 24 }} role="status">
            <Loader2 size={16} className="spin" /> Loading labs…
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16 }}>
            <GlassCard>
              <SectionTitle count={rels.length}><span style={iconSpan}><GitBranch size={14} /> Causal Relationships</span></SectionTitle>
              {rels.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No causal links inferred yet — DASH learns them from observed correlations over time.</p>
              ) : (
                rels.slice(0, 8).map((r, i) => (
                  <div key={r.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12, display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.cause || "?"} <span style={{ color: "#3fa9f5" }}>→</span> {r.effect || "?"}</span>
                    <span style={{ color: "var(--dash-text-muted)", flexShrink: 0 }}>conf {r.confidence != null ? `${Math.round(r.confidence * 100)}%` : "—"}</span>
                  </div>
                ))
              )}
            </GlassCard>

            <GlassCard>
              <SectionTitle count={patterns.length}><span style={iconSpan}><Users size={14} /> Federated Patterns</span></SectionTitle>
              {patterns.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No cross-device patterns — privacy-preserving learning activates with companion devices.</p>
              ) : (
                patterns.slice(0, 8).map((p, i) => (
                  <div key={p.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontWeight: 500 }}>{p.type || "pattern"}</span>
                      <span style={{ color: "var(--dash-text-muted)" }}>{p.source || "local"}</span>
                    </div>
                    <div style={{ color: "var(--dash-text-muted)", marginTop: 2 }}>{p.description || ""}</div>
                  </div>
                ))
              )}
            </GlassCard>

            <GlassCard>
              <SectionTitle count={curricula.length}><span style={iconSpan}><GraduationCap size={14} /> Curriculum Learning</span></SectionTitle>
              {curricula.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No curricula active yet.</p>
              ) : (
                curricula.slice(0, 8).map((c, i) => (
                  <div key={c.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontWeight: 500 }}>{c.name || c.id}</span>
                      <span style={{ color: "var(--dash-text-muted)" }}>{c.level || "L1"}</span>
                    </div>
                    {typeof c.progress === "number" && (
                      <div style={{ height: 4, background: "var(--dash-bg)", borderRadius: 2, marginTop: 6, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${Math.round(c.progress * 100)}%`, background: "#3fa9f5" }} />
                      </div>
                    )}
                  </div>
                ))
              )}
            </GlassCard>

            <GlassCard>
              <SectionTitle count={queries.length}><span style={iconSpan}><Database size={14} /> NL → SQL Queries</span></SectionTitle>
              {queries.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No natural-language queries translated yet. Ask DASH a data question in chat to see one here.</p>
              ) : (
                queries.slice(0, 6).map((q, i) => (
                  <div key={q.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12 }}>
                    <div style={{ fontWeight: 500, marginBottom: 2 }}>{q.question || q.id}</div>
                    <code style={{ fontSize: 10, color: "#3fa9f5", wordBreak: "break-all", display: "block", whiteSpace: "pre-wrap" }}>{q.sql || ""}</code>
                  </div>
                ))
              )}
            </GlassCard>

            <GlassCard>
              <SectionTitle count={processed.length}><span style={iconSpan}><Eye size={14} /> Multi-Modal Processed</span></SectionTitle>
              {processed.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No images, audio, or documents processed yet.</p>
              ) : (
                processed.slice(0, 8).map((m, i) => (
                  <div key={m.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12, display: "flex", justifyContent: "space-between" }}>
                    <span style={{ padding: "1px 6px", borderRadius: 4, background: "rgba(63,169,245,0.12)", color: "#3fa9f5", textTransform: "uppercase", fontSize: 10 }}>{m.modality || "unknown"}</span>
                    <span style={{ color: "var(--dash-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.summary || ""}</span>
                  </div>
                ))
              )}
            </GlassCard>

            <GlassCard>
              <SectionTitle count={chains.length}><span style={iconSpan}><Network size={14} /> Reasoning Chains</span></SectionTitle>
              {chains.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No reasoning chains recorded — complex multi-step answers will appear here.</p>
              ) : (
                chains.slice(0, 8).map((c, i) => (
                  <div key={c.id || i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--dash-surface)", marginBottom: 6, fontSize: 12 }}>
                    <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.query || c.id}</div>
                    <div style={{ color: "var(--dash-text-muted)", marginTop: 2 }}>{c.steps ?? "—"} steps · {c.conclusion || "in progress"}</div>
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
