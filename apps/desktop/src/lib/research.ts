const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

import { authFetch } from "@/lib/api";

export interface ResearchResult {
  title: string;
  url: string;
  snippet: string;
}

export interface ResearchResponse {
  ok: boolean;
  query: string;
  summary: string | null;
  error: string | null;
  results: ResearchResult[];
  abstract: string;
  total_results: number;
}

export async function runResearch(query: string): Promise<ResearchResponse> {
  const url = `${API_BASE}/monitor/research?query=${encodeURIComponent(query)}&max_results=8`;
  const response = await authFetch(url, { method: "POST", signal: AbortSignal.timeout(20000) });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || "Research request failed");
  }
  return response.json();
}
