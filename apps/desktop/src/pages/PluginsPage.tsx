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
} from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle, StatusIndicator } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

export const PluginsPage: React.FC = () => {
  const [plugins, setPlugins] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPlugins = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/plugins`);
      const d = await r.json();
      setPlugins(d.plugins || d || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  const builtinModules = [
    {
      name: "Voice System",
      desc: "STT + TTS providers, wake word, conversation mode",
      icon: Mic,
      status: "active",
      color: "var(--dash-cyan)",
    },
    {
      name: "Browser Automation",
      desc: "Web scraping, research mode, tab management",
      icon: Globe,
      status: "active",
      color: "var(--dash-accent)",
    },
    {
      name: "Desktop Control",
      desc: "Mouse, keyboard, window management, power controls",
      icon: Monitor,
      status: "active",
      color: "var(--dash-success)",
    },
    {
      name: "Memory Engine",
      desc: "Long-term episodic and semantic memory with embeddings",
      icon: Brain,
      status: "active",
      color: "var(--dash-accent-secondary)",
    },
    {
      name: "Neural Network",
      desc: "Context engine, personality, self-improvement",
      icon: Network,
      status: "active",
      color: "var(--dash-warning)",
    },
    {
      name: "Orchestrator",
      desc: "Master orchestrator, decision engine, tool chains",
      icon: Workflow,
      status: "active",
      color: "var(--dash-info)",
    },
  ];

  return (
    <PageShell glowColor="rgba(159, 122, 250, 0.05)">
      <PageHeader
        icon={<Puzzle size={22} color="var(--dash-accent-secondary)" />}
        iconColor="var(--dash-accent-secondary)"
        iconBg="rgba(159, 122, 250, 0.12)"
        title="Plugins & Extensions"
        subtitle="Built-in modules and installed integrations"
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
            {builtinModules.length} built-in
          </span>
        }
        actions={
          <button onClick={fetchPlugins} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Built-in modules */}
        <SectionTitle>Built-in Modules</SectionTitle>
        <div
          className="dash-stagger"
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
          }}
        >
          {builtinModules.map((m) => {
            const Icon = m.icon;
            return (
              <GlassCard key={m.name} padding={14} className="dash-card-glow">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                  }}
                >
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
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--dash-text)",
                      }}
                    >
                      {m.name}
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: "var(--dash-text-muted)",
                        marginTop: 3,
                        lineHeight: 1.4,
                      }}
                    >
                      {m.desc}
                    </div>
                  </div>
                  <StatusIndicator status="online" label="active" />
                </div>
              </GlassCard>
            );
          })}
        </div>

        {/* Installed plugins */}
        {plugins.length > 0 && (
          <>
            <div style={{ marginTop: 8 }}><SectionTitle count={plugins.length}>
              Installed Plugins
            </SectionTitle></div>
            {plugins.map((p: any, i: number) => (
              <GlassCard key={i} padding={14} className="dash-card-glow">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "var(--dash-radius-sm)",
                      background: "rgba(159,122,250,0.12)",
                      border: "1px solid rgba(159,122,250,0.2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Cpu
                      size={16}
                      style={{ color: "var(--dash-accent-secondary)" }}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--dash-text)",
                      }}
                    >
                      {p.name || p.id || "Plugin"}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--dash-text-muted)",
                        marginTop: 2,
                      }}
                    >
                      {p.description || "No description"}
                    </div>
                  </div>
                  <span
                    className="dash-badge-glow"
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      color: "var(--dash-text-secondary)",
                      border: "1px solid var(--dash-border)",
                    }}
                  >
                    {p.status || "installed"}
                  </span>
                </div>
              </GlassCard>
            ))}
          </>
        )}

        {plugins.length === 0 && (
          <EmptyState
            icon={
              <Puzzle size={28} style={{ color: "var(--dash-text-muted)" }} />
            }
            title="No external plugins installed"
            description="Plugins extend DASH with new capabilities and integrations."
          />
        )}
      </div>
    </PageShell>
  );
};

export default PluginsPage;
