import React, { useState, useEffect, useCallback } from "react";
import { automation } from "@/lib/api";
import { Zap, Plus, Trash2, RefreshCw, Clock, ToggleLeft, ToggleRight } from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle } from "@/components/ultron";

interface Rule {
  id: string;
  name: string;
  trigger: string;
  action: string;
  enabled: boolean;
}

export const AutomationPage: React.FC = () => {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("");
  const [action, setAction] = useState("");

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      setRules(await automation.getRules());
    } catch {}
    setLoading(false);
  }, []);

  const createRule = async () => {
    if (!name.trim()) return;
    try {
      await automation.createRule({ name, trigger, action, enabled: true });
      setName("");
      setTrigger("");
      setAction("");
      setShowCreate(false);
      fetchRules();
    } catch {}
  };

  const toggleRule = async (id: string, enabled: boolean) => {
    try {
      await automation.toggleRule(id, !enabled);
      fetchRules();
    } catch {}
  };

  const deleteRule = async (id: string) => {
    try {
      await automation.deleteRule(id);
      fetchRules();
    } catch {}
  };

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const enabledCount = rules.filter((r) => r.enabled).length;

  return (
    <PageShell glowColor="rgba(251, 191, 36, 0.05)">
      <PageHeader
        icon={<Zap size={22} color="var(--dash-warning)" />}
        iconColor="var(--dash-warning)"
        iconBg="rgba(251, 191, 36, 0.12)"
        title="Automation & Workflows"
        subtitle="Event-driven background workflows and scheduled triggers"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "rgba(251, 191, 36, 0.10)",
              color: "var(--dash-warning)",
              border: "1px solid rgba(251, 191, 36, 0.25)",
            }}
          >
            <Clock size={10} />
            {enabledCount}/{rules.length} active
          </span>
        }
        actions={
          <>
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="dash-btn-primary"
              style={{
                background: "var(--dash-warning)",
                boxShadow: "0 0 16px rgba(251,191,36,0.2)",
              }}
            >
              <Plus size={14} /> New Rule
            </button>
            <button onClick={fetchRules} className="dash-btn-ghost">
              <RefreshCw size={14} />
            </button>
          </>
        }
      />

      <div className="dash-page-content">
        {/* Create form */}
        {showCreate && (
          <GlassCard glow padding={18}>
            <SectionTitle>Create Automation Rule</SectionTitle>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Rule name"
                className="dash-input-ultron"
                style={{ width: "100%", boxSizing: "border-box" }}
              />
              <input
                value={trigger}
                onChange={(e) => setTrigger(e.target.value)}
                placeholder="Trigger (e.g. daily at 9am)"
                className="dash-input-ultron"
                style={{ width: "100%", boxSizing: "border-box" }}
              />
              <input
                value={action}
                onChange={(e) => setAction(e.target.value)}
                placeholder="Action (e.g. summarize tasks)"
                className="dash-input-ultron"
                style={{ width: "100%", boxSizing: "border-box" }}
              />
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button
                  onClick={() => setShowCreate(false)}
                  className="dash-btn-ghost"
                >
                  Cancel
                </button>
                <button onClick={createRule} className="dash-btn-primary">
                  <Zap size={12} /> Create Rule
                </button>
              </div>
            </div>
          </GlassCard>
        )}

        {/* Rules list */}
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
            <div>Loading rules...</div>
          </div>
        ) : rules.length === 0 ? (
          <EmptyState
            icon={<Zap size={28} style={{ color: "var(--dash-warning)" }} />}
            title="No automation rules"
            description="Create rules to automate repetitive tasks and workflows."
            action={
              <button
                onClick={() => setShowCreate(true)}
                className="dash-btn-primary"
                style={{
                  background: "var(--dash-warning)",
                  boxShadow: "0 0 16px rgba(251,191,36,0.2)",
                }}
              >
                <Plus size={14} /> Create Rule
              </button>
            }
          />
        ) : (
          <div className="dash-stagger">
            <SectionTitle count={rules.length}>Active Rules</SectionTitle>
            {rules.map((r) => (
              <GlassCard key={r.id} padding={0} className="dash-card-glow">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    padding: "14px 18px",
                  }}
                >
                  {/* Toggle */}
                  <button
                    onClick={() => toggleRule(r.id, r.enabled)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 0,
                      color: r.enabled
                        ? "var(--dash-warning)"
                        : "var(--dash-text-muted)",
                    }}
                  >
                    {r.enabled ? (
                      <ToggleRight size={24} />
                    ) : (
                      <ToggleLeft size={24} />
                    )}
                  </button>

                  {/* Rule info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: r.enabled
                          ? "var(--dash-text)"
                          : "var(--dash-text-secondary)",
                      }}
                    >
                      {r.name}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--dash-text-muted)",
                        fontFamily: "'JetBrains Mono', monospace",
                        marginTop: 3,
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <span style={{ color: "var(--dash-warning)" }}>
                        {r.trigger || "*"}
                      </span>
                      <span style={{ opacity: 0.4 }}>{">"}</span>
                      <span>{r.action || "*"}</span>
                    </div>
                  </div>

                  {/* Delete */}
                  <button
                    onClick={() => deleteRule(r.id)}
                    className="dash-btn-ghost"
                    style={{ padding: 6 }}
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

export default AutomationPage;
