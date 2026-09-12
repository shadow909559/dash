import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard, EmptyState, SectionTitle } from "@/components/ultron";
import { Plug, RefreshCw, Loader2, MessagesSquare, ArrowDownToLine, ArrowUpFromLine, Slack, Send, NotebookPen } from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface ConnectorStatus {
  service: string;
  enabled?: boolean;
  has_bot_token?: boolean;
  has_webhook_url?: boolean;
  has_signing_secret?: boolean;
  has_webhook_secret?: boolean;
  channel_id?: string;
  workspace_id?: string;
  configured_at?: string;
  messages?: number;
  rules?: { to_dash: boolean; from_dash: boolean };
}

interface ConnectorEvent {
  event: string;
  service: string;
  detail: string;
  at: string;
}

interface ConnectorMessage {
  id: string;
  channel: string;
  author: string;
  text: string;
  direction?: string;
  status?: string;
  at?: string;
  error?: string | null;
}

const SERVICE_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  slack: { label: "Slack", icon: <Slack size={16} />, color: "#4A154B" },
  telegram: { label: "Telegram", icon: <Send size={16} />, color: "#26A5E4" },
  notion: { label: "Notion", icon: <NotebookPen size={16} />, color: "#8f8f8f" },
};

export default function ConnectorsPage() {
  const { addNotification } = useNotifier();
  const [status, setStatus] = useState<ConnectorStatus[]>([]);
  const [events, setEvents] = useState<ConnectorEvent[]>([]);
  const [messages, setMessages] = useState<Record<string, ConnectorMessage[]>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [sRes, eRes] = await Promise.all([
        authFetch(`${API}/connectors/status`),
        authFetch(`${API}/connectors/events?limit=50`),
      ]);
      if (sRes?.ok) setStatus((await sRes.json()).connectors || []);
      if (eRes?.ok) setEvents((await eRes.json()).events || []);
      const configured = ((await sRes?.json().then((d) => d.connectors)) || []).filter(
        (c: ConnectorStatus) => c.has_bot_token || c.has_signing_secret || c.has_webhook_secret
      );
      const msgEntries = await Promise.all(
        configured.map(async (c: ConnectorStatus) => {
          const mRes = await authFetch(`${API}/connectors/messages/${c.service}?limit=25`);
          if (mRes?.ok) return [c.service, (await mRes.json()).messages || []] as const;
          return [c.service, []] as const;
        })
      );
      setMessages(Object.fromEntries(msgEntries));
    } catch {
      setStatus([]);
      setEvents([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const toggleRule = async (service: string, rule: "to_dash" | "from_dash", current: boolean) => {
    setToggling(`${service}:${rule}`);
    try {
      const res = await authFetch(`${API}/connectors/rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service, [rule]: !current }),
      });
      if (res?.ok) {
        addNotification({ title: "Rule updated", message: `${service} ${rule === "to_dash" ? "inbound→DASH" : "DASH→outbound"} ${!current ? "enabled" : "disabled"}`, type: "success" });
        await fetchAll();
      }
    } finally {
      setToggling(null);
    }
  };

  const refresh = () => { setRefreshing(true); fetchAll(); };

  return (
    <PageShell>
      <PageHeader
        icon={<Plug size={18} />}
        iconColor="var(--dash-accent)"
        title="Connectors"
        subtitle="Slack, Telegram, and Notion bridges with verified webhooks"
        actions={
          <button
            onClick={refresh}
            aria-label="Refresh connector status"
            style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text)", cursor: "pointer", fontSize: 12 }}
          >
            <RefreshCw size={13} className={refreshing ? "animate-spin" : undefined} /> Refresh
          </button>
        }
      />
      <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 24 }}>
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 60 }}><Loader2 size={22} className="animate-spin" /></div>
        ) : status.length === 0 ? (
          <EmptyState
            icon={<Plug size={28} />}
            title="No connectors configured"
            description="Configure Slack, Telegram, or Notion credentials via the backend to see live status here."
          />
        ) : (
          <>
            <section>
              <SectionTitle count={status.length}>Connected services</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
                {status.map((c) => {
                  const meta = SERVICE_META[c.service] || { label: c.service, icon: <Plug size={16} />, color: "var(--dash-accent)" };
                  const configured = !!(c.has_bot_token || c.has_signing_secret || c.has_webhook_secret);
                  return (
                    <GlassCard key={c.service} glow={configured}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                        <span style={{ color: meta.color, display: "flex" }}>{meta.icon}</span>
                        <strong style={{ fontSize: 14 }}>{meta.label}</strong>
                        <span style={{
                          marginLeft: "auto", fontSize: 10, padding: "2px 8px", borderRadius: 999,
                          border: "1px solid",
                          borderColor: configured ? "var(--dash-success)" : "var(--dash-border)",
                          color: configured ? "var(--dash-success)" : "var(--dash-text-muted)",
                        }}>
                          {configured ? "CONFIGURED" : "NOT CONFIGURED"}
                        </span>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 12 }}>
                        <span>Bot token: {c.has_bot_token ? "✓ stored" : "—"}</span>
                        <span>Webhook secret: {c.has_signing_secret || c.has_webhook_secret ? "✓ stored" : "—"}</span>
                        <span>Messages: {c.messages ?? 0}</span>
                        {c.channel_id ? <span>Channel: {c.channel_id}</span> : null}
                      </div>
                      <div style={{ display: "flex", gap: 8 }}>
                        {(["to_dash", "from_dash"] as const).map((rule) => {
                          const on = !!c.rules?.[rule];
                          const busy = toggling === `${c.service}:${rule}`;
                          return (
                            <button
                              key={rule}
                              onClick={() => toggleRule(c.service, rule, on)}
                              disabled={busy}
                              aria-pressed={on}
                              aria-label={`${meta.label} ${rule === "to_dash" ? "inbound" : "outbound"} forwarding ${on ? "on" : "off"}`}
                              style={{
                                flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
                                padding: "6px 8px", fontSize: 10, borderRadius: "var(--dash-radius-sm)", cursor: busy ? "wait" : "pointer",
                                border: "1px solid", borderColor: on ? "var(--dash-accent)" : "var(--dash-border)",
                                background: on ? "var(--dash-accent-glow)" : "transparent", color: on ? "var(--dash-accent)" : "var(--dash-text-muted)",
                              }}
                            >
                              {busy ? <Loader2 size={11} className="animate-spin" /> : rule === "to_dash" ? <ArrowDownToLine size={11} /> : <ArrowUpFromLine size={11} />}
                              {rule === "to_dash" ? "To DASH" : "From DASH"}
                            </button>
                          );
                        })}
                      </div>
                    </GlassCard>
                  );
                })}
              </div>
            </section>

            <section>
              <SectionTitle count={Object.values(messages).reduce((n, m) => n + m.length, 0)}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><MessagesSquare size={13} /> Recent messages</span>
              </SectionTitle>
              {Object.entries(messages).every(([, m]) => m.length === 0) ? (
                <div style={{ fontSize: 12, color: "var(--dash-text-muted)", padding: "8px 0" }}>No messages received yet. Inbound forwarding (To DASH) is off by default — enable it per service above.</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {Object.entries(messages).flatMap(([service, msgs]) =>
                    msgs.slice(-6).map((m) => (
                      <GlassCard key={m.id} padding={12}>
                        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                          <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: SERVICE_META[service]?.color, minWidth: 56, paddingTop: 2 }}>
                            {SERVICE_META[service]?.label?.toUpperCase() || service}
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 2 }}>
                              {m.author || "unknown"} → {m.channel || "dm"} {m.status ? `· ${m.status}` : ""}
                            </div>
                            <div style={{ fontSize: 12, overflowWrap: "anywhere" }}>{m.text || "(no text)"}</div>
                          </div>
                        </div>
                      </GlassCard>
                    ))
                  )}
                </div>
              )}
            </section>

            <section>
              <SectionTitle count={events.length}>Event log</SectionTitle>
              {events.length === 0 ? (
                <div style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>No connector events yet.</div>
              ) : (
                <GlassCard padding={0}>
                  <div style={{ maxHeight: 240, overflowY: "auto" }}>
                    {events.map((e, i) => (
                      <div key={i} style={{ display: "flex", gap: 10, padding: "8px 14px", fontSize: 11, borderBottom: "1px solid var(--dash-border)", fontFamily: "'JetBrains Mono', monospace" }}>
                        <span style={{ color: "var(--dash-text-muted)", minWidth: 140 }}>{(e.at || "").replace("T", " ").slice(0, 19)}</span>
                        <span style={{ color: "var(--dash-accent)", minWidth: 60 }}>{e.service}</span>
                        <span>{e.event}</span>
                        {e.detail ? <span style={{ color: "var(--dash-text-muted)" }}>{e.detail}</span> : null}
                      </div>
                    ))}
                  </div>
                </GlassCard>
              )}
            </section>
          </>
        )}
      </div>
    </PageShell>
  );
}
