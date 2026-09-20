import React, { useState, useEffect, useCallback, useRef } from "react";
import { authFetch } from "@/lib/api";
import { getWsClient } from "@/lib/wsClient";
import {
  Video,
  RefreshCw,
  Play,
  Square,
  FileText,
  AlertTriangle,
} from "lucide-react";
import {
  PageShell,
  PageHeader,
  EmptyState,
  GlassCard,
  SectionTitle,
  StatusIndicator,
} from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Meeting {
  id: string;
  title: string;
  client_id: string | null;
  project_id: string | null;
  scheduled_at: number | null;
  status: string; // scheduled | live | completed
  mode: string; // listen_only | assisted | authorized_participant
  transcript: { speaker: string; text: string; ts: number }[] | null;
  summary: {
    turns?: number;
    participants?: string[];
    counts?: Record<string, number>;
    needs_clarification?: string[];
    requirements_detected?: { text: string }[];
    decisions?: { text: string }[];
    questions?: { text: string }[];
    commitments_flagged?: { text: string }[];
  } | null;
  briefing: Record<string, unknown> | null;
  created_at: number;
}

function ts(n: number | null | undefined): string {
  return n ? new Date(n * 1000).toLocaleString() : "—";
}

const stateStyle: React.CSSProperties = {
  padding: "4px 10px",
  borderRadius: 999,
  fontSize: 10,
  fontWeight: 600,
  textTransform: "uppercase" as const,
};

function statusBadge(status: string) {
  const map: Record<string, React.CSSProperties> = {
    live: { background: "rgba(239,68,68,0.12)", color: "var(--dash-danger)", border: "1px solid rgba(239,68,68,0.3)" },
    completed: { background: "rgba(34,197,94,0.1)", color: "var(--dash-success)", border: "1px solid rgba(34,197,94,0.25)" },
    scheduled: { background: "rgba(59,130,246,0.1)", color: "var(--dash-accent)", border: "1px solid rgba(59,130,246,0.25)" },
  };
  return <span style={{ ...stateStyle, ...(map[status] || map.scheduled) }}>{status}</span>;
}

