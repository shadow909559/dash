import React, { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Clock,
  AlertTriangle,
  Target,
  Bell,
  Cpu,
  HardDrive,
  Monitor,
  ChevronRight,
  RefreshCw,
  Loader2,
  Plus,
  X,
  Check,
} from "lucide-react";
import { useAIStore } from "@/stores/aiStore";
import { authFetch, commandCenter } from "@/lib/api";
import type {
  UpcomingItem,
  PredictiveRisk,
  ProactiveSuggestion,
} from "@/lib/api";
import { LiveRegion } from "@/components/LiveRegion";

const API =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

/* --------------------------------------------------------------------------- */
/* Types                                                                       */
/* --------------------------------------------------------------------------- */

interface BriefingData {
  date?: string;
  system?: string;
  project?: string;
  deadlines?: string;
  trends?: string;
  predictions?: string;
  briefings?: string;
  attention?: string;
}

/* --------------------------------------------------------------------------- */
/* Helpers                                                                     */
/* --------------------------------------------------------------------------- */

function severityColor(s: number): string {
  if (s >= 0.8) return "var(--dash-danger)";
  if (s >= 0.6) return "var(--dash-warning)";
  return "var(--dash-accent)";
}

function severityLabel(s: number): string {
  if (s >= 0.8) return "HIGH";
  if (s >= 0.6) return "MED";
  return "LOW";
}

