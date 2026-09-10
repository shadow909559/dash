import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { PageShell, PageHeader, GlassCard, EmptyState } from "@/components/ultron";
import { Cpu, Check, Clock, RefreshCw, Loader2 } from "lucide-react";

interface Model {
  id: string;
  provider: string;
  name: string;
  active: boolean;
  tier: string;
}
interface SwapEvent {
  from: string;
  to: string;
  at: string;
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: "#22c55e",
  anthropic: "#8b5cf6",
  deepseek: "#06b6d4",
  groq: "#f59e0b",
  ollama: "#3b82f6",
};

const TIER_COLORS: Record<string, string> = {
  premium: "rgba(139,92,246,0.15)",
  standard: "rgba(6,182,212,0.15)",
  fast: "rgba(245,158,11,0.15)",
  local: "rgba(59,130,246,0.15)",
};

export default function ModelSelectorPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [active, setActive] = useState<string>("");
  const [history, setHistory] = useState<SwapEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [swapping, setSwapping] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState<string>("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, h] = await Promise.all([
        authFetch("/enhanced/models/available"),
        authFetch("/enhanced/models/history"),
      ]);
      if (m?.ok) {
        const d = await m.json();
        setModels(d.models || []);
        setActive(d.active || "");
      } else {
        setError("Backend did not return the model list.");
      }
      if (h?.ok) {
        const d = await h.json();
        setHistory(d.history || []);
      }
    } catch {
      setError("Could not reach the DASH backend. Is it running?");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const swap = async (modelId: string) => {
    if (modelId === active) return;
    setSwapping(modelId);
    try {
      const r = await authFetch(`/enhanced/models/swap?model_id=${encodeURIComponent(modelId)}`, {
        method: "POST",
      });
      if (r?.ok) {
        const d = await r.json();
        if (d.ok !== false) {
          setActive(modelId);
          const h = await authFetch("/enhanced/models/history");
          if (h?.ok) setHistory((await h.json()).history || []);
        }
      }
    } catch {
      setError("Swap failed — try again.");
    }
    setSwapping(null);
  };

  const providers = ["all", ...new Set(models.map((m) => m.provider))];
  const visible = providerFilter === "all" ? models : models.filter((m) => m.provider === providerFilter);

  return (
    <PageShell>
      <PageHeader
        icon={<Cpu size={18} />}
        iconColor="var(--accent, #8b5cf6)"
        iconBg="rgba(139,92,246,0.15)"
        title="Model Selector"
        subtitle="Hot-swap the active AI model across providers without restarting DASH."
        actions={
          <button onClick={load} className="dash-btn-ghost" title="Refresh" aria-label="Refresh models">
            <RefreshCw size={14} className={loading ? "animate-rotate" : undefined} />
          </button>
        }
      />

      {error && (
        <div
          role="alert"
          style={{
            padding: "10px 14px",
            background: "rgba(239,68,68,0.1)",
            border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: 8,
            marginBottom: 16,
            fontSize: 12,
            color: "#ef4444",
          }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ height: 110, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 12, opacity: 0.5 }} />
          ))}
        </div>
      ) : models.length === 0 ? (
        <EmptyState
          icon={<Cpu size={28} />}
          title="No models configured"
          description="Model providers will appear here once configured in the backend."
        />
      ) : (
        <>
          {/* Provider filter */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
            {providers.map((p) => (
              <button
                key={p}
                onClick={() => setProviderFilter(p)}
                aria-pressed={providerFilter === p}
                style={{
                  padding: "5px 12px",
                  borderRadius: 999,
                  fontSize: 11,
                  cursor: "pointer",
                  border: `1px solid ${providerFilter === p ? PROVIDER_COLORS[p] || "#8b5cf6" : "rgba(148,163,184,0.25)"}`,
                  color: providerFilter === p ? PROVIDER_COLORS[p] || "#e2e8f0" : "var(--text-muted, #94a3b8)",
                  background: providerFilter === p ? "rgba(255,255,255,0.05)" : "transparent",
                  textTransform: "capitalize",
                }}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Model cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12, marginBottom: 20 }}>
            {visible.map((m) => {
              const isActive = m.id === active;
              const color = PROVIDER_COLORS[m.provider] || "#94a3b8";
              return (
                <GlassCard
                  key={m.id}
                  className="dash-card-glow"
                  style={isActive ? { border: `1px solid ${color}`, boxShadow: `0 0 14px ${color}33` } : undefined}
                >
                  <button
                    onClick={() => swap(m.id)}
                    disabled={isActive || swapping !== null}
                    aria-label={`${isActive ? "Active model" : "Switch to"} ${m.name}`}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      background: "none",
                      border: "none",
                      color: "inherit",
                      cursor: isActive || swapping !== null ? "default" : "pointer",
                      padding: 0,
                      font: "inherit",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <span
                        style={{
                          fontSize: 10,
                          textTransform: "uppercase",
                          letterSpacing: 0.8,
                          color,
                          fontWeight: 600,
                        }}
                      >
                        {m.provider}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          padding: "2px 8px",
                          borderRadius: 999,
                          background: TIER_COLORS[m.tier] || "rgba(148,163,184,0.15)",
                          color: "var(--text-primary, #e2e8f0)",
                          textTransform: "capitalize",
                        }}
                      >
                        {m.tier}
                      </span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                      {m.name}
                      {isActive && <Check size={14} style={{ color }} aria-label="active" />}
                      {swapping === m.id && <Loader2 size={13} className="spin" />}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted, #64748b)" }}>
                      {isActive ? "Active — used for all AI requests" : swapping === m.id ? "Switching…" : "Click to activate"}
                    </div>
                  </button>
                </GlassCard>
              );
            })}
          </div>

          {/* Swap history */}
          {history.length > 0 && (
            <GlassCard padding={16}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <Clock size={14} style={{ color: "var(--text-muted, #64748b)" }} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>Swap history</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {history.slice(0, 10).map((h, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12 }}>
                    <span style={{ color: "var(--text-muted, #64748b)", fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>
                      {h.at ? new Date(h.at).toLocaleTimeString() : "—"}
                    </span>
                    <span style={{ color: "var(--text-muted, #64748b)" }}>{h.from || "—"}</span>
                    <span aria-hidden="true" style={{ color: "#8b5cf6" }}>→</span>
                    <span style={{ color: "var(--text-primary, #e2e8f0)" }}>{h.to}</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </>
      )}
    </PageShell>
  );
}
