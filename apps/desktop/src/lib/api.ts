const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

// ── Device-token auth (no login UI) ────────────────────────────────────
// The Electron main process reads %LOCALAPPDATA%\DASH\identity.json and
// exposes it via preload. Every request carries the token; the backend
// returns 401 for anything else.

let cachedToken: string | null | undefined;

async function getDeviceToken(): Promise<string | null> {
  if (cachedToken !== undefined) return cachedToken ?? null;
  try {
    const res = await window.electronAPI?.auth?.deviceToken();
    cachedToken = res?.ok && res.token ? res.token : null;
  } catch {
    cachedToken = null;
  }
  return cachedToken ?? null;
}

export async function isAuthenticated(): Promise<boolean> {
  return (await getDeviceToken()) !== null;
}

/**
 * fetch() with the local device token attached. Use this instead of bare
 * fetch() for every backend call so newly protected endpoints keep working.
 */
export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  };
  const token = await getDeviceToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(url, { ...init, headers });
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  authenticated?: boolean;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {} } = options;

  const allHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...headers,
  };

  const token = await getDeviceToken();
  if (token) {
    allHeaders["Authorization"] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    method,
    headers: allHeaders,
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${endpoint}`, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Request failed");
  }

  return response.json();
}

// Auth
// NOTE: DASH is a single-user local AI. There is no login/register flow;
// the Windows user is the boundary. The Electron main process reads
// %LOCALAPPDATA%\DASH\identity.json and every request carries the device
// token (see getDeviceToken / authFetch above). The backend rejects
// anything without a valid token.

// Chat
export const chat = {
  getConversations: (limit = 50, offset = 0) =>
    request<{ items: Array<{ id: string; title: string; created_at: string; message_count: number; last_message_at: string | null }>; total: number }>(
      `/conversations?limit=${limit}&offset=${offset}`
    ),

  getConversation: (id: string) =>
    request<{ id: string; title: string; message_count: number; created_at: string; updated_at: string }>(
      `/conversations/${id}`
    ),

  getMessages: (conversationId: string, limit = 100, offset = 0) =>
    request<{ items: Array<{ id: string; role: string; content: string; created_at: string }>; total: number; has_more: boolean }>(
      `/conversations/${conversationId}/messages?limit=${limit}&offset=${offset}`
    ),

  createConversation: (title?: string) =>
    request<{ id: string; title: string }>("/conversations", {
      method: "POST",
      body: { title },
    }),
};

// Memory
export const memory = {
  getAll: (page = 1, perPage = 20) =>
    request<{ items: Array<{ id: string; content: string; type: string; created_at: string }>; total: number }>(
      `/memory?page=${page}&per_page=${perPage}`
    ),

  delete: (id: string) =>
    request<void>(`/memory/${id}`, { method: "DELETE" }),

  search: (query: string) =>
    request<Array<{ id: string; content: string; type: string; score: number }>>(
      `/memory/search?q=${encodeURIComponent(query)}`
    ),
};

// Projects
export const projects = {
  getAll: () =>
    request<Array<{ id: string; name: string; description?: string; status: string; created_at: string }>>("/projects"),

  getById: (id: string) =>
    request<{ id: string; name: string; description?: string; status: string; created_at: string }>(`/projects/${id}`),

  create: (data: { name: string; description?: string }) =>
    request<{ id: string; name: string; description?: string }>("/projects", {
      method: "POST",
      body: data,
    }),
};

// Automation
export const automation = {
  getRules: () =>
    request<Array<{ id: string; name: string; trigger: string; action: string; enabled: boolean }>>("/automation/rules"),

  createRule: (data: { name: string; trigger: string; action: string; enabled?: boolean }) =>
    request<{ id: string; name: string; trigger: string; action: string; enabled: boolean }>("/automation/rules", {
      method: "POST",
      body: data,
    }),

  toggleRule: (id: string, enabled: boolean) =>
    request<{ id: string; enabled: boolean }>(`/automation/rules/${id}`, {
      method: "PATCH",
      body: { enabled },
    }),

  deleteRule: (id: string) =>
    request<void>(`/automation/rules/${id}`, { method: "DELETE" }),
};

// Notifications
export const notifications = {
  getAll: () =>
    request<Array<{ id: string; title: string; message: string; read: boolean; created_at: string }>>("/notifications"),

  markRead: (id: string) =>
    request<void>(`/notifications/${id}/read`, { method: "PATCH" }),
};

// WebSocket
// NOTE: The canonical WebSocket client is lib/wsClient.ts (singleton). It
// attaches the local device token to the handshake and waits for the
// server's session.info greeting. There is deliberately no token-less
// "guest" connect helper here — unauthenticated sockets are rejected by
// the backend with close code 4401/HTTP 403.

// Desktop Control
export const desktop = {
  // Volume
  getVolume: () => request<{ volume: number; muted: boolean; summary: string }>("/desktop/volume"),
  setVolume: (level: number) => request<{ volume: number; summary: string }>("/desktop/volume", { method: "POST", body: { level } }),
  setMute: (muted: boolean) => request<{ summary: string }>("/desktop/volume/mute", { method: "POST", body: { muted } }),
  volumeUp: (amount = 5) => request<{ summary: string }>(`/desktop/volume/up?amount=${amount}`, { method: "POST" }),
  volumeDown: (amount = 5) => request<{ summary: string }>(`/desktop/volume/down?amount=${amount}`, { method: "POST" }),

  // Brightness
  getBrightness: () => request<{ brightness: number; summary: string }>("/desktop/brightness"),
  setBrightness: (level: number) => request<{ brightness: number; summary: string }>("/desktop/brightness", { method: "POST", body: { level } }),

  // Clipboard
  clipboardRead: () => request<{ text: string; summary: string }>("/desktop/clipboard"),
  clipboardWrite: (text: string) => request<{ text: string; summary: string }>("/desktop/clipboard", { method: "POST", body: { text } }),
  clipboardClear: () => request<{ summary: string }>("/desktop/clipboard", { method: "DELETE" }),

  // Mouse
  mouseMove: (x: number, y: number) => request<{ status: string }>("/desktop/mouse/move", { method: "POST", body: { x, y } }),
  mouseClick: (button = "left", x?: number, y?: number) => request<{ status: string }>("/desktop/mouse/click", { method: "POST", body: { button, x, y } }),
  mouseDoubleClick: () => request<{ status: string }>("/desktop/mouse/double-click", { method: "POST" }),
  mouseScroll: (clicks = 1) => request<{ status: string }>(`/desktop/mouse/scroll?clicks=${clicks}`, { method: "POST" }),
  mousePosition: () => request<{ status: string; details: { x: number; y: number } }>("/desktop/mouse/position"),

  // Keyboard
  keyboardType: (text: string) => request<{ status: string }>("/desktop/keyboard/type", { method: "POST", body: { text } }),
  keyboardPress: (key: string) => request<{ status: string }>("/desktop/keyboard/press", { method: "POST", body: { key } }),
  keyboardHotkey: (keys: string[]) => request<{ status: string }>("/desktop/keyboard/hotkey", { method: "POST", body: { keys } }),

  // Power
  shutdown: (force = false, timeout = 30) => request<{ summary: string }>("/desktop/power/shutdown", { method: "POST", body: { force, timeout } }),
  restart: (force = false, timeout = 30) => request<{ summary: string }>("/desktop/power/restart", { method: "POST", body: { force, timeout } }),
  lock: () => request<{ summary: string }>("/desktop/power/lock", { method: "POST" }),
  sleep: () => request<{ summary: string }>("/desktop/power/sleep", { method: "POST" }),
  hibernate: () => request<{ summary: string }>("/desktop/power/hibernate", { method: "POST" }),
  logoff: (force = false) => request<{ summary: string }>(`/desktop/power/logoff?force=${force}`, { method: "POST" }),
  abortShutdown: () => request<{ summary: string }>("/desktop/power/abort-shutdown", { method: "POST" }),

  // Screenshot
  screenshot: () => request<{ status: string; details: { image_base64: string; size: number } }>("/desktop/screenshot", { method: "POST" }),

  // Notification
  notification: (title: string, message: string, duration = 5) =>
    request<{ summary: string }>("/desktop/notification", { method: "POST", body: { title, message, duration } }),
};

// Window Manager
export const windows = {
  list: () => request<{ status: string; details: { windows: Array<{ hwnd: number; title: string }>; count: number } }>("/windows"),
  focus: (title: string) => request<{ status: string; details: { summary: string } }>("/windows/focus", { method: "POST", body: { title } }),
  close: (title: string) => request<{ status: string; details: { summary: string } }>("/windows/close", { method: "POST", body: { title } }),
  minimize: (title: string) => request<{ status: string; details: { summary: string } }>("/windows/minimize", { method: "POST", body: { title } }),
  maximize: (title: string) => request<{ status: string; details: { summary: string } }>("/windows/maximize", { method: "POST", body: { title } }),
  move: (title: string, x: number, y: number) => request<{ status: string }>("/windows/move", { method: "POST", body: { title, x, y } }),
  resize: (title: string, width: number, height: number) => request<{ status: string }>("/windows/resize", { method: "POST", body: { title, width, height } }),
  snap: (title: string, position: string) => request<{ status: string }>("/windows/snap", { method: "POST", body: { title, position } }),
  active: () => request<{ status: string; details: { title: string; rect: Record<string, number> } }>("/windows/active"),
};

// Files
export const files = {
  browse: (path = ".", showHidden = false) =>
    request<{ path: string; entries: Array<{ name: string; type: string; size: number; path: string }>; count: number }>(
      `/files/browse?path=${encodeURIComponent(path)}&show_hidden=${showHidden}`
    ),
  search: (pattern: string, path = ".", maxResults = 50) =>
    request<{ pattern: string; path: string; results: Array<{ name: string; path: string; type: string; size: number }>; count: number }>(
      `/files/search?pattern=${encodeURIComponent(pattern)}&path=${encodeURIComponent(path)}&max_results=${maxResults}`
    ),
  preview: (path: string, maxLines = 50) =>
    request<{ name: string; path: string; content: string; type: string; total_lines?: number }>(
      `/files/preview?path=${encodeURIComponent(path)}&max_lines=${maxLines}`
    ),
  copy: (source: string, destination: string) =>
    request<{ summary: string }>("/files/copy", { method: "POST", body: { source, destination } }),
  move: (source: string, destination: string) =>
    request<{ summary: string }>("/files/move", { method: "POST", body: { source, destination } }),
  rename: (path: string, newName: string) =>
    request<{ summary: string }>("/files/rename", { method: "POST", body: { path, new_name: newName } }),
  delete: (path: string, permanent = false) =>
    request<{ summary: string }>("/files/delete", { method: "POST", body: { path, permanent } }),
  recycleBin: () => request<{ results: Array<{ path: string }>; count: number }>("/files/recycle-bin"),
  emptyRecycleBin: () => request<{ summary: string }>("/files/recycle-bin/empty", { method: "POST" }),
  specialFolders: () => request<Record<string, string>>("/files/special-folders"),
  drives: () => request<{ results: Array<{ letter: string; type: string }>; count: number }>("/files/drives"),
};

// AI OS
export const aiOs = {
  execute: (text: string, sessionId = "", userId = "", autoApprove = false) =>
    request<{ success: boolean; plan_id: string; summary: string; steps_completed: number; steps_failed: number }>("/ai-os/execute", {
      method: "POST",
      body: { text, session_id: sessionId, user_id: userId, auto_approve: autoApprove },
    }),
  listPlans: (limit = 10) => request<Array<{ plan_id: string; user_query: string; status: string; steps: Array<Record<string, unknown>> }>>(`/ai-os/plans?limit=${limit}`),
  getPlan: (planId: string) => request<{ plan_id: string; user_query: string; status: string; steps: Array<Record<string, unknown>> }>(`/ai-os/plans/${planId}`),
  cancelPlan: (planId: string) => request<{ cancelled: boolean }>(`/ai-os/plans/${planId}/cancel`, { method: "POST" }),
  listProviders: () => request<{ providers: Array<{ name: string; provider: string; model: string; healthy: boolean }> }>("/ai-os/providers"),
  checkHealth: () => request<Record<string, { healthy: boolean; latency_ms: number }>>("/ai-os/providers/check-health", { method: "POST" }),
  getPermissions: (userId: string) => request<{ always_allowed: Record<string, string[]>; always_denied: Record<string, string[]> }>(`/ai-os/permissions/${userId}`),
  allowCommand: (userId: string, category: string, action: string) =>
    request<{ status: string }>(`/ai-os/permissions/${userId}/allow`, { method: "POST", body: { category, action } }),
  denyCommand: (userId: string, category: string, action: string) =>
    request<{ status: string }>(`/ai-os/permissions/${userId}/deny`, { method: "POST", body: { category, action } }),
  approve: (commandId: string, decision = "allow_once") =>
    request<{ approved: boolean }>(`/ai-os/approve/${commandId}`, { method: "POST", body: { decision } }),
};

// Health
// NOTE: Backend serves health at the ROOT level (no /api/v1 prefix),
// so we fetch it directly from the origin rather than through API_BASE.
export const health = {
  check: () =>
    fetch(`${API_BASE.replace(/\/api\/v1$/, "")}/health`, { signal: AbortSignal.timeout(5000) })
      .then((r) => r.json() as Promise<{ status: string; version: string; uptime: number }>),
};
