import React, { useState } from "react";
import { authFetch } from "@/lib/api";
import { Compass, Send, AlertCircle, Search, FileText, Sparkles } from "lucide-react";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

export const ResearchPage: React.FC = () => {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startResearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResult("");
    setError(null);
    try {
      const r = await authFetch(`${API}/ai-os/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: `Research topic: ${query}` }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setResult(data.summary || JSON.stringify(data, null, 2));
    } catch (e: any) {
      setError(e.message || "Research failed");
    }
    setLoading(false);
  };

  const topics = [
    "Latest advances in local LLMs",
    "Quantum computing applications",
    "WebAssembly performance benchmarks",
    "Neural architecture search techniques",
  ];

  return (
    <PageShell glowColor="rgba(159, 122, 250, 0.05)">
      <PageHeader
        icon={<Compass size={22} color="var(--dash-accent-secondary)" />}
        iconColor="var(--dash-accent-secondary)"
        iconBg="rgba(159, 122, 250, 0.12)"
        title="Research & Intelligence"
        subtitle="Deep-web synthesis, citation tracking, and report generation"
      />

      <div className="dash-page-content">
        {/* Input */}
        <GlassCard glow padding={16}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Search
              size={16}
              style={{
                color: "var(--dash-text-muted)",
                flexShrink: 0,
              }}
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && startResearch()}
              placeholder="What would you like to research?"
              className="dash-input-ultron"
              style={{ flex: 1 }}
            />
            <button
              onClick={startResearch}
              disabled={loading || !query.trim()}
              className="dash-btn-primary"
              style={{
                background: "var(--dash-accent-secondary)",
                boxShadow: "0 0 16px rgba(159,122,250,0.2)",
              }}
            >
              {loading ? "Researching..." : <><Send size={14} /> Research</>}
            </button>
          </div>
        </GlassCard>

        {/* Topic suggestions */}
        {!result && !loading && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {topics.map((t) => (
              <button
                key={t}
                onClick={() => setQuery(t)}
                className="dash-btn-ghost"
                style={{
                  fontSize: 11,
                  padding: "6px 12px",
                  borderRadius: "var(--dash-radius-full)",
                  background: "var(--dash-surface)",
                }}
              >
                <Sparkles size={10} style={{ opacity: 0.6 }} />
                {t}
              </button>
            ))}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <GlassCard padding={24}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 12,
                color: "var(--dash-accent-secondary)",
              }}
            >
              <Compass size={18} className="animate-rotate" />
              <span
                style={{
                  fontSize: 13,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                Researching...
              </span>
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </GlassCard>
        )}

        {/* Error */}
        {error && (
          <GlassCard
            glow
            padding={14}
            style={{
              borderLeft: "3px solid var(--dash-danger)",
              background: "rgba(63, 169, 245, 0.06)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <AlertCircle
                size={16}
                style={{ color: "var(--dash-danger)", flexShrink: 0 }}
              />
              <span style={{ fontSize: 13, color: "var(--dash-danger)" }}>
                {error}
              </span>
            </div>
          </GlassCard>
        )}

        {/* Result */}
        {result && (
          <GlassCard glow padding={0}>
            <div
              style={{
                padding: "14px 18px 10px",
                borderBottom: "1px solid var(--dash-border-subtle)",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <FileText
                size={14}
                style={{ color: "var(--dash-accent-secondary)" }}
              />
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--dash-text)",
                  fontFamily: "'JetBrains Mono', monospace",
                  letterSpacing: "0.05em",
                }}
              >
                RESEARCH RESULTS
              </span>
            </div>
            <div
              style={{
                fontSize: 13,
                color: "var(--dash-text-secondary)",
                lineHeight: 1.7,
                whiteSpace: "pre-wrap",
                padding: 18,
                background: "var(--dash-bg)",
                borderTop: "1px solid var(--dash-border-subtle)",
              }}
            >
              {result}
            </div>
          </GlassCard>
        )}
      </div>
    </PageShell>
  );
};

export default ResearchPage;
