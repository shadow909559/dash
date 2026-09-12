import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { PageShell, PageHeader, GlassCard, EmptyState, SectionTitle } from "@/components/ultron";
import { FileText, RefreshCw, Loader2, Search, Trash2, Upload } from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Document {
  id: string;
  filename: string | null;
  content: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

interface SearchHit {
  document_id: string;
  filename: string | null;
  chunk_index: number;
  chunk_text: string;
  score: number;
}

export default function RagDocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API}/documents`);
      if (res?.ok) setDocs(await res.json());
    } catch {
      setDocs([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  const addDoc = async () => {
    const filename = window.prompt("Document name (optional)");
    const content = window.prompt("Document content");
    if (!content) return;
    const res = await authFetch(`${API}/documents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: filename || undefined, content }),
    });
    if (res?.ok) fetchDocs();
  };

  const deleteDoc = async (id: string) => {
    setBusyId(id);
    try {
      const res = await authFetch(`${API}/documents/${id}`, { method: "DELETE" });
      if (res?.ok || res?.status === 204) setDocs((d) => d.filter((x) => x.id !== id));
    } finally {
      setBusyId(null);
    }
  };

  const search = async () => {
    if (!query.trim()) { setHits(null); return; }
    setSearching(true);
    try {
      const res = await authFetch(`${API}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), top_k: 8 }),
      });
      setHits(res?.ok ? (await res.json()).items || [] : []);
    } catch {
      setHits([]);
    }
    setSearching(false);
  };

  return (
    <PageShell>
      <PageHeader
        icon={<FileText size={18} />}
        iconColor="var(--dash-accent)"
        title="Knowledge Documents"
        subtitle="RAG document store — upload text, chunked and embedded for semantic search"
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={fetchDocs}
              aria-label="Refresh documents"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text)", cursor: "pointer", fontSize: 12 }}
            >
              <RefreshCw size={13} /> Refresh
            </button>
            <button
              onClick={addDoc}
              aria-label="Add document"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-accent)", background: "var(--dash-accent-glow)", color: "var(--dash-accent)", cursor: "pointer", fontSize: 12, fontWeight: 600 }}
            >
              <Upload size={13} /> Add document
            </button>
          </div>
        }
      />
      <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 24 }}>
        <section>
          <SectionTitle>Semantic search</SectionTitle>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") search(); }}
              placeholder="Search across all document chunks…"
              aria-label="Semantic search query"
              style={{ flex: 1, padding: "9px 12px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text)", fontSize: 13, outline: "none" }}
            />
            <button
              onClick={search}
              disabled={searching}
              aria-label="Run semantic search"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-accent)", background: "var(--dash-accent-glow)", color: "var(--dash-accent)", cursor: "pointer", fontSize: 12 }}
            >
              {searching ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />} Search
            </button>
          </div>
          {hits !== null && (
            <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
              {hits.length === 0 ? (
                <div style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No matching chunks. Upload more documents or rephrase.</div>
              ) : (
                hits.map((h, i) => (
                  <GlassCard key={`${h.document_id}-${h.chunk_index}-${i}`} padding={12}>
                    <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 4, display: "flex", justifyContent: "space-between" }}>
                      <span>{h.filename || h.document_id.slice(0, 8)} · chunk {h.chunk_index}</span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>score {h.score.toFixed(3)}</span>
                    </div>
                    <div style={{ fontSize: 12, lineHeight: 1.5, overflowWrap: "anywhere" }}>{h.chunk_text}</div>
                  </GlassCard>
                ))
              )}
            </div>
          )}
        </section>

        <section>
          <SectionTitle count={docs.length}>Documents</SectionTitle>
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: 40 }}><Loader2 size={20} className="animate-spin" /></div>
          ) : docs.length === 0 ? (
            <EmptyState
              icon={<FileText size={28} />}
              title="No documents yet"
              description="Add a text document and DASH will chunk it, generate embeddings, and make it searchable."
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {docs.map((d) => (
                <GlassCard key={d.id} padding={14}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <FileText size={16} style={{ color: "var(--dash-accent)", flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, overflowWrap: "anywhere" }}>{d.filename || "Untitled document"}</div>
                      <div style={{ fontSize: 11, color: "var(--dash-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {d.content.slice(0, 140)}{d.content.length > 140 ? "…" : ""}
                      </div>
                    </div>
                    <span style={{ fontSize: 10, color: "var(--dash-text-muted)", whiteSpace: "nowrap" }}>
                      {new Date(d.created_at).toLocaleDateString()}
                    </span>
                    <button
                      onClick={() => deleteDoc(d.id)}
                      disabled={busyId === d.id}
                      aria-label={`Delete ${d.filename || "document"}`}
                      style={{ padding: 6, borderRadius: "var(--dash-radius-sm)", border: "1px solid transparent", background: "transparent", color: "var(--dash-danger)", cursor: "pointer", display: "flex" }}
                    >
                      {busyId === d.id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                    </button>
                  </div>
                </GlassCard>
              ))}
            </div>
          )}
        </section>
      </div>
    </PageShell>
  );
}
