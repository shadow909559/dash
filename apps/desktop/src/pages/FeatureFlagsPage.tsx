import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { Flag, ToggleLeft, ToggleRight, FlaskConical, BarChart3 } from "lucide-react";

export default function FeatureFlagsPage() {
  const { addNotification } = useNotifier();
  const [flags, setFlags] = useState<Record<string, any>>({});
  const [experiments, setExperiments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const [fRes, eRes] = await Promise.all([authFetch("/phase3/feature-flags"), authFetch("/phase3/experiments")]);
      if (fRes?.ok) setFlags(await fRes.json());
      if (eRes?.ok) setExperiments((await eRes.json()).experiments || []);
    } catch {
      setFlags({
        voice_commands: { enabled: true, rollout_percentage: 100, description: "Voice command support" },
        browser_automation: { enabled: true, rollout_percentage: 100, description: "Browser automation features" },
        plugin_marketplace: { enabled: true, rollout_percentage: 100, description: "Plugin marketplace" },
        knowledge_graph: { enabled: true, rollout_percentage: 100, description: "Knowledge graph visualization" },
        prompt_studio: { enabled: true, rollout_percentage: 100, description: "Prompt engineering studio" },
        workflow_builder: { enabled: true, rollout_percentage: 100, description: "Visual workflow builder" },
        model_ensemble: { enabled: true, rollout_percentage: 100, description: "Multi-model ensemble" },
        conversation_branching: { enabled: true, rollout_percentage: 100, description: "Conversation forking" },
        email_integration: { enabled: true, rollout_percentage: 100, description: "Email read/send" },
        calendar_sync: { enabled: true, rollout_percentage: 100, description: "Calendar sync" },
        encrypted_messaging: { enabled: true, rollout_percentage: 100, description: "E2E encrypted messaging" },
        "2fa_totp": { enabled: true, rollout_percentage: 100, description: "TOTP two-factor auth" },
        password_vault: { enabled: true, rollout_percentage: 100, description: "Encrypted password storage" },
        collaboration: { enabled: true, rollout_percentage: 100, description: "Multi-user collaboration" },
      });
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const toggleFlag = (name: string) => {
    setFlags(prev => ({ ...prev, [name]: { ...prev[name], enabled: !prev[name]?.enabled } }));
    addNotification({ type: "info", title: "Feature Flag", message: `${name} ${flags[name]?.enabled ? "disabled" : "enabled"}` });
  };

  return (
    <PageShell>
      <PageHeader icon={<Flag size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Feature Flags" subtitle={`${Object.keys(flags).length} flags • ${experiments.length} experiments`} />

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{[1, 2, 3].map(i => <div key={i} style={{ height: 60, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 8, opacity: 0.5 }} />)}</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Feature Flags */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Feature Flags</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {Object.entries(flags).map(([name, flag]: [string, any]) => (
                <div key={name} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 500, fontFamily: "monospace" }}>{name}</div>
                    <div style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>{flag.description}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>{flag.rollout_percentage}%</span>
                    <button onClick={() => toggleFlag(name)} style={{ background: "none", border: "none", cursor: "pointer", color: flag.enabled ? "var(--accent, #22c55e)" : "var(--text-muted, #666)" }}>
                      {flag.enabled ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* A/B Experiments */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 6 }}><FlaskConical size={14} /> A/B Experiments ({experiments.length})</h4>
            {experiments.length === 0 ? (
              <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted, #666)" }}>
                <FlaskConical size={24} style={{ marginBottom: 8, opacity: 0.3 }} />
                <p style={{ fontSize: 12 }}>No active experiments</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {experiments.map(exp => (
                  <div key={exp.id} style={{ padding: "10px 12px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 500 }}>{exp.name}</span>
                      <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: exp.status === "running" ? "rgba(34,197,94,0.15)" : "rgba(100,100,100,0.15)", color: exp.status === "running" ? "var(--accent, #22c55e)" : "var(--text-muted, #666)" }}>{exp.status}</span>
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>Metric: {exp.metric}</div>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>
      )}
    </PageShell>
  );
}