function deadlineRelative(dateStr: string | null): string {
  if (!dateStr) return "No date";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`;
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  return `${diffDays}d`;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

/* --------------------------------------------------------------------------- */
/* Sub-components                                                              */
/* --------------------------------------------------------------------------- */

function PanelHeader({
  icon: Icon,
  label,
  count,
  accentColor,
}: {
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
  label: string;
  count?: number;
  accentColor?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 12,
      }}
    >
      <Icon size={14} style={{ color: accentColor || "var(--dash-accent)" }} />
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "var(--dash-text-secondary)",
        }}
      >
        {label}
      </span>
      {count !== undefined && count > 0 && (
        <span
          style={{
            fontSize: 10,
            padding: "1px 6px",
            borderRadius: "var(--dash-radius-full)",
            backgroundColor: "rgba(63,169,245,0.12)",
            color: "var(--dash-accent)",
            fontFamily: "'JetBrains Mono', monospace",
            marginLeft: "auto",
          }}
        >
          {count}
        </span>
      )}
    </div>
  );
}

function LoadingPlaceholder({ text }: { text: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        gap: 8,
      }}
    >
      <Loader2
        size={14}
        style={{
          color: "var(--dash-text-muted)",
          animation: "spin 1s linear infinite",
        }}
      />
      <span
        style={{
          fontSize: 11,
          color: "var(--dash-text-muted)",
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >
        {text}
      </span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div
      style={{
        padding: 16,
        textAlign: "center",
      }}
    >
      <span
        style={{
          fontSize: 11,
          color: "var(--dash-text-muted)",
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >
        {text}
      </span>
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* Quick Goal Form                                                             */
/* --------------------------------------------------------------------------- */

function QuickGoalForm({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [priority, setPriority] = useState(3);
  const [deadline, setDeadline] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || submitting) return;
    setSubmitting(true);
    try {
      await commandCenter.createGoal(name.trim(), {
        priority,
        deadline: deadline || undefined,
      });
      onCreated();
    } catch {
      // ignore; form stays open
    }
    setSubmitting(false);
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        padding: "12px 14px",
        borderRadius: "var(--dash-radius-sm)",
        background: "var(--dash-bg-subtle)",
        border: "1px solid var(--dash-border-accent)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 2,
        }}
      >
        <Plus size={13} style={{ color: "var(--dash-accent)" }} />
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "var(--dash-text)",
          }}
        >
          New Goal
        </span>
      </div>

      <input
        ref={inputRef}
        value={name}
        onChange={(e) => setName(e.target.value)}
        aria-label="Goal name"
        placeholder="Goal name..."
        disabled={submitting}
        style={{
          background: "var(--dash-surface)",
          border: "1px solid var(--dash-border)",
          borderRadius: "var(--dash-radius-sm)",
          padding: "6px 10px",
          fontSize: 12,
          color: "var(--dash-text)",
          /* a11y: focus ring from global :focus-visible */
        }}
      />

      <div style={{ display: "flex", gap: 8 }}>
        <div style={{ flex: 1 }}>
          <label
            htmlFor="cc-priority"
            style={{
              fontSize: 9,
              color: "var(--dash-text-muted)",
              display: "block",
              marginBottom: 2,
            }}
          >
            Priority (1=high, 5=low)
          </label>
          <select
            id="cc-priority"
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            style={{
              width: "100%",
              background: "var(--dash-surface)",
              border: "1px solid var(--dash-border)",
              borderRadius: "var(--dash-radius-sm)",
              padding: "5px 8px",
              fontSize: 11,
              color: "var(--dash-text)",
            }}
          >
            <option value={1}>1 - Critical</option>
            <option value={2}>2 - High</option>
            <option value={3}>3 - Medium</option>
            <option value={4}>4 - Low</option>
            <option value={5}>5 - Nice to have</option>
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label
            htmlFor="cc-deadline"
            style={{
              fontSize: 9,
              color: "var(--dash-text-muted)",
              display: "block",
              marginBottom: 2,
            }}
          >
            Deadline (optional)
          </label>
          <input
            id="cc-deadline"
            aria-label="Deadline date"
            type="date"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            style={{
              width: "100%",
              background: "var(--dash-surface)",
              border: "1px solid var(--dash-border)",
              borderRadius: "var(--dash-radius-sm)",
              padding: "5px 8px",
              fontSize: 11,
              color: "var(--dash-text)",
            }}
          />
        </div>
      </div>

      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          style={{
            padding: "4px 10px",
            fontSize: 11,
            borderRadius: "var(--dash-radius-sm)",
            border: "1px solid var(--dash-border-subtle)",
            background: "transparent",
            color: "var(--dash-text-muted)",
            cursor: "pointer",
          }}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!name.trim() || submitting}
          style={{
            padding: "4px 12px",
            fontSize: 11,
            borderRadius: "var(--dash-radius-sm)",
            border: "1px solid var(--dash-accent)",
            background:
              name.trim() && !submitting
                ? "rgba(63,169,245,0.15)"
                : "transparent",
            color:
              name.trim() && !submitting
                ? "var(--dash-accent)"
                : "var(--dash-text-muted)",
            cursor: name.trim() && !submitting ? "pointer" : "default",
          }}
        >
          {submitting ? "Creating..." : "Create Goal"}
        </button>
      </div>
    </form>
  );
}

/* --------------------------------------------------------------------------- */
/* Main Component                                                              */
/* --------------------------------------------------------------------------- */

export const CommandCenterPage: React.FC = () => {
  const navigate = useNavigate();
  const { systemStats, systemStatus, websocketStatus } = useAIStore();
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // Data states
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [deadlines, setDeadlines] = useState<UpcomingItem[]>([]);
  const [risks, setRisks] = useState<PredictiveRisk[]>([]);
  const [suggestions, setSuggestions] = useState<ProactiveSuggestion[]>([]);

  // Load state
  const [deadlinesLoaded, setDeadlinesLoaded] = useState(false);
  const [risksLoaded, setRisksLoaded] = useState(false);
  const [suggestionsLoaded, setSuggestionsLoaded] = useState(false);

  // Quick goal form
  const [showGoalForm, setShowGoalForm] = useState(false);

  // Acknowledged suggestions (optimistic UI)
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());

  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [briefingRes, deadlinesRes, risksRes, suggestionsRes] =
        await Promise.allSettled([
          authFetch(`${API}/proactive/briefing`).then((r) =>
            r.ok ? r.json() : null
          ),
          authFetch(`${API}/executive/goals/upcoming?days=7`).then((r) =>
            r.ok ? r.json() : null
          ),
          authFetch(`${API}/predictive/risks`).then((r) =>
            r.ok ? r.json() : null
          ),
          authFetch(`${API}/proactive/suggestions?limit=10`).then((r) =>
            r.ok ? r.json() : null
          ),
        ]);

      if (briefingRes.status === "fulfilled" && briefingRes.value) {
        setBriefing(briefingRes.value);
      }
      if (deadlinesRes.status === "fulfilled" && deadlinesRes.value) {
        setDeadlines(deadlinesRes.value.items || []);
        setDeadlinesLoaded(true);
      }
      if (risksRes.status === "fulfilled" && risksRes.value) {
        setRisks(risksRes.value.risks || []);
        setRisksLoaded(true);
      }
      if (suggestionsRes.status === "fulfilled" && suggestionsRes.value) {
        setSuggestions(suggestionsRes.value.suggestions || []);
        setSuggestionsLoaded(true);
      }

      setLastRefresh(new Date());
    } catch {
      // Backend may not be running; show whatever we have
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    refreshTimerRef.current = setInterval(fetchData, 30000);
    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [fetchData]);

  // Acknowledge a suggestion
  const handleAcknowledge = useCallback(async (sug: ProactiveSuggestion) => {
    setAcknowledged((prev) => new Set(prev).add(sug.id));
    try {
      await commandCenter.ackSuggestion(sug.id, sug.title);
    } catch {
      // Best-effort; optimistic UI already updated
    }
  }, []);

  // Goal created handler
  const handleGoalCreated = useCallback(() => {
    setShowGoalForm(false);
    fetchData();
  }, [fetchData]);

  // Extract project name from briefing
  const projectName =
    briefing?.project?.match(/^(.+?)\s*\(/)?.[1]?.trim() ||
    briefing?.project?.split(" ")[0] ||
    null;

  const projectBranch =
    briefing?.project?.match(/\(([^)]+)\)/)?.[1] || null;

  // Filter out acknowledged suggestions from display
  const visibleSuggestions = suggestions.filter(
    (s) => !acknowledged.has(s.id)
  );

  return (
    <div
      style={{
        padding: "20px 28px",
        maxWidth: 1400,
        margin: "0 auto",
        height: "100%",
        overflowY: "auto",
      }}
    >
      {/* Screen reader summary of Command Center status */}
      <LiveRegion>
        {`${deadlines.length} upcoming deadline${deadlines.length === 1 ? "" : "s"}, ${risks.length} predictive risk${risks.length === 1 ? "" : "s"}, ${suggestions.length - acknowledged.size} pending suggestion${suggestions.length - acknowledged.size === 1 ? "" : "s"}.`}
      </LiveRegion>
      {/* ─── Header ─────────────────────────────────────────────────────── */}
      <div
        className="dash-card"
        style={{
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          gap: 14,
          marginBottom: 16,
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: "var(--dash-radius-md)",
            backgroundColor: "rgba(63,169,245,0.12)",
            border: "1px solid rgba(63,169,245,0.25)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Activity size={20} style={{ color: "var(--dash-accent)" }} />
        </div>
        <div style={{ flex: 1 }}>
          <h1
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "var(--dash-text)",
              margin: 0,
            }}
          >
            Command Center
          </h1>
          <p
            style={{
              fontSize: 11,
              color: "var(--dash-text-muted)",
              margin: "2px 0 0",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {briefing?.date || "System overview"}
          </p>
        </div>

        {/* Status indicators */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background:
                  systemStatus === "online"
                    ? "var(--dash-success)"
                    : "var(--dash-danger)",
              }}
            />
            <span
              style={{
                fontSize: 10,
                color:
                  systemStatus === "online"
                    ? "var(--dash-success)"
                    : "var(--dash-danger)",
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {systemStatus === "online" ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background:
                  websocketStatus === "connected"
                    ? "var(--dash-success)"
                    : "var(--dash-warning)",
              }}
            />
            <span
              style={{
                fontSize: 10,
                color: "var(--dash-text-muted)",
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              WS
            </span>
          </div>
          {lastRefresh && (
            <span
              style={{
                fontSize: 9,
                color: "var(--dash-text-muted)",
                fontFamily: "'JetBrains Mono', monospace",
                opacity: 0.6,
              }}
            >
              {lastRefresh.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
          <button
            onClick={fetchData}
            title="Refresh data"
            aria-label="Refresh command center data"
            style={{
              padding: 6,
              borderRadius: "var(--dash-radius-sm)",
              border: "1px solid var(--dash-border-subtle)",
              background: "transparent",
              color: "var(--dash-text-muted)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all var(--dash-transition-fast)",
            }}
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* ─── Main Grid ──────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gridTemplateRows: "auto auto",
          gap: 14,
        }}
      >
        {/* ─── System Context (top-left) ──────────────────────────────── */}
        <div className="dash-card" style={{ padding: 16 }}>
          <PanelHeader icon={Monitor} label="System Context" />
          {loading && !systemStats ? (
            <LoadingPlaceholder text="Loading..." />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {/* Resource bars */}
              {[
                {
                  label: "CPU",
                  value: systemStats?.cpu ?? 0,
                  icon: Cpu,
                  color: "var(--dash-cyan)",
                },
                {
                  label: "RAM",
                  value: systemStats?.ram ?? 0,
                  icon: HardDrive,
                  color: "var(--dash-accent-secondary)",
                },
                {
                  label: "Disk",
                  value: systemStats?.disk ?? 0,
                  icon: Monitor,
                  color: "var(--dash-success)",
                },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: 4,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <Icon size={12} style={{ color }} />
                      <span
                        style={{
                          fontSize: 11,
                          color: "var(--dash-text-secondary)",
                        }}
                      >
                        {label}
                      </span>
                    </div>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--dash-text)",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {value.toFixed(1)}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 3,
                      borderRadius: 2,
                      background: "rgba(255,255,255,0.05)",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(value, 100)}%`,
                        borderRadius: 2,
                        background: color,
                        transition: "width 0.5s",
                      }}
                    />
                  </div>
                </div>
              ))}

              {/* Uptime */}
              {systemStats && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    paddingTop: 6,
                    borderTop: "1px solid var(--dash-border-subtle)",
                    marginTop: 2,
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      color: "var(--dash-text-muted)",
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    UPTIME
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      color: "var(--dash-text-secondary)",
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {formatUptime(systemStats.uptime)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ─── Active Project (top-center) ────────────────────────────── */}
        <div className="dash-card" style={{ padding: 16 }}>
          <PanelHeader icon={Target} label="Active Project" />
          {loading && !briefing ? (
            <LoadingPlaceholder text="Loading..." />
          ) : projectName ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 600,
                    color: "var(--dash-text)",
                    marginBottom: 2,
                  }}
                >
                  {projectName}
                </div>
                {projectBranch && (
                  <span
                    style={{
                      fontSize: 10,
                      padding: "2px 7px",
                      borderRadius: "var(--dash-radius-full)",
                      backgroundColor: "rgba(63,169,245,0.1)",
                      color: "var(--dash-accent)",
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {projectBranch}
                  </span>
                )}
              </div>
              {briefing?.system && (
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--dash-text-secondary)",
                    lineHeight: 1.5,
                    fontFamily: "'JetBrains Mono', monospace",
                    whiteSpace: "pre-line",
                  }}
                >
                  {briefing.system}
                </div>
              )}
            </div>
          ) : (
            <EmptyState text="No active project detected" />
          )}
        </div>

        {/* ─── Upcoming Deadlines (top-right) ─────────────────────────── */}
        <div className="dash-card" style={{ padding: 16 }}>
          <PanelHeader
            icon={Clock}
            label="Upcoming Deadlines"
            count={deadlines.length}
          />
          {!deadlinesLoaded && loading ? (
            <LoadingPlaceholder text="Loading deadlines..." />
          ) : deadlines.length === 0 ? (
            <EmptyState text="No deadlines in the next 7 days" />
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              {deadlines.slice(0, 5).map((item) => (
                <button
                  key={`${item.type}-${item.id}`}
                  onClick={() => navigate("/planner")}
                  title={`View goals (${item.name})`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 10px",
                    borderRadius: "var(--dash-radius-sm)",
                    background: item.overdue
                      ? "var(--dash-danger-bg)"
                      : "var(--dash-bg-subtle)",
                    border: `1px solid ${
                      item.overdue
                        ? "rgba(239,68,68,0.25)"
                        : "var(--dash-border-subtle)"
                    }`,
                    cursor: "pointer",
                    textAlign: "left",
                    width: "100%",
                    transition: "all var(--dash-transition-fast)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor =
                      "var(--dash-border-hover)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.border = `1px solid ${
                      item.overdue
                        ? "rgba(239,68,68,0.25)"
                        : "var(--dash-border-subtle)"
                    }`;
                  }}
                >
                  <div
                    style={{
                      fontSize: 10,
                      fontFamily: "'JetBrains Mono', monospace",
                      fontWeight: 600,
                      color: item.overdue
                        ? "var(--dash-danger)"
                        : "var(--dash-accent)",
                      minWidth: 56,
                      textAlign: "center",
                    }}
                  >
                    {deadlineRelative(item.deadline)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 500,
                        color: "var(--dash-text)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.name}
                    </div>
                    {item.goal_name && (
                      <div
                        style={{
                          fontSize: 10,
                          color: "var(--dash-text-muted)",
                          marginTop: 1,
                        }}
                      >
                        {item.goal_name}
                      </div>
                    )}
                  </div>
                  {item.progress_pct !== null &&
                    item.progress_pct !== undefined && (
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        {Math.round(item.progress_pct)}%
                      </div>
                    )}
                  <ChevronRight
                    size={12}
                    style={{
                      color: "var(--dash-text-muted)",
                      flexShrink: 0,
                    }}
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ─── Predictive Risks (bottom-left) ─────────────────────────── */}
        <div className="dash-card" style={{ padding: 16 }}>
          <PanelHeader
            icon={AlertTriangle}
            label="Predictive Risks"
            count={risks.length}
            accentColor="var(--dash-warning)"
          />
          {!risksLoaded && loading ? (
            <LoadingPlaceholder text="Analyzing risks..." />
          ) : risks.length === 0 ? (
            <EmptyState text="No significant risks detected" />
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              {risks.slice(0, 4).map((risk) => (
                <div
                  key={risk.id}
                  style={{
                    padding: "8px 10px",
                    borderRadius: "var(--dash-radius-sm)",
                    background: "var(--dash-bg-subtle)",
                    border: "1px solid var(--dash-border-subtle)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 4,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: "1px 5px",
                        borderRadius: 3,
                        background: `${severityColor(risk.severity)}18`,
                        color: severityColor(risk.severity),
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {severityLabel(risk.severity)}
                    </span>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 500,
                        color: "var(--dash-text)",
                        flex: 1,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {risk.name}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: "var(--dash-text-muted)",
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {risk.horizon} &middot; {risk.category}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ─── Attention / Suggestions (bottom-center + bottom-right) ─── */}
        <div
          className="dash-card"
          style={{
            padding: 16,
            gridColumn: "span 2",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 12,
            }}
          >
            <Bell
              size={14}
              style={{ color: "var(--dash-accent-secondary)" }}
            />
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "var(--dash-text-secondary)",
              }}
            >
              Attention Required
            </span>
            {visibleSuggestions.length > 0 && (
              <span
                style={{
                  fontSize: 10,
                  padding: "1px 6px",
                  borderRadius: "var(--dash-radius-full)",
                  backgroundColor: "rgba(78,205,196,0.12)",
                  color: "var(--dash-accent-secondary)",
                  fontFamily: "'JetBrains Mono', monospace",
                  marginLeft: "auto",
                }}
              >
                {visibleSuggestions.length}
              </span>
            )}
            <button
              onClick={() => setShowGoalForm(!showGoalForm)}
              title="Create new goal"
              aria-label="Create new goal"
              style={{
                padding: "3px 8px",
                fontSize: 10,
                fontWeight: 600,
                borderRadius: "var(--dash-radius-sm)",
                border: "1px solid var(--dash-border-subtle)",
                background: showGoalForm
                  ? "rgba(63,169,245,0.12)"
                  : "transparent",
                color: showGoalForm
                  ? "var(--dash-accent)"
                  : "var(--dash-text-muted)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
                transition: "all var(--dash-transition-fast)",
              }}
            >
              <Plus size={11} />
              New Goal
            </button>
          </div>

          {/* Quick goal form */}
          {showGoalForm && (
            <div style={{ marginBottom: 10 }}>
              <QuickGoalForm
                onCreated={handleGoalCreated}
                onCancel={() => setShowGoalForm(false)}
              />
            </div>
          )}

          {!suggestionsLoaded && loading ? (
            <LoadingPlaceholder text="Evaluating suggestions..." />
          ) : visibleSuggestions.length === 0 ? (
            <EmptyState text="No pending attention items. System operating normally." />
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: 8,
              }}
            >
              {visibleSuggestions.map((sug) => (
                <button
                  key={sug.id}
                  onClick={() => handleAcknowledge(sug)}
                  title={`Acknowledge: ${sug.title}`}
                  style={{
                    padding: "10px 12px",
                    borderRadius: "var(--dash-radius-sm)",
                    background: "var(--dash-bg-subtle)",
                    border: "1px solid var(--dash-border-subtle)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                    cursor: "pointer",
                    textAlign: "left",
                    width: "100%",
                    transition: "all var(--dash-transition-fast)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor =
                      "var(--dash-border-hover)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor =
                      "var(--dash-border-subtle)";
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        padding: "1px 6px",
                        borderRadius: 3,
                        backgroundColor: "rgba(78,205,196,0.1)",
                        color: "var(--dash-accent-secondary)",
                        fontFamily: "'JetBrains Mono', monospace",
                        textTransform: "uppercase",
                      }}
                    >
                      {sug.category}
                    </span>
                    <span
                      style={{
                        fontSize: 9,
                        color: "var(--dash-text-muted)",
                        fontFamily: "'JetBrains Mono', monospace",
                        marginLeft: "auto",
                      }}
                    >
                      {Math.round(sug.importance * 100)}%
                    </span>
                    <Check
                      size={11}
                      style={{ color: "var(--dash-text-muted)", opacity: 0.4 }}
                    />
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 500,
                      color: "var(--dash-text)",
                    }}
                  >
                    {sug.title}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--dash-text-muted)",
                      lineHeight: 1.4,
                    }}
                  >
                    {sug.message}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CommandCenterPage;
