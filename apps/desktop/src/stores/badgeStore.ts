import { create } from "zustand";
import { authFetch } from "@/lib/api";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface BadgeCounts {
  deadlines: number;
  suggestions: number;
}

export interface OutboxDeadLetter {
  id: string;
  record_type: string;
  record_id: string;
  operation: string;
  error: string | null;
  attempt_count: number;
  recovery_count: number;
  last_attempt_at: string | null;
}

export interface OutboxHealth {
  state: "HEALTHY" | "DEGRADED" | "SYNCING" | "LOCAL_ONLY" | "ERROR";
  sync_enabled?: boolean;
  pending?: number;
  processing?: number;
  completed?: number;
  dead_letter?: number;
  dead_letter_retryable?: number;
  dead_letter_exhausted?: number;
  recent_dead_letters?: OutboxDeadLetter[];
  last_successful_sync?: string | null;
  checked_at?: string;
}

interface BadgeStore {
  counts: BadgeCounts;
  lastFetched: number | null;
  outbox: OutboxHealth | null;
  outboxError: string | null;
  fetchCounts: () => Promise<void>;
}

export const useBadgeStore = create<BadgeStore>((set) => ({
  counts: { deadlines: 0, suggestions: 0 },
  lastFetched: null,
  outbox: null,
  outboxError: null,

  fetchCounts: async () => {
    try {
      const [deadlinesRes, suggestionsRes, outboxRes] = await Promise.allSettled([
        authFetch(`${API}/executive/goals/upcoming?days=7`).then((r) =>
          r.ok ? r.json() : null
        ),
        authFetch(`${API}/proactive/suggestions?limit=20`).then((r) =>
          r.ok ? r.json() : null
        ),
        authFetch(`${API}/sync/outbox/health`).then((r) =>
          r.ok ? r.json() : { state: "ERROR" as const }
        ),
      ]);

      const deadlines =
        deadlinesRes.status === "fulfilled" && deadlinesRes.value
          ? deadlinesRes.value.count ?? (deadlinesRes.value.items?.length ?? 0)
          : 0;

      const suggestions =
        suggestionsRes.status === "fulfilled" && suggestionsRes.value
          ? suggestionsRes.value.count ??
            (suggestionsRes.value.suggestions?.length ?? 0)
          : 0;

      // Outbox health: fulfilled + parsed body wins; a non-OK response maps
      // to state ERROR so the indicator can show "sync status unknown"
      // instead of silently keeping stale data. Backend-down (rejected)
      // clears to null — the global system indicator already covers that.
      let outbox: OutboxHealth | null = null;
      let outboxError: string | null = null;
      if (outboxRes.status === "fulfilled") {
        const value = outboxRes.value;
        if (value && value.state && value.state !== "ERROR") {
          outbox = value;
        } else {
          outboxError = "sync status unavailable";
        }
      }

      set({
        counts: { deadlines, suggestions },
        lastFetched: Date.now(),
        outbox,
        outboxError,
      });
    } catch {
      // Backend may be offline; keep stale counts
    }
  },
}));

/**
 * Start periodic badge polling. Returns the interval ID for cleanup.
 * Call this once from App.tsx on mount.
 */
export function startBadgePolling(intervalMs: number = 60000): ReturnType<typeof setInterval> | null {
  if (typeof window === "undefined") return null;

  // Initial fetch
  useBadgeStore.getState().fetchCounts();

  const intervalId = setInterval(() => {
    useBadgeStore.getState().fetchCounts();
  }, intervalMs);

  return intervalId;
}
