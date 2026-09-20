import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import {
  Users,
  Building2,
  UserPlus,
  ChevronRight,
  ChevronLeft,
  RefreshCw,
  MessageSquare,
  FolderKanban,
  ListChecks,
  CalendarDays,
  History,
  User,
} from "lucide-react";
import {
  PageShell,
  PageHeader,
  EmptyState,
  GlassCard,
  SectionTitle,
} from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface ClientRow {
  id: string;
  name: string;
  organization: string;
  priority: string;
  notes: string;
}

interface Contact {
  id: string;
  name: string;
  role: string;
  email: string;
  phone: string;
}

interface Project {
  id: string;
  name: string;
  goals: string;
  deadline?: string | null;
}

interface Requirement {
  id: string;
  text: string;
  status: string;
  confidence: number;
  task_ids?: string[];
}

interface Communication {
  id: string;
  direction: string;
  channel: string;
  summary: string;
  sent: boolean;
  created_at: number;
}

interface TimelineEvent {
  ts: number;
  type: string;
  text: string;
  status: string;
  id: string;
}

interface ClientDetail {
  client: ClientRow;
  contacts: Contact[];
  projects: Project[];
  requirements: Requirement[];
  communications: Communication[];
  meetings: unknown[];
}

const PRIORITY_COLOR: Record<string, string> = {
  high: "var(--dash-danger)",
  normal: "var(--dash-accent)",
  low: "var(--dash-text-muted)",
};

const REQ_STATUS_COLOR: Record<string, string> = {
  confirmed: "var(--dash-success)",
  approved: "var(--dash-success)",
  planned: "var(--dash-accent)",
  in_progress: "var(--dash-accent)",
  implemented: "var(--dash-accent)",
  verified: "var(--dash-success)",
  delivered: "var(--dash-success)",
  clarification_needed: "var(--dash-warning)",
  detected: "var(--dash-text-muted)",
  requested: "var(--dash-text-muted)",
  rejected: "var(--dash-danger)",
  dropped: "var(--dash-text-muted)",
};

const TIMELINE_ICON: Record<string, React.ReactNode> = {
  requirement: <ListChecks size={12} />,
  requirement_status: <ListChecks size={12} />,
  meeting: <CalendarDays size={12} />,
  communication: <MessageSquare size={12} />,
  follow_up: <History size={12} />,
};

function ts(n: number): string {
  return n ? new Date(n * 1000).toLocaleString() : "—";
}

