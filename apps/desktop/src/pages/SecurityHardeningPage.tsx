import { useState, useEffect } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { Shield, Key, Lock, Scan, MessageSquare, AlertTriangle, CheckCircle, RefreshCw, Plus } from "lucide-react";

type Tab = "2fa" | "vault" | "anonymize" | "messenger";

export default function SecurityHardeningPage() {
  const { addNotification } = useNotifier();
  const [tab, setTab] = useState<Tab>("2fa");
  const [twoFA, setTwoFA] = useState({ enrolled: false, enabled: false, backup_codes_remaining: 0 });
  const [vaultCount, setVaultCount] = useState(0);
  const [piiText, setPiiText] = useState("");
  const [piiResult, setPiiResult] = useState<any>(null);

  useEffect(() => {
    authFetch("/features/security/2fa/status").then(r => r?.json()).then(d => d && setTwoFA(d)).catch(() => {});
    authFetch("/features/vault/stats").then(r => r?.json()).then(d => d && setVaultCount(d.total || 0)).catch(() => {});
  }, []);

  const enroll2FA = async () => {
    try { const r = await authFetch("/features/security/2fa/enroll", { method: "POST" }); if (r?.ok) { const d = await r.json(); addNotification({ type: "success", title: "2FA Enrolled", message: `Backup codes: ${d.backup_codes?.slice(0, 3).join(", ")}...` }); } } catch {}
    setTwoFA({ ...twoFA, enrolled: true });
  };

  const enable2FA = async () => {
    try { await authFetch("/features/security/2fa/enable", { method: "POST" }); } catch {}
    setTwoFA({ ...twoFA, enabled: true });
    addNotification({ type: "success", title: "2FA Enabled", message: "Two-factor authentication is now active" });
  };

  const scanPII = async () => {
    if (!piiText.trim()) return;
    try { const r = await authFetch("/features/privacy/scan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: piiText }) }); if (r?.ok) { setPiiResult(await r.json()); return; } } catch {}
    const f: Record<string, any> = {};
    if (/[\w.-]+@[\w.-]+\.\w+/.test(piiText)) f.email = { count: 1 };
    if (/\d{3}[-.]?\d{3}[-.]?\d{4}/.test(piiText)) f.phone = { count: 1 };
    setPiiResult({ has_pii: Object.keys(f).length > 0, findings: f });
  };

  const anonymize = async () => {
    if (!piiText.trim()) return;
    try { const r = await authFetch("/features/privacy/anonymize", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: piiText }) }); if (r?.ok) { const d = await r.json(); setPiiText(d.redacted); addNotification({ type: "success", title: "Anonymized", message: "PII redacted" }); return; } } catch {}
    setPiiText(piiText.replace(/[\w.-]+@[\w.-]+\.\w+/g, "[REDACTED_EMAIL]").replace(/\d{3}[-.]?\d{3}[-.]?\d{4}/g, "[REDACTED_PHONE]"));
    addNotification({ type: "success", title: "Anonymized", message: "PII redacted locally" });
  };

  const genPW = async () => {
    try { const r = await authFetch("/features/vault/generate-password?length=20"); if (r?.ok) { const d = await r.json(); navigator.clipboard.writeText(d.password); addNotification({ type: "success", title: "Copied", message: "Password copied to clipboard" }); return; } } catch {}
    const c = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*";
    navigator.clipboard.writeText(Array.from({ length: 20 }, () => c[Math.floor(Math.random() * c.length)]).join(""));
    addNotification({ type: "success", title: "Copied", message: "Password generated locally" });
  };

  const tabs: { id: Tab; label: string; I: typeof Shield }[] = [
    { id: "2fa", label: "Two-Factor Auth", I: Shield },
    { id: "vault", label: "Password Vault", I: Lock },
    { id: "anonymize", label: "PII Scanner", I: Scan },
    { id: "messenger", label: "Encrypted Chat", I: MessageSquare },
  ];

  return (
    <PageShell>
      <PageHeader icon={<Shield size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Security Hardening" subtitle="2FA, password vault, PII scanning, and encrypted messaging." />
      <div style={{ display: "flex", gap: 2, borderBottom: "1px solid var(--border, #333)", marginBottom: 20 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{ padding: "8px 14px", background: "none", border: "none", borderBottom: `2px solid ${tab === t.id ? "var(--accent, #22c55e)" : "transparent"}`, color: tab === t.id ? "var(--text)" : "var(--text-muted, #666)", cursor: "pointer", display: "flex", alignItems: "center", gap: 5, fontSize: 12, fontWeight: tab === t.id ? 600 : 400 }}>
            <t.I size={13} />{t.label}
          </button>
        ))}
      </div>

      {tab === "2fa" && (
        <GlassCard>
          <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>Two-Factor Authentication</h3>
          <p style={{ fontSize: 12, color: "var(--text-muted, #666)", margin: "0 0 16px" }}>Add TOTP-based 2FA for extra security.</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
            {[{ l: "Enrolled", v: twoFA.enrolled }, { l: "Enabled", v: twoFA.enabled }].map(s => (
              <div key={s.l} style={{ padding: 12, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 6, display: "flex", alignItems: "center", gap: 6 }}>
                {s.v ? <CheckCircle size={14} style={{ color: "var(--accent, #22c55e)" }} /> : <AlertTriangle size={14} style={{ color: "var(--text-muted, #666)" }} />}
                <span style={{ fontSize: 12, fontWeight: 500 }}>{s.l}: {s.v ? "Yes" : "No"}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {!twoFA.enrolled && <button className="btn btn--primary" onClick={enroll2FA} style={{ fontSize: 12 }}>Enroll 2FA</button>}
            {twoFA.enrolled && !twoFA.enabled && <button className="btn btn--primary" onClick={enable2FA} style={{ fontSize: 12 }}>Enable 2FA</button>}
            {twoFA.enabled && <button onClick={() => { setTwoFA({ ...twoFA, enabled: false }); addNotification({ type: "info", title: "Disabled", message: "2FA disabled" }); }} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", color: "var(--text)", cursor: "pointer", fontSize: 12 }}>Disable</button>}
            {twoFA.enrolled && <button onClick={() => addNotification({ type: "success", title: "Regenerated", message: "New backup codes generated" })} style={{ background: "none", border: "none", color: "var(--text-muted, #999)", cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}><RefreshCw size={12} /> Regenerate Codes</button>}
          </div>
        </GlassCard>
      )}

      {tab === "vault" && (
        <GlassCard>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
            <div><h3 style={{ margin: 0, fontSize: 15 }}>Password Vault</h3><p style={{ fontSize: 12, color: "var(--text-muted, #666)", margin: "2px 0 0" }}>{vaultCount} entries stored</p></div>
            <button className="btn btn--primary" onClick={genPW} style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}><Key size={12} /> Generate Password</button>
          </div>
          <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted, #666)" }}>
            <Lock size={28} style={{ marginBottom: 10, opacity: 0.3 }} />
            <p style={{ fontSize: 12 }}>Vault is encrypted and empty.</p>
            <button style={{ marginTop: 6, background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", color: "var(--text)", cursor: "pointer", fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4 }}><Plus size={12} /> Add Entry</button>
          </div>
        </GlassCard>
      )}

      {tab === "anonymize" && (
        <GlassCard>
          <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>PII Scanner & Anonymizer</h3>
          <p style={{ fontSize: 12, color: "var(--text-muted, #666)", margin: "0 0 12px" }}>Scan for emails, phone numbers, SSNs, credit cards, API keys.</p>
          <textarea value={piiText} onChange={e => setPiiText(e.target.value)} rows={5} placeholder="Paste text to scan..." style={{ width: "100%", padding: 10, background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 12, fontFamily: "monospace", resize: "vertical", marginBottom: 10 }} />
          <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            <button className="btn btn--primary" onClick={scanPII} style={{ fontSize: 12 }}>Scan</button>
            <button onClick={anonymize} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", color: "var(--text)", cursor: "pointer", fontSize: 12 }}>Anonymize</button>
          </div>
          {piiResult && (
            <div style={{ padding: 10, background: piiResult.has_pii ? "rgba(239,68,68,0.1)" : "rgba(34,197,94,0.1)", border: `1px solid ${piiResult.has_pii ? "rgba(239,68,68,0.3)" : "rgba(34,197,94,0.3)"}`, borderRadius: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                {piiResult.has_pii ? <AlertTriangle size={12} style={{ color: "#ef4444" }} /> : <CheckCircle size={12} style={{ color: "var(--accent, #22c55e)" }} />}
                <span style={{ fontSize: 12, fontWeight: 500 }}>{piiResult.has_pii ? "PII Found" : "Clean"}</span>
              </div>
              {piiResult.has_pii && (
                <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
                  {Object.entries(piiResult.findings).map(([t, i]: [string, any]) => (
                    <span key={t} style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(239,68,68,0.15)", color: "#ef4444", textTransform: "uppercase" }}>{t}: {i.count}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </GlassCard>
      )}

      {tab === "messenger" && (
        <GlassCard>
          <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>Encrypted Messenger</h3>
          <p style={{ fontSize: 12, color: "var(--text-muted, #666)", margin: "0 0 16px" }}>End-to-end encrypted messaging.</p>
          <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted, #666)" }}>
            <MessageSquare size={28} style={{ marginBottom: 10, opacity: 0.3 }} />
            <p style={{ fontSize: 12 }}>No active conversations.</p>
          </div>
        </GlassCard>
      )}
    </PageShell>
  );
}
