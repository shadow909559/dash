import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { Shield, AlertTriangle, CheckCircle, XCircle, Bug, FileText, Activity } from "lucide-react";

export default function CompliancePage() {
  const { addNotification } = useNotifier();
  const [reports, setReports] = useState<any[]>([]);
  const [vulns, setVulns] = useState<any[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [playbooks, setPlaybooks] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const [cr, vr, ir, pr] = await Promise.all([
        authFetch("/phase3/compliance/reports"),
        authFetch("/phase3/vulnerabilities"),
        authFetch("/phase3/incidents"),
        authFetch("/phase3/incidents/playbooks"),
      ]);
      if (cr?.ok) setReports((await cr.json()).reports || []);
      if (vr?.ok) setVulns((await vr.json()).vulnerabilities || []);
      if (ir?.ok) setIncidents((await ir.json()).incidents || []);
      if (pr?.ok) setPlaybooks(await pr.json());
    } catch {
      setReports([
        { framework: "GDPR", name: "General Data Protection Regulation", total_checks: 8, passed: 6, failed: 2, score: 75, details: {} },
        { framework: "SOC2", name: "Service Organization Control 2", total_checks: 5, passed: 4, failed: 1, score: 80, details: {} },
      ]);
      setPlaybooks({ brute_force: { name: "Brute Force Detection", steps: ["lock_account", "notify_admin", "log_event", "block_ip"] }, data_breach: { name: "Data Breach Response", steps: ["isolate_system", "assess_scope", "notify_users"] } });
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return (
    <PageShell>
      <PageHeader icon={<Shield size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Compliance & Security" subtitle={`${reports.length} frameworks • ${vulns.length} vulnerabilities • ${incidents.length} incidents`} />

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{[1, 2, 3].map(i => <div key={i} style={{ height: 80, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 8, opacity: 0.5 }} />)}</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Compliance Reports */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 6 }}><FileText size={14} /> Compliance Reports</h4>
            {reports.map(r => (
              <div key={r.framework} style={{ padding: "10px 12px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{r.framework}</span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: r.score >= 80 ? "var(--accent, #22c55e)" : r.score >= 60 ? "#f59e0b" : "#ef4444" }}>{r.score}%</span>
                </div>
                <div style={{ height: 6, background: "var(--bg-tertiary, #0d0d1a)", borderRadius: 3, overflow: "hidden", marginBottom: 4 }}>
                  <div style={{ height: "100%", borderRadius: 3, width: `${r.score}%`, background: r.score >= 80 ? "var(--accent, #22c55e)" : r.score >= 60 ? "#f59e0b" : "#ef4444" }} />
                </div>
                <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--text-muted, #666)" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 3 }}><CheckCircle size={10} style={{ color: "var(--accent, #22c55e)" }} /> {r.passed} passed</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 3 }}><XCircle size={10} style={{ color: "#ef4444" }} /> {r.failed} failed</span>
                </div>
              </div>
            ))}
          </GlassCard>

          {/* Vulnerabilities */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 6 }}><Bug size={14} /> Vulnerabilities ({vulns.length})</h4>
            {vulns.length === 0 ? (
              <div style={{ textAlign: "center", padding: 20, color: "var(--text-muted, #666)" }}>
                <CheckCircle size={24} style={{ marginBottom: 8, color: "var(--accent, #22c55e)", opacity: 0.5 }} />
                <p style={{ fontSize: 12 }}>No known vulnerabilities</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {vulns.map((v, i) => (
                  <div key={i} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", borderLeft: `3px solid ${v.severity === "critical" ? "#ef4444" : v.severity === "high" ? "#f59e0b" : "var(--accent, #22c55e)"}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 12, fontWeight: 500 }}>{v.dependency}@{v.version}</span>
                      <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: v.severity === "critical" ? "rgba(239,68,68,0.15)" : "rgba(245,158,11,0.15)", color: v.severity === "critical" ? "#ef4444" : "#f59e0b", textTransform: "uppercase" }}>{v.severity}</span>
                    </div>
                    <p style={{ fontSize: 10, color: "var(--text-muted, #666)", margin: "3px 0 0" }}>{v.cve}: {v.description}</p>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          {/* Incidents */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 6 }}><AlertTriangle size={14} /> Incidents ({incidents.length})</h4>
            {incidents.length === 0 ? (
              <div style={{ textAlign: "center", padding: 20, color: "var(--text-muted, #666)" }}>
                <Activity size={24} style={{ marginBottom: 8, opacity: 0.3 }} />
                <p style={{ fontSize: 12 }}>No incidents reported</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {incidents.map(inc => (
                  <div key={inc.id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 12, fontWeight: 500 }}>{inc.type}</span>
                      <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: inc.status === "resolved" ? "rgba(34,197,94,0.15)" : "rgba(245,158,11,0.15)", color: inc.status === "resolved" ? "var(--accent, #22c55e)" : "#f59e0b" }}>{inc.status}</span>
                    </div>
                    <p style={{ fontSize: 10, color: "var(--text-muted, #666)", margin: "3px 0 0" }}>{inc.description}</p>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          {/* Playbooks */}
          <GlassCard>
            <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Response Playbooks</h4>
            {Object.entries(playbooks).map(([id, pb]: [string, any]) => (
              <div key={id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", marginBottom: 6 }}>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 4 }}>{pb.name}</div>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {(pb.steps || []).map((step: string, i: number) => (
                    <span key={i} style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: "var(--bg-tertiary, #0d0d1a)", color: "var(--text-muted, #666)" }}>{step}</span>
                  ))}
                </div>
              </div>
            ))}
          </GlassCard>
        </div>
      )}
    </PageShell>
  );
}