export const ClientsPage: React.FC = () => {
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newOrg, setNewOrg] = useState("");
  const [newPriority, setNewPriority] = useState("normal");
  const [error, setError] = useState("");

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/assistant/clients`);
      const data = await r.json();
      setClients(data.clients || []);
    } catch {}
    setLoading(false);
  }, []);

  const fetchDetail = useCallback(async (name: string) => {
    setDetailLoading(true);
    try {
      const [d, t] = await Promise.all([
        authFetch(`${API}/assistant/clients/${encodeURIComponent(name)}`),
        authFetch(`${API}/assistant/clients/${encodeURIComponent(name)}/timeline`),
      ]);
      if (d.ok) setDetail(await d.json());
      else setDetail(null);
      if (t.ok) setTimeline((await t.json()).timeline || []);
    } catch {}
    setDetailLoading(false);
  }, []);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  useEffect(() => {
    if (selected) fetchDetail(selected);
    else {
      setDetail(null);
      setTimeline([]);
    }
  }, [selected, fetchDetail]);

  const createClient = async () => {
    if (!newName.trim()) return;
    setError("");
    try {
      const r = await authFetch(`${API}/assistant/clients`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newName.trim(),
          organization: newOrg.trim() || newName.trim(),
          priority: newPriority,
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(body.detail || `Failed (${r.status})`);
        return;
      }
      setNewName("");
      setNewOrg("");
      setShowCreate(false);
      fetchClients();
    } catch {
      setError("Network error");
    }
  };

  return (
    <PageShell glowColor="rgba(63, 169, 245, 0.05)">
      <PageHeader
        icon={<Users size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        iconBg="rgba(63,169,245,0.12)"
        title={selected ? selected : "Clients"}
        subtitle={
          selected
            ? "Client intelligence — grounded in stored records"
            : "Client management — every answer from structured records"
        }
        badge={
          clients.length > 0 && !selected ? (
            <span className="dash-badge-glow" style={{
              background: "rgba(63,169,245,0.12)",
              color: "var(--dash-accent)",
              border: "1px solid rgba(63,169,245,0.25)",
            }}>
              {clients.length}
            </span>
          ) : undefined
        }
        actions={
          <>
            {selected ? (
              <button
                onClick={() => setSelected(null)}
                className="dash-btn-ghost"
                title="Back to list"
              >
                <ChevronLeft size={14} /> All clients
              </button>
            ) : (
              <button
                onClick={() => setShowCreate((v) => !v)}
                className="dash-btn-ghost"
                title="New client"
              >
                <UserPlus size={14} />
              </button>
            )}
            <button
              onClick={() => (selected ? fetchDetail(selected) : fetchClients())}
              className="dash-btn-ghost"
            >
              <RefreshCw size={14} />
            </button>
          </>
        }
      />

      <div className="dash-page-content">
        {/* Create form */}
        {showCreate && !selected ? (
          <GlassCard padding={16} className="animate-slide-up">
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Client name"
                style={inputStyle}
              />
              <input
                value={newOrg}
                onChange={(e) => setNewOrg(e.target.value)}
                placeholder="Organization (optional)"
                style={inputStyle}
              />
              <select
                value={newPriority}
                onChange={(e) => setNewPriority(e.target.value)}
                style={inputStyle}
              >
                <option value="high">high</option>
                <option value="normal">normal</option>
                <option value="low">low</option>
              </select>
              <button onClick={createClient} style={primaryBtnStyle}>
                Create
              </button>
              {error ? (
                <span style={{ fontSize: 11, color: "var(--dash-danger)" }}>{error}</span>
              ) : null}
            </div>
          </GlassCard>
        ) : null}

        {/* List view */}
        {!selected ? (
          loading ? (
            <div style={{ textAlign: "center", padding: 48, color: "var(--dash-text-muted)" }}>
              <RefreshCw size={18} className="animate-rotate" style={{ marginBottom: 10 }} />
              <div>Loading clients...</div>
            </div>
          ) : clients.length === 0 ? (
            <EmptyState
              icon={<Users size={28} style={{ color: "var(--dash-text-muted)" }} />}
              title="No clients yet"
              description="Add your first client to start tracking requirements, meetings and communication."
            />
          ) : (
            <div className="dash-stagger">
              {clients.map((c) => (
                <GlassCard
                  key={c.id}
                  padding={0}
                  className="animate-slide-up"
                >
                  <div
                    onClick={() => setSelected(c.name)}
                    style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 20px", cursor: "pointer" }}>
                    <Building2 size={16} style={{ color: "var(--dash-text-muted)", flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--dash-text)" }}>
                        {c.name}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 2 }}>
                        {c.organization !== c.name ? c.organization : "—"}
                      </div>
                    </div>
                    <span className="dash-badge-glow" style={{
                      background: "rgba(255,255,255,0.04)",
                      color: PRIORITY_COLOR[c.priority] || "var(--dash-accent)",
                      border: "1px solid rgba(255,255,255,0.08)",
                    }}>
                      {c.priority}
                    </span>
                    <ChevronRight size={15} style={{ color: "var(--dash-text-muted)" }} />
                  </div>
                </GlassCard>
              ))}
            </div>
          )
        ) : detailLoading ? (
          <div style={{ textAlign: "center", padding: 48, color: "var(--dash-text-muted)" }}>
            <RefreshCw size={18} className="animate-rotate" style={{ marginBottom: 10 }} />
            <div>Loading client...</div>
          </div>
        ) : !detail ? (
          <EmptyState
            icon={<Users size={28} style={{ color: "var(--dash-text-muted)" }} />}
            title="Client not found"
            description="The record may have been removed."
          />
        ) : (
          <>
            {/* Contacts */}
            <SectionTitle>Contacts</SectionTitle>
            {detail.contacts.length === 0 ? (
              <p style={mutedText}>No contacts recorded.</p>
            ) : (
              <div className="dash-stagger">
                {detail.contacts.map((ct) => (
                  <GlassCard key={ct.id} padding={12}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <User size={13} style={{ color: "var(--dash-accent)" }} />
                      <span style={{ fontSize: 13, color: "var(--dash-text)", fontWeight: 600 }}>
                        {ct.name}
                      </span>
                      {ct.role ? (
                        <span style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>{ct.role}</span>
                      ) : null}
                      {ct.email ? (
                        <span style={{ fontSize: 11, color: "var(--dash-text-muted)", marginLeft: "auto" }}>
                          {ct.email}
                        </span>
                      ) : null}
                    </div>
                  </GlassCard>
                ))}
              </div>
            )}

            {/* Projects */}
            <SectionTitle>Projects</SectionTitle>
            {detail.projects.length === 0 ? (
              <p style={mutedText}>No projects yet.</p>
            ) : (
              <div className="dash-stagger">
                {detail.projects.map((p) => (
                  <GlassCard key={p.id} padding={12}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <FolderKanban size={13} style={{ color: "var(--dash-accent)" }} />
                      <span style={{ fontSize: 13, color: "var(--dash-text)", fontWeight: 600 }}>
                        {p.name}
                      </span>
                      {p.deadline ? (
                        <span style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>
                          due {p.deadline}
                        </span>
                      ) : null}
                    </div>
                    {p.goals ? (
                      <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: "6px 0 0" }}>
                        {p.goals}
                      </p>
                    ) : null}
                  </GlassCard>
                ))}
              </div>
            )}

            {/* Requirements */}
            <SectionTitle>Requirements</SectionTitle>
            {detail.requirements.length === 0 ? (
              <p style={mutedText}>No requirements recorded.</p>
            ) : (
              <div className="dash-stagger">
                {detail.requirements.map((r) => (
                  <GlassCard key={r.id} padding={12}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
                      <span style={{ fontSize: 12, color: "var(--dash-text)" }}>{r.text}</span>
                      <span className="dash-badge-glow" style={{
                        background: "rgba(255,255,255,0.04)",
                        color: REQ_STATUS_COLOR[r.status] || "var(--dash-accent)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        flexShrink: 0,
                      }}>
                        {r.status}
                      </span>
                    </div>
                    <div style={{ fontSize: 10, color: "var(--dash-text-muted)", marginTop: 4 }}>
                      confidence {r.confidence}
                      {r.task_ids?.length ? ` · ${r.task_ids.length} linked task(s)` : ""}
                    </div>
                  </GlassCard>
                ))}
              </div>
            )}

            {/* Recent communications */}
            <SectionTitle>Recent communications</SectionTitle>
            {detail.communications.length === 0 ? (
              <p style={mutedText}>No communication on record.</p>
            ) : (
              <div className="dash-stagger">
                {detail.communications.slice(-5).reverse().map((c) => (
                  <GlassCard key={c.id} padding={12}>
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <MessageSquare size={12} style={{
                        color: c.direction === "outgoing" ? "var(--dash-accent)" : "var(--dash-success)",
                        flexShrink: 0,
                      }} />
                      <span style={{ fontSize: 12, color: "var(--dash-text)", flex: 1 }}>
                        {c.summary}
                      </span>
                      <span style={{ fontSize: 10, color: "var(--dash-text-muted)", flexShrink: 0 }}>
                        {ts(c.created_at)}
                      </span>
                      <span className="dash-badge-glow" style={{
                        background: "rgba(255,255,255,0.04)",
                        color: c.sent ? "var(--dash-success)" : "var(--dash-warning)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        flexShrink: 0,
                      }}>
                        {c.sent ? "delivered" : "recorded"}
                      </span>
                    </div>
                  </GlassCard>
                ))}
              </div>
            )}

            {/* Timeline */}
            <SectionTitle>Timeline</SectionTitle>
            {timeline.length === 0 ? (
              <p style={mutedText}>No events on record.</p>
            ) : (
              <GlassCard padding={16}>
                {timeline.map((e, i) => (
                  <div
                    key={`${e.type}-${e.id}-${i}`}
                    style={{
                      display: "flex",
                      gap: 10,
                      alignItems: "flex-start",
                      padding: "6px 0",
                      borderBottom: i < timeline.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
                    }}
                  >
                    <span style={{ color: "var(--dash-text-muted)", marginTop: 2, flexShrink: 0 }}>
                      {TIMELINE_ICON[e.type] || <History size={12} />}
                    </span>
                    <span style={{ fontSize: 12, color: "var(--dash-text)", flex: 1 }}>
                      {e.text}
                    </span>
                    <span style={{ fontSize: 10, color: "var(--dash-text-muted)", flexShrink: 0 }}>
                      {ts(e.ts)}
                    </span>
                  </div>
                ))}
              </GlassCard>
            )}
          </>
        )}
      </div>
    </PageShell>
  );
};

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: "var(--dash-radius-sm)",
  border: "1px solid rgba(255,255,255,0.08)",
  background: "rgba(255,255,255,0.03)",
  color: "var(--dash-text)",
  fontSize: 12,
  outline: "none",
};

const primaryBtnStyle: React.CSSProperties = {
  padding: "8px 16px",
  borderRadius: "var(--dash-radius-sm)",
  border: "none",
  background: "var(--dash-accent)",
  color: "white",
  cursor: "pointer",
  fontSize: 12,
  fontWeight: 600,
};

const mutedText: React.CSSProperties = {
  fontSize: 12,
  color: "var(--dash-text-muted)",
  margin: "4px 0 10px",
};

export default ClientsPage;
