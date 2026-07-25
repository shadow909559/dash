import { useEffect, useState, FormEvent } from "react";
import { automation as automationApi } from "@/lib/api";

interface Rule {
  id: string;
  name: string;
  trigger: string;
  action: string;
  enabled: boolean;
}

export default function Automation() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("");
  const [action, setAction] = useState("");

  useEffect(() => {
    loadRules();
  }, []);

  async function loadRules() {
    setIsLoading(true);
    try {
      const result = await automationApi.getRules();
      setRules(result);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !trigger.trim() || !action.trim()) return;
    try {
      await automationApi.createRule({ name: name.trim(), trigger: trigger.trim(), action: action.trim() });
      setName("");
      setTrigger("");
      setAction("");
      setShowCreate(false);
      loadRules();
    } catch {
      // ignore
    }
  }

  async function handleToggle(id: string, enabled: boolean) {
    try {
      await automationApi.toggleRule(id, enabled);
      setRules((prev) => prev.map((r) => (r.id === id ? { ...r, enabled } : r)));
    } catch {
      // ignore
    }
  }

  async function handleDelete(id: string) {
    try {
      await automationApi.deleteRule(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Automation</h2>
          <p className="page-subtitle">Manage automation rules and triggers</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          + New Rule
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="glass-card animate-fade-in" style={{ padding: 20, marginBottom: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            Create Automation Rule
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <input className="input" type="text" placeholder="Rule name" value={name} onChange={(e) => setName(e.target.value)} required />
            <input className="input" type="text" placeholder="Trigger (e.g., 'new_email')" value={trigger} onChange={(e) => setTrigger(e.target.value)} required />
            <input className="input" type="text" placeholder="Action (e.g., 'send_notification')" value={action} onChange={(e) => setAction(e.target.value)} required />
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn btn-primary">Create</button>
              <button type="button" className="btn" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </div>
        </form>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {isLoading && <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>Loading...</div>}
        {!isLoading && rules.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
            No automation rules yet
          </div>
        )}
        {!isLoading && rules.map((rule, i) => (
          <div key={rule.id} className="glass-card animate-fade-in" style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", animationDelay: `${i * 0.03}s` }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)" }}>{rule.name}</h3>
                <span className={`status-dot ${rule.enabled ? "online" : "offline"}`} />
              </div>
              <div style={{ display: "flex", gap: 16, fontSize: 13, color: "var(--text-secondary)" }}>
                <span>Trigger: <strong style={{ color: "var(--accent-secondary)" }}>{rule.trigger}</strong></span>
                <span>Action: <strong style={{ color: "var(--accent-secondary)" }}>{rule.action}</strong></span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className={`btn ${rule.enabled ? "btn-ghost" : "btn-primary"}`} onClick={() => handleToggle(rule.id, !rule.enabled)} style={{ fontSize: 12, padding: "6px 12px" }}>
                {rule.enabled ? "Disable" : "Enable"}
              </button>
              <button className="btn-ghost" onClick={() => handleDelete(rule.id)} style={{ fontSize: 12, padding: "6px 12px", color: "var(--danger)" }}>
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}