import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Cloud, CloudOff, RefreshCw, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { useBadgeStore, type OutboxDeadLetter } from "@/stores/badgeStore";

/**
 * Sidebar footer indicator for Supabase outbox health (decisions.md #46).
 * Polls with the shared 60s badge cycle; expands to show counts and the
 * most recent dead letters with their errors. Clicking navigates to the
 * Command Center for deeper status. Renders nothing while sync is healthy
 * or local-only — failures are what need visibility.
 */

const STATE_STYLES: Record<string, { color: string; label: string }> = {
  HEALTHY: { color: "var(--dash-success)", label: "Sync OK" },
  SYNCING: { color: "var(--dash-accent)", label: "Syncing…" },
  DEGRADED: { color: "var(--dash-warning)", label: "Sync issues" },
  ERROR: { color: "var(--dash-danger)", label: "Sync unknown" },
};

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "unknown";
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function DeadLetterRow({ dl }: { dl: OutboxDeadLetter }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 2,
        padding: "6px 8px",
        borderRadius: "var(--dash-radius-xs)",
        background: "var(--dash-bg-subtle, rgba(255,255,255,0.03))",
        border: "1px solid var(--dash-border-subtle)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "var(--dash-text)",
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {dl.record_type}.{dl.operation}
        </span>
        <span style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>
          {formatWhen(dl.last_attempt_at)}
        </span>
      </div>
      <span
        style={{
          fontSize: 10,
          color: "var(--dash-text-secondary)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={dl.error ?? undefined}
      >
        {dl.error || "unknown error"}
      </span>
      <span style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>
        attempts {dl.attempt_count} · recoveries {dl.recovery_count}/3
      </span>
    </div>
  );
}

export const SyncHealthIndicator: React.FC = () => {
  const { outbox, outboxError } = useBadgeStore();
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  const state = outbox?.state ?? (outboxError ? "ERROR" : null);
  if (!state) return null; // healthy & quiet: no noise in the footer
  if (state === "HEALTHY") return null;
  if (state === "LOCAL_ONLY") return null;

  const style = STATE_STYLES[state] ?? STATE_STYLES.ERROR;
  const dead = outbox?.dead_letter ?? 0;
  const pending = outbox?.pending ?? 0;
  const exhausted = outbox?.dead_letter_exhausted ?? 0;
  const recent = outbox?.recent_dead_letters ?? [];

  return (
    <div
      style={{
        margin: "8px 8px 4px 8px",
        borderRadius: "var(--dash-radius-sm)",
        border: `1px solid ${style.color}55`,
        background: `${style.color}0d`,
        overflow: "hidden",
      }}
    >
      <button
        onClick={() => (state === "DEGRADED" ? setExpanded((v) => !v) : navigate("/"))}
        aria-expanded={state === "DEGRADED" ? expanded : undefined}
        aria-label={`Cloud sync status: ${style.label}. ${dead} dead-lettered, ${pending} pending events`}
        title={`Cloud sync: ${style.label}`}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "7px 10px",
          background: "transparent",
          border: "none",
          color: "var(--dash-text-secondary)",
          cursor: "pointer",
          fontSize: 11,
          textAlign: "left",
        }}
      >
        {state === "ERROR" ? (
          <AlertTriangle size={14} style={{ color: style.color, flexShrink: 0 }} />
        ) : (
          <Cloud size={14} style={{ color: style.color, flexShrink: 0 }} />
        )}
        <span style={{ flex: 1, fontWeight: 600, color: style.color }}>{style.label}</span>
        {dead > 0 && (
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              padding: "1px 6px",
              borderRadius: "var(--dash-radius-full)",
              background: `${style.color}22`,
              border: `1px solid ${style.color}55`,
              color: style.color,
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {dead}
          </span>
        )}
        {state === "DEGRADED" &&
          (expanded ? (
            <ChevronUp size={12} />
          ) : (
            <ChevronDown size={12} />
          ))}
      </button>

      {expanded && state === "DEGRADED" && (
        <div
          style={{
            padding: "2px 8px 8px 8px",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 10,
              fontSize: 10,
              color: "var(--dash-text-muted)",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            <span>pending {pending}</span>
            <span>retryable {Math.max(0, dead - exhausted)}</span>
            <span>stuck {exhausted}</span>
          </div>
          {recent.length > 0 && (
            <>
              <span
                style={{
                  fontSize: 9,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--dash-text-muted)",
                }}
              >
                Recent failures
              </span>
              {recent.map((dl) => (
                <DeadLetterRow key={dl.id} dl={dl} />
              ))}
            </>
          )}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 10,
              color: "var(--dash-text-muted)",
            }}
          >
            <RefreshCw size={10} />
            <span>last sync: {formatWhen(outbox?.last_successful_sync)}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default SyncHealthIndicator;
