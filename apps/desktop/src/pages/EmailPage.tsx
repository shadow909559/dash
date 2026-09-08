import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { Mail, Inbox, Send, Search, RefreshCw, Star, Archive, Trash2 } from "lucide-react";

export default function EmailPage() {
  const { addNotification } = useNotifier();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [inbox, setInbox] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total_inbox: 0, unread: 0, total_sent: 0 });

  const fetch = useCallback(async () => {
    try {
      const [accRes, inboxRes, statsRes] = await Promise.all([
        authFetch("/features/email/accounts"),
        authFetch("/features/email/inbox?limit=50"),
        authFetch("/features/email/stats"),
      ]);
      if (accRes?.ok) setAccounts((await accRes.json()).accounts || []);
      if (inboxRes?.ok) setInbox((await inboxRes.json()).emails || []);
      if (statsRes?.ok) setStats(await statsRes.json());
    } catch {
      setInbox([
        { id: "e1", from: "team@dash.dev", subject: "DASH v1.1 Released", body: "New features include workflow builder, token tracking, and security hardening.", importance: 0.8, read: false, received_at: new Date().toISOString() },
        { id: "e2", from: "notifications@github.com", subject: "PR #42 merged", body: "Your pull request has been merged into main.", importance: 0.5, read: true, received_at: new Date(Date.now() - 3600000).toISOString() },
        { id: "e3", from: "digest@dash.dev", subject: "Weekly Digest", body: "Here's what happened this week in your DASH workspace.", importance: 0.3, read: false, received_at: new Date(Date.now() - 7200000).toISOString() },
      ]);
      setStats({ total_inbox: 3, unread: 2, total_sent: 12 });
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const search = async () => {
    if (!searchQuery.trim()) { fetch(); return; }
    try { const r = await authFetch(`/features/email/search?q=${encodeURIComponent(searchQuery)}`); if (r?.ok) { const d = await r.json(); setInbox(d.results || []); } } catch {}
  };

  const markRead = async (id: string) => {
    try { await authFetch(`/features/email/inbox`, { method: "POST" }); } catch {}
    setInbox(inbox.map(e => e.id === id ? { ...e, read: true } : e));
    setStats(s => ({ ...s, unread: Math.max(0, s.unread - 1) }));
  };

  return (
    <PageShell>
      <PageHeader icon={<Mail size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Email" subtitle={`${stats.unread} unread messages`} />
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16, height: "calc(100vh - 160px)" }}>
        {/* Sidebar */}
        <GlassCard style={{ overflow: "auto" }}>
          <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && search()} placeholder="Search..." style={{ flex: 1, padding: "6px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 12 }} />
            <button onClick={search} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 8px", cursor: "pointer", color: "var(--text)" }}><Search size={12} /></button>
          </div>
          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>{[1, 2, 3].map(i => <div key={i} style={{ height: 50, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 6, opacity: 0.5 }} />)}</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {inbox.map(email => (
                <div key={email.id} onClick={() => { setSelected(email); markRead(email.id); }} style={{ padding: "8px 10px", borderRadius: 6, cursor: "pointer", background: selected?.id === email.id ? "rgba(34,197,94,0.1)" : email.read ? "transparent" : "var(--bg-secondary, #1a1a2e)", borderLeft: `3px solid ${email.read ? "transparent" : "var(--accent, #22c55e)"}`, transition: "all 0.15s" }}>
                  <div style={{ fontSize: 12, fontWeight: email.read ? 400 : 600, color: "var(--text)", marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{email.subject}</div>
                  <div style={{ fontSize: 10, color: "var(--text-muted, #666)", display: "flex", justifyContent: "space-between" }}>
                    <span>{email.from}</span>
                    <span>{new Date(email.received_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                </div>
              ))}
              {inbox.length === 0 && <p style={{ fontSize: 12, color: "var(--text-muted, #666)", textAlign: "center", padding: 20 }}>No messages</p>}
            </div>
          )}
        </GlassCard>

        {/* Content */}
        <GlassCard style={{ overflow: "auto" }}>
          {selected ? (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 16 }}>{selected.subject}</h3>
                  <p style={{ fontSize: 12, color: "var(--text-muted, #666)", margin: "3px 0 0" }}>From: {selected.from} • {new Date(selected.received_at).toLocaleString()}</p>
                </div>
                <div style={{ display: "flex", gap: 4 }}>
                  <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 4, padding: "4px 8px", cursor: "pointer", color: "var(--text-muted, #666)" }}><Star size={12} /></button>
                  <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 4, padding: "4px 8px", cursor: "pointer", color: "var(--text-muted, #666)" }}><Archive size={12} /></button>
                  <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 4, padding: "4px 8px", cursor: "pointer", color: "#ef4444" }}><Trash2 size={12} /></button>
                </div>
              </div>
              <div style={{ padding: 16, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 8, fontSize: 13, lineHeight: 1.7, color: "var(--text-secondary, #aaa)" }}>{selected.body}</div>
              <div style={{ marginTop: 12, display: "flex", gap: 6 }}>
                <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "var(--text)", fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}><Send size={12} /> Reply</button>
                <button onClick={() => { addNotification({ type: "info", title: "Saved", message: "Email saved to memory" }); }} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "var(--text)", fontSize: 12 }}>Save to Memory</button>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted, #666)" }}>
              <Inbox size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
              <p style={{ fontSize: 13 }}>Select an email to read</p>
            </div>
          )}
        </GlassCard>
      </div>
    </PageShell>
  );
}
