import React, { useState } from "react";
import { authFetch } from "@/lib/api";
import { Code2, Send, AlertCircle, FileCode2, Sparkles, Copy, Check } from "lucide-react";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

export const CodingPage: React.FC = () => {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const requestCode = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResult("");
    setError(null);
    try {
      const r = await authFetch(`${API}/ai-os/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: `Code task: ${query}` }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setResult(data.summary || JSON.stringify(data, null, 2));
    } catch (e: any) {
      setError(e.message || "Code execution failed");
    }
    setLoading(false);
  };

  const copyResult = () => {
    navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const suggestions = [
    "Write a Python function to parse CSV files",
    "Refactor this code to use async/await",
    "Create a React component for a data table",
    "Debug this error: TypeError: cannot read property of undefined",
  ];

  return (
    <PageShell glowColor="rgba(34, 211, 238, 0.05)">
      <PageHeader
        icon={<Code2 size={22} color="var(--dash-cyan)" />}
        iconColor="var(--dash-cyan)"
        iconBg="rgba(34, 211, 238, 0.12)"
        title="Coding Environment"
        subtitle="Autonomous code generation, refactoring, and debugging"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "rgba(34, 211, 238, 0.10)",
              color: "var(--dash-cyan)",
              border: "1px solid rgba(34, 211, 238, 0.25)",
            }}
          >
            <FileCode2 size={10} />
            DASH Code
          </span>
        }
      />

      <div className="dash-page-content">
        {/* Input area */}
        <GlassCard glow padding={16}>
          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "center",
            }}
          >
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && requestCode()}
              placeholder="Describe a coding task..."
              className="dash-input-ultron"
              style={{
                flex: 1,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 13,
              }}
            />
            <button
              onClick={requestCode}
              disabled={loading || !query.trim()}
              className="dash-btn-primary"
              style={{
                background: loading ? undefined : "var(--dash-cyan)",
                boxShadow: loading ? undefined : "0 0 16px rgba(34,211,238,0.2)",
              }}
            >
              {loading ? (
                <span className="animate-rotate" style={{ display: "inline-flex" }}>
                  <Send size={14} />
                </span>
              ) : (
                <>
                  <Send size={14} /> Execute
                </>
              )}
            </button>
          </div>
        </GlassCard>

        {/* Quick suggestions */}
        {!result && !loading && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => {
                  setQuery(s);
                }}
                className="dash-btn-ghost"
                style={{
                  fontSize: 11,
                  padding: "6px 12px",
                  borderRadius: "var(--dash-radius-full)",
                  border: "1px solid var(--dash-border)",
                  background: "var(--dash-surface)",
                }}
              >
                <Sparkles size={10} style={{ opacity: 0.6 }} />
                {s.length > 40 ? s.substring(0, 40) + "..." : s}
              </button>
            ))}
          </div>
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
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
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

        {/* Loading indicator */}
        {loading && (
          <GlassCard padding={24}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 12,
                color: "var(--dash-cyan)",
              }}
            >
              <div className="animate-rotate">
                <Code2 size={18} />
              </div>
              <span
                style={{
                  fontSize: 13,
                  fontFamily: "'JetBrains Mono', monospace",
                  letterSpacing: "0.05em",
                }}
              >
                DASH is coding...
              </span>
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </GlassCard>
        )}

        {/* Result */}
        {result && (
          <GlassCard glow padding={0}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "14px 18px 10px",
                borderBottom: "1px solid var(--dash-border-subtle)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <FileCode2
                  size={14}
                  style={{ color: "var(--dash-cyan)" }}
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
                  RESULT
                </span>
              </div>
              <button
                onClick={copyResult}
                className="dash-btn-ghost"
                style={{ padding: "4px 8px" }}
              >
                {copied ? (
                  <>
                    <Check size={12} /> Copied
                  </>
                ) : (
                  <>
                    <Copy size={12} /> Copy
                  </>
                )}
              </button>
            </div>
            <pre
              style={{
                fontSize: 12,
                color: "var(--dash-text-secondary)",
                fontFamily: "'JetBrains Mono', monospace",
                whiteSpace: "pre-wrap",
                margin: 0,
                lineHeight: 1.7,
                padding: 18,
                background: "var(--dash-bg)",
                borderTop: "1px solid var(--dash-border-subtle)",
              }}
            >
              {result}
            </pre>
          </GlassCard>
        )}
      </div>
    </PageShell>
  );
};

export default CodingPage;
