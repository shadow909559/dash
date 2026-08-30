import React, { useState } from "react";
import { authFetch } from "@/lib/api";
import { Globe, Send, AlertCircle, ExternalLink, GlobeLock } from "lucide-react";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

export const BrowserPage: React.FC = () => {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  const browse = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setResult("");
    setError(null);
    try {
      const r = await authFetch(`${API}/ai-os/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: `Browse and summarize: ${url}` }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setResult(data.summary || JSON.stringify(data, null, 2));
      setHistory((prev) => [url, ...prev.slice(0, 9)]);
    } catch (e: any) {
      setError(e.message || "Browse failed");
    }
    setLoading(false);
  };

  return (
    <PageShell glowColor="rgba(77, 148, 255, 0.05)">
      <PageHeader
        icon={<Globe size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        title="Browser Automation"
        subtitle="Headless web interaction, session extraction, and exploration"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "var(--dash-accent-glow)",
              color: "var(--dash-accent)",
              border: "1px solid var(--dash-border-accent)",
            }}
          >
            <GlobeLock size={10} />
            Headless
          </span>
        }
      />

      <div className="dash-page-content">
        {/* URL input */}
        <GlassCard glow padding={16}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "var(--dash-radius-sm)",
                background: "var(--dash-accent-glow)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Globe size={14} style={{ color: "var(--dash-accent)" }} />
            </div>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && browse()}
              placeholder="Enter URL or search query..."
              className="dash-input-ultron"
              style={{ flex: 1, fontFamily: "'JetBrains Mono', monospace" }}
            />
            <button
              onClick={browse}
              disabled={loading || !url.trim()}
              className="dash-btn-primary"
            >
              {loading ? (
                <span className="animate-rotate">...</span>
              ) : (
                <>
                  <Send size={14} /> Browse
                </>
              )}
            </button>
          </div>
        </GlassCard>

        {/* Recent history */}
        {history.length > 0 && (
          <GlassCard padding={12}>
            <div
              style={{
                fontSize: 10,
                fontFamily: "'JetBrains Mono', monospace",
                color: "var(--dash-text-muted)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              Recent
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {history.slice(0, 5).map((h, i) => (
                <button
                  key={i}
                  onClick={() => setUrl(h)}
                  className="dash-btn-ghost"
                  style={{
                    fontSize: 10,
                    padding: "4px 8px",
                    borderRadius: "var(--dash-radius-full)",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  <ExternalLink size={9} />
                  {h.length > 40 ? h.substring(0, 40) + "..." : h}
                </button>
              ))}
            </div>
          </GlassCard>
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
                color: "var(--dash-accent)",
              }}
            >
              <Globe size={18} className="animate-rotate" />
              <span
                style={{
                  fontSize: 13,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                Browsing...
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
              background: "rgba(239, 68, 68, 0.06)",
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
              <Globe size={14} style={{ color: "var(--dash-accent)" }} />
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--dash-text)",
                  fontFamily: "'JetBrains Mono', monospace",
                  letterSpacing: "0.05em",
                }}
              >
                PAGE SUMMARY
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

export default BrowserPage;