export const MeetingsPage: React.FC = () => {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selected, setSelected] = useState<Meeting | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState("");
  const wsBound = useRef(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/assistant/meetings`);
      if (r.ok) {
        const body = await r.json();
        setMeetings(body.meetings || []);
        setSelected((prev) =>
          prev ? (body.meetings || []).find((m: Meeting) => m.id === prev.id) || null : null
        );
      }
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Live refresh when meeting events or approvals change
  useEffect(() => {
    if (wsBound.current) return;
    const ws = getWsClient();
    const refresh = () => fetchAll();
    ws.on("meeting.alert", refresh);
    ws.on("proactive.digest", refresh);
    wsBound.current = true;
    return () => {
      ws.off("meeting.alert", refresh);
      ws.off("proactive.digest", refresh);
      wsBound.current = false;
    };
  }, [fetchAll]);

  const act = async (path: string, body?: unknown, done?: string) => {
    setBusy(true);
    try {
      const r = await authFetch(`${API}/assistant${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setFlash(data.detail || `Action failed (${r.status})`);
      } else if (done) {
        setFlash(done);
      }
    } catch (e) {
      setFlash("Action failed — see backend logs.");
    }
    setBusy(false);
    fetchAll();
  };

  return (
    <PageShell>
      <PageHeader
        icon={<Video size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        iconBg="rgba(59,130,246,0.12)"
        title="Meetings"
        subtitle="Briefings, live meeting assistance, and post-meeting records"
        actions={
          <button onClick={fetchAll} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {loading ? (
          <div style={{ textAlign: "center", padding: 48, color: "var(--dash-text-muted)" }}>
            <RefreshCw size={18} className="animate-rotate" style={{ marginBottom: 10 }} />
            <div>Loading meetings...</div>
          </div>
        ) : meetings.length === 0 ? (
          <EmptyState
            icon={<Video size={28} />}
            title="No meetings on record"
            description="Create one via POST /assistant/meetings or the chat command surface."
          />
        ) : (
          <>
            <SectionTitle>Meetings on record</SectionTitle>
            <div className="dash-stagger">
              {meetings.map((m) => (
                <GlassCard
                  key={m.id}
                  padding={12}
                  glow={m.status === "live"}
                >
                  <div
                    onClick={() => setSelected(m)}
                    style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
                  >
                    <StatusIndicator
                      status={m.status === "live" ? "offline" : m.status === "completed" ? "online" : "processing"}
                      label=""
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>
                        {m.title}
                      </div>
                      <div style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>
                        {ts(m.scheduled_at || m.created_at)} · {m.mode.replace(/_/g, " ")} ·
                        {" "}{(m.transcript || []).length} turn(s)
                      </div>
                    </div>
                    {statusBadge(m.status)}
                    {m.status === "scheduled" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); act(`/meetings/${m.id}/start`, { mode: "listen_only" }, "Meeting live — assistant listening."); }}
                        disabled={busy}
                        style={miniBtn}
                        title="Start live meeting in listen-only mode"
                      >
                        <Play size={11} /> Start
                      </button>
                    )}
                    {m.status === "live" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); act(`/meetings/${m.id}/end`, undefined, "Meeting ended — summary generated."); }}
                        disabled={busy}
                        style={miniBtn}
                        title="End meeting and generate summary"
                      >
                        <Square size={11} /> End
                      </button>
                    )}
                  </div>

                  {/* Detail panel (spec #124) */}
                  {selected?.id === m.id && (
                    <div style={{ marginTop: 12, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 12 }}>
                      {m.briefing && (
                        <>
                          <p style={labelStyle}><FileText size={11} /> Briefing</p>
                          <pre style={preStyle}>{JSON.stringify(m.briefing, null, 1).slice(0, 600)}</pre>
                        </>
                      )}
                      {(m.transcript || []).length > 0 && (
                        <>
                          <p style={labelStyle}>Transcript</p>
                          <div style={{ maxHeight: 220, overflowY: "auto", marginBottom: 8 }}>
                            {(m.transcript || []).map((t, i) => (
                              <div key={i} style={{ fontSize: 11, marginBottom: 4 }}>
                                <span style={{ color: "var(--dash-accent)", fontWeight: 600 }}>{t.speaker}:</span>{" "}
                                <span style={{ color: "var(--dash-text-secondary)" }}>{t.text}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                      {m.summary && (
                        <>
                          <p style={labelStyle}>Summary</p>
                          <div style={{ fontSize: 11, color: "var(--dash-text-secondary)", marginBottom: 6 }}>
                            {m.summary.turns ?? 0} turn(s) · {(m.summary.participants || []).join(", ") || "no participants"}
                            {m.summary.counts ? (
                              <> · {" "}
                                {Object.entries(m.summary.counts)
                                  .filter(([, n]) => n > 0)
                                  .map(([k, n]) => `${n} ${k}`)
                                  .join(", ")}
                              </>
                            ) : null}
                          </div>                          {(m.summary.needs_clarification ?? []).length > 0 && (
                            <div style={warnStyle}>
                              <AlertTriangle size={11} />
                              <span>
                                Clarification needed: {" "}
                                {(m.summary.needs_clarification ?? []).slice(0, 3).join(" · ")}
                              </span>
                            </div>
                          )}
                          {(m.summary.decisions || []).length > 0 && (
                            <>
                              <p style={labelStyle}>Decisions</p>
                              {(m.summary.decisions || []).map((d, i) => (
                                <div key={i} style={itemStyle}>{d.text}</div>
                              ))}
                            </>
                          )}
                          {(m.summary.commitments_flagged || []).length > 0 && (
                            <>
                              <p style={labelStyle}>Commitments flagged (not authorized)</p>
                              {(m.summary.commitments_flagged || []).map((c, i) => (
                                <div key={i} style={itemStyle}>{c.text}</div>
                              ))}
                            </>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </GlassCard>
              ))}
            </div>
            {flash ? (
              <GlassCard padding={10}>
                <p style={{ fontSize: 11, color: "var(--dash-text-secondary)", margin: 0 }}>{flash}</p>
              </GlassCard>
            ) : null}
          </>
        )}
      </div>
    </PageShell>
  );
};

const miniBtn: React.CSSProperties = {
  padding: "5px 10px",
  borderRadius: "var(--dash-radius-sm)",
  border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(255,255,255,0.04)",
  color: "var(--dash-text)",
  cursor: "pointer",
  fontSize: 11,
  display: "flex",
  alignItems: "center",
  gap: 4,
  flexShrink: 0,
};

const labelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: 0.5,
  color: "var(--dash-text-muted)",
  margin: "8px 0 4px",
  display: "flex",
  alignItems: "center",
  gap: 4,
};

const preStyle: React.CSSProperties = {
  fontSize: 10,
  background: "rgba(0,0,0,0.25)",
  borderRadius: 6,
  padding: 8,
  overflowX: "auto",
  color: "var(--dash-text-secondary)",
  margin: 0,
};

const itemStyle: React.CSSProperties = {
  fontSize: 11,
  color: "var(--dash-text-secondary)",
  marginBottom: 3,
};

const warnStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  fontSize: 11,
  color: "var(--dash-warning)",
  background: "rgba(234,179,8,0.08)",
  border: "1px solid rgba(234,179,8,0.2)",
  borderRadius: 6,
  padding: "6px 8px",
  marginBottom: 6,
};

export default MeetingsPage;
