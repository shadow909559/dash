import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { BookOpen, Search, RefreshCw, Globe, Sparkles } from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

export const KnowledgePage: React.FC = () => {
  const [memories, setMemories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[] | null>(null);

  const fetchKnowledge = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/memory?type=knowledge`);
      const d = await r.json();
      setMemories(d.items || d.memories || d || []);
    } catch {}
    setLoading(false);
  }, []);

  const searchKnowledge = async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      fetchKnowledge();
      return;
    }
    setLoading(true);
    try {
      const r = await authFetch(
        `${API}/memory/search?q=${encodeURIComponent(searchQuery)}`
      );
      const d = await r.json();
      setSearchResults(Array.isArray(d) ? d : d.items || []);
    } catch {
      setSearchResults([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchKnowledge();
  }, [fetchKnowledge]);

  const displayItems = searchResults !== null ? searchResults : memories;

  return (
    <PageShell glowColor="rgba(159, 122, 250, 0.05)">
      <PageHeader
        icon={<BookOpen size={22} color="var(--dash-accent-secondary)" />}
        iconColor="var(--dash-accent-secondary)"
        iconBg="rgba(159, 122, 250, 0.15)"
        title="Knowledge Base"
        subtitle="Indexed vector stores, documentation, and local resources"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "rgba(159, 122, 250, 0.12)",
              color: "var(--dash-accent-secondary)",
              border: "1px solid rgba(159, 122, 250, 0.25)",
            }}
          >
            <Globe size={10} />
            {displayItems.length} entries
          </span>
        }
        actions={
          <button onClick={fetchKnowledge} className="dash-btn-ghost" title="Refresh">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Search bar */}
        <GlassCard padding={14}>
          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "center",
              padding: "8px 14px",
              borderRadius: "var(--dash-radius-md)",
              border: "1px solid var(--dash-border)",
              backgroundColor: "var(--dash-bg)",
            }}
          >
            <Search
              size={16}
              style={{ color: "var(--dash-text-muted)", flexShrink: 0 }}
            />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && searchKnowledge()}
              placeholder="Search the knowledge base..."
              style={{
                flex: 1,
                background: "none",
                border: "none",
                color: "var(--dash-text)",
                fontSize: 13,
                outline: "none",
              }}
            />
          </div>
        </GlassCard>

        {/* Results */}
        {loading ? (
          <div
            style={{
              textAlign: "center",
              padding: 48,
              color: "var(--dash-text-muted)",
            }}
          >
            <RefreshCw
              size={18}
              className="animate-rotate"
              style={{ marginBottom: 10 }}
            />
            <div>Indexing knowledge...</div>
          </div>
        ) : displayItems.length === 0 ? (
          <EmptyState
            icon={
              <BookOpen size={28} style={{ color: "var(--dash-accent-secondary)" }} />
            }
            title="No knowledge entries"
            description="The knowledge base will populate as DASH processes documents and learns from conversations."
          />
        ) : (
          <div className="dash-stagger">
            <SectionTitle count={displayItems.length}>Knowledge Store</SectionTitle>
            {displayItems.map((m: any, i: number) => (
              <GlassCard key={m.id || i} padding={14} className="dash-card-glow">
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                  }}
                >
                  <div
                    style={{
                      width: 3,
                      minHeight: 28,
                      borderRadius: 2,
                      background: "var(--dash-accent-secondary)",
                      opacity: 0.5,
                      flexShrink: 0,
                      marginTop: 2,
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: 13,
                        color: "var(--dash-text)",
                        lineHeight: 1.6,
                      }}
                    >
                      {m.content}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        marginTop: 8,
                        alignItems: "center",
                      }}
                    >
                      <span
                        className="dash-badge-glow"
                        style={{
                          background: "rgba(159, 122, 250, 0.12)",
                          color: "var(--dash-accent-secondary)",
                          border: "1px solid rgba(159, 122, 250, 0.25)",
                        }}
                      >
                        {m.type || "knowledge"}
                      </span>
                      {m.score && (
                        <span
                          style={{
                            fontSize: 10,
                            color: "var(--dash-text-muted)",
                            fontFamily: "'JetBrains Mono', monospace",
                          }}
                        >
                          Score: {(m.score * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default KnowledgePage;
