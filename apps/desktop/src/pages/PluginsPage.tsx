import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import {
  Puzzle,
  RefreshCw,
  Mic,
  Globe,
  Monitor,
  Brain,
  Network,
  Workflow,
  CheckCircle,
  Cpu,
  Layers,
  Star,
  Download,
  Trash2,
  Power,
  Store,
  PackageOpen,
  Loader2,
} from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle, StatusIndicator, TabBar } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface MarketplacePlugin {
  id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  category: string;
  permissions: string[];
  rating: number;
  installs: number;
  icon: string;
  status: string;
}

export const PluginsPage: React.FC = () => {
  const [tab, setTab] = useState<"marketplace" | "modules">("marketplace");
  const [market, setMarket] = useState<MarketplacePlugin[]>([]);
  const [installed, setInstalled] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [category, setCategory] = useState("all");
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, i] = await Promise.all([
        authFetch(`${API}/enhanced/plugins/marketplace`),
        authFetch(`${API}/enhanced/plugins/installed`),
      ]);
      if (m?.ok) setMarket((await m.json()).plugins || []);
      if (i?.ok) setInstalled((await i.json()).plugins || []);
    } catch {
      setError("Could not reach the DASH backend. Is it running?");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const act = async (pluginId: string, action: "install" | "uninstall" | "toggle") => {
    setBusy(`${pluginId}:${action}`);
    try {
      await authFetch(`${API}/enhanced/plugins/${pluginId}/${action}`, { method: "POST" });
      await fetchAll();
    } catch {
      setError(`Failed to ${action} ${pluginId}.`);
    }
    setBusy(null);
  };

  const categories = ["all", ...new Set(market.map((p) => p.category))];
  const visible = category === "all" ? market : market.filter((p) => p.category === category);
  const installedIds = new Set(installed.filter((p) => p.status !== "uninstalled").map((p) => p.id));

  const builtinModules = [
    { name: "Voice System", desc: "STT + TTS providers, wake word, conversation mode", icon: Mic, status: "active", color: "var(--dash-cyan)" },
    { name: "Browser Automation", desc: "Web scraping, research mode, tab management", icon: Globe, status: "active", color: "var(--dash-accent)" },
    { name: "Desktop Control", desc: "Mouse, keyboard, window management, power controls", icon: Monitor, status: "active", color: "var(--dash-success)" },
    { name: "Memory Engine", desc: "Long-term episodic and semantic memory with embeddings", icon: Brain, status: "active", color: "var(--dash-accent-secondary)" },
    { name: "Neural Network", desc: "Context engine, personality, self-improvement", icon: Network, status: "active", color: "var(--dash-warning)" },
    { name: "Orchestrator", desc: "Master orchestrator, decision engine, tool chains", icon: Workflow, status: "active", color: "var(--dash-info)" },
  ];

  return (
    <PageShell glowColor="rgba(159, 122, 250, 0.05)">
      <PageHeader
        icon={<Puzzle size={22} color="var(--dash-accent-secondary)" />}
        iconColor="var(--dash-accent-secondary)"
        iconBg="rgba(159, 122, 250, 0.12)"
        title="Plugins & Extensions"
        subtitle="Marketplace plugins, installs, and built-in modules"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "rgba(159, 122, 250, 0.10)",
              color: "var(--dash-accent-secondary)",
              border: "1px solid rgba(159, 122, 250, 0.25)",
            }}
          >
            <Layers size={10} />
            {market.length} available
          </span>
        }
        actions={
          <button onClick={fetchAll} className="dash-btn-ghost" title="Refresh" aria-label="Refresh plugins">
            <RefreshCw size={14} className={loading ? "animate-rotate" : undefined} />
          </button>
        }
      />

      <div className="dash-page-content">
        <TabBar
          tabs={[
            { id: "marketplace", label: "Marketplace", icon: <Store size={13} />, count: market.length },
            { id: "modules", label: "Built-in Modules", icon: <PackageOpen size={13} />, count: builtinModules.length },
          ]}
          activeTab={tab}
          onTabChange={(id) => setTab(id as "marketplace" | "modules")}
        />

        {error && (
          <div role="alert" style={{ padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, marginBottom: 16, fontSize: 12, color: "#ef4444" }}>
            {error}
          </div>
        )}

        {tab === "marketplace" && (
          <>
            {/* Category filter */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
              {categories.map((c) => (
                <button
                  key={c}
                  onClick={() => setCategory(c)}
                  aria-pressed={category === c}
                  style={{
                    padding: "5px 12px",
                    borderRadius: 999,
                    fontSize: 11,
                    cursor: "pointer",
                    border: `1px solid ${category === c ? "var(--dash-accent-secondary)" : "var(--dash-border)"}`,
                    color: category === c ? "var(--dash-accent-secondary)" : "var(--dash-text-muted)",
                    background: category === c ? "rgba(159,122,250,0.1)" : "transparent",
                    textTransform: "capitalize",
                  }}
                >
                  {c}
                </button>
              ))}
            </div>

            {loading ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} style={{ height: 96, background: "var(--dash-bg)", borderRadius: "var(--dash-radius-md)", opacity: 0.5 }} />
                ))}
              </div>
            ) : visible.length === 0 ? (
              <EmptyState icon={<Store size={28} style={{ color: "var(--dash-text-muted)" }} />} title="No plugins in this category" description="Try another category or refresh." />
            ) : (
              <div className="dash-stagger">
                <SectionTitle count={visible.length}>Marketplace</SectionTitle>
                {visible.map((p) => {
                  const isInstalled = installedIds.has(p.id) || p.status === "installed";
                  const busyKey = busy?.startsWith(p.id);
                  return (
                    <GlassCard key={p.id} padding={14} className="dash-card-glow">
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <div
                          style={{
                            width: 38,
                            height: 38,
                            borderRadius: "var(--dash-radius-sm)",
                            background: "rgba(159,122,250,0.12)",
                            border: "1px solid rgba(159,122,250,0.2)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}
                        >
                          <Cpu size={17} style={{ color: "var(--dash-accent-secondary)" }} />
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>{p.name}</span>
                            <span style={{ fontSize: 10, color: "var(--dash-text-muted)", border: "1px solid var(--dash-border)", borderRadius: 999, padding: "1px 7px" }}>
                              v{p.version}
                            </span>
                            <span style={{ fontSize: 10, color: "var(--dash-text-muted)", textTransform: "capitalize" }}>{p.category}</span>
                          </div>
                          <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 3, lineHeight: 1.4 }}>{p.description}</div>
                          <div style={{ display: "flex", gap: 12, marginTop: 5, alignItems: "center", fontSize: 10, color: "var(--dash-text-muted)" }}>
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                              <Star size={10} style={{ color: "#f59e0b" }} /> {p.rating?.toFixed?.(1) ?? p.rating}
                            </span>
                            <span>{(p.installs ?? 0).toLocaleString()} installs</span>
                            <span>by {p.author}</span>
                            {p.permissions?.length > 0 && (
                              <span title={p.permissions.join(", ")}>
                                {p.permissions.length} permission{p.permissions.length > 1 ? "s" : ""}
                              </span>
                            )}
                          </div>
                        </div>
                        {isInstalled ? (
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              onClick={() => act(p.id, "toggle")}
                              disabled={!!busy}
                              title="Enable / disable"
                              aria-label={`Toggle ${p.name}`}
                              className="dash-btn-ghost"
                              style={{ minHeight: 24, minWidth: 24 }}
                            >
                              {busyKey && busy === `${p.id}:toggle` ? <Loader2 size={13} className="spin" /> : <Power size={13} />}
                            </button>
                            <button
                              onClick={() => act(p.id, "uninstall")}
                              disabled={!!busy}
                              title="Uninstall"
                              aria-label={`Uninstall ${p.name}`}
                              className="dash-btn-ghost"
                              style={{ minHeight: 24, minWidth: 24, color: "#ef4444" }}
                            >
                              {busyKey && busy === `${p.id}:uninstall` ? <Loader2 size={13} className="spin" /> : <Trash2 size={13} />}
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => act(p.id, "install")}
                            disabled={!!busy}
                            aria-label={`Install ${p.name}`}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 6,
                              padding: "6px 12px",
                              borderRadius: "var(--dash-radius-sm)",
                              border: "1px solid rgba(159,122,250,0.35)",
                              background: "rgba(159,122,250,0.12)",
                              color: "var(--dash-accent-secondary)",
                              fontSize: 11,
                              fontWeight: 600,
                              cursor: "pointer",
                              minHeight: 24,
                            }}
                          >
                            {busyKey && busy === `${p.id}:install` ? <Loader2 size={12} className="spin" /> : <Download size={12} />}
                            Install
                          </button>
                        )}
                      </div>
                    </GlassCard>
                  );
                })}
              </div>
            )}

            {/* Installed (from backend registry) */}
            {installed.length > 0 && (
              <>
                <div style={{ marginTop: 8 }}>
                  <SectionTitle count={installed.length}>Registry</SectionTitle>
                </div>
                {installed.map((p: any) => (
                  <GlassCard key={p.id} padding={14} className="dash-card-glow">
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <CheckCircle size={16} style={{ color: "var(--dash-success)", flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>{p.name || p.id}</div>
                        <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 2 }}>{p.description || "No description"}</div>
                      </div>
                      <StatusIndicator status={p.status === "disabled" ? "offline" : "online"} label={p.status || "installed"} />
                    </div>
                  </GlassCard>
                ))}
              </>
            )}
          </>
        )}

        {tab === "modules" && (
          <div className="dash-stagger" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {builtinModules.map((m) => {
              const Icon = m.icon;
              return (
                <GlassCard key={m.name} padding={14} className="dash-card-glow">
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: "var(--dash-radius-sm)",
                        background: `${m.color}12`,
                        border: `1px solid ${m.color}25`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <Icon size={16} style={{ color: m.color }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--dash-text)" }}>{m.name}</div>
                      <div style={{ fontSize: 10, color: "var(--dash-text-muted)", marginTop: 3, lineHeight: 1.4 }}>{m.desc}</div>
                    </div>
                    <StatusIndicator status="online" label="active" />
                  </div>
                </GlassCard>
              );
            })}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default PluginsPage;
