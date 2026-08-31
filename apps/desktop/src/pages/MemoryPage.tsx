import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { Brain, Search, Trash2, RefreshCw, Sparkles, Database } from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Memory {
  id: string;
  content: string;
  type: string;
  created_at: string;
}

export const MemoryPage: React.FC = () => {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await authFetch(`${API}/memory?page=1&per_page=100`);
      const data = await r.json();
      setMemories(data.items || []);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, []);

  const searchMemories = useCallback(async () => {
    if (!searchQuery.trim()) {
      fetchMemories();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await authFetch(
        `${API}/memory/search?q=${encodeURIComponent(searchQuery)}`
      );
      const data = await r.json();
      setMemories(Array.isArray(data) ? data : data.items || []);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, [searchQuery, fetchMemories]);

  const deleteMemory = async (id: string) => {
    try {
      await authFetch(`${API}/memory/${id}`, { method: "DELETE" });
      fetchMemories();
    } catch {}
  };

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const typeColor = (type: string) => {
    switch (type?.toLowerCase()) {
      case "episodic":
        return "var(--dash-accent)";
      case "semantic":
        return "var(--dash-accent-secondary)";
      case "procedural":
        return "var(--dash-cyan)";
      default:
        return "var(--dash-text-muted)";
    }
  };

  return (
    <PageShell glowColor="rgba(159, 122, 250, 0.06)">
      <PageHeader
        icon={<Brain size={22} color="var(--dash-accent-secondary)" />}
        iconColor="var(--dash-accent-secondary)"
        iconBg="rgba(159, 122, 250, 0.15)"
        title="Memory Engine"
        subtitle="Long-term episodic and semantic memory management"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "rgba(159, 122, 250, 0.12)",
              color: "var(--dash-accent-secondary)",
              border: "1px solid rgba(159, 122, 250, 0.25)",
            }}
          >
            <Database size={10} />
            {memories.length} memories
          </span>
        }
        actions={
          <button
            onClick={fetchMemories}
            className="dash-btn-ghost"
            title="Refresh"
          >
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Search bar */}
        <div
          style={{
            display: "flex",
            gap: 8,
          }}
        >
          <div
            style={{
              flex: 1,
              display: "flex",
              gap: 8,
              alignItems: "center",
              padding: "8px 14px",
              borderRadius: "var(--dash-radius-md)",
              border: "1px solid var(--dash-border)",
              backgroundColor: "var(--dash-surface)",
              transition: "border-color var(--dash-transition-fast)",
            }}
          >
            <Search
              size={16}
              style={{ color: "var(--dash-text-muted)", flexShrink: 0 }}
            />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && searchMemories()}
              placeholder="Search memories..."
              style={{
                flex: 1,
                background: "none",
                border: "none",
                color: "var(--dash-text)",
                fontSize: 13,
                /* a11y: removed outline:none — global :focus-visible handles focus */
              }}
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <GlassCard
            glow
            padding={12}
            style={{
              borderLeft: "3px solid var(--dash-danger)",
              background: "rgba(63, 169, 245, 0.06)",
            }}
          >
            <span style={{ fontSize: 12, color: "var(--dash-danger)" }}>
              {error}
            </span>
          </GlassCard>
        )}

        {/* Content */}
        {loading ? (
          <div
            style={{
              textAlign: "center",
              padding: 48,
              color: "var(--dash-text-muted)",
              fontSize: 13,
            }}
          >
            <RefreshCw
              size={18}
              className="animate-rotate"
              style={{ marginBottom: 10 }}
            />
            <div>Loading memories...</div>
          </div>
        ) : memories.length === 0 ? (
          <EmptyState
            icon={<Brain size={28} style={{ color: "var(--dash-accent-secondary)" }} />}
            title="No memories yet"
            description="Start chatting with DASH to build long-term memory. Memories are automatically created from your conversations."
          />
        ) : (
          <div className="dash-stagger">
            <SectionTitle count={memories.length}>Memory Store</SectionTitle>
            {memories.map((m) => (
              <GlassCard key={m.id} padding={0} className="dash-card-glow">
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                    padding: "14px 18px",
                  }}
                >
                  {/* Type indicator */}
                  <div
                    style={{
                      width: 3,
                      minHeight: 32,
                      borderRadius: 2,
                      background: typeColor(m.type),
                      opacity: 0.6,
                      flexShrink: 0,
                      marginTop: 2,
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        color: "var(--dash-text)",
                        lineHeight: 1.5,
                        marginBottom: 6,
                      }}
                    >
                      {m.content}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span
                        className="dash-badge-glow"
                        style={{
                          background: `${typeColor(m.type)}15`,
                          color: typeColor(m.type),
                          border: `1px solid ${typeColor(m.type)}30`,
                        }}
                      >
                        {m.type || "general"}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        {new Date(m.created_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => deleteMemory(m.id)}
                    className="dash-btn-ghost"
                    style={{ flexShrink: 0, padding: 6 }}
                    title="Delete memory"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default MemoryPage;
