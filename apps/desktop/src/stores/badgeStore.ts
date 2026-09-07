import { create } from "zustand";
import { authFetch } from "@/lib/api";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface BadgeCounts {
  deadlines: number;
  suggestions: number;
}

interface BadgeStore {
  counts: BadgeCounts;
  lastFetched: number | null;
  fetchCounts: () => Promise<void>;
}

export const useBadgeStore = create<BadgeStore>((set) => ({
  counts: { deadlines: 0, suggestions: 0 },
  lastFetched: null,

  fetchCounts: async () => {
    try {
      const [deadlinesRes, suggestionsRes] = await Promise.allSettled([
        authFetch(`${API}/executive/goals/upcoming?days=7`).then((r) =>
          r.ok ? r.json() : null
        ),
        authFetch(`${API}/proactive/suggestions?limit=20`).then((r) =>
          r.ok ? r.json() : null
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

      set({
        counts: { deadlines, suggestions },
        lastFetched: Date.now(),
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
