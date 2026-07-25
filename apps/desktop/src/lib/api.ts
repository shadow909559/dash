const API_BASE = "http://127.0.0.1:8000/api/v1";

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  authenticated?: boolean;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {}, authenticated = true } = options;

  const token = localStorage.getItem("dash_access_token");
  const allHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...headers,
  };

  if (authenticated && token) {
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
export const auth = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: { email, password },
      authenticated: false,
    }),

  register: (email: string, password: string, username?: string) =>
  request("/auth/register", {
    method: "POST",
    body: {
      email,
      password,
      username,
    },
    authenticated: false,
  }),
  
  me: () => request<{ id: string; email: string; name?: string }>("/auth/me"),

  refresh: (refreshToken: string) =>
    request<{ access_token: string; refresh_token: string }>("/auth/refresh", {
      method: "POST",
      body: { refresh_token: refreshToken },
      authenticated: false,
    }),
};

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
export function createWebSocket(): WebSocket {
  const token = localStorage.getItem("dash_access_token");
  // Connect without token in query param - auth is done by sending an "auth" message
  const ws = new WebSocket("ws://127.0.0.1:8000/api/v1/ws");

  ws.addEventListener("open", () => {
    // Authenticate immediately on connect
    if (token) {
      ws.send(JSON.stringify({ type: "auth", access_token: token }));
    }
  });

  return ws;
}

// Health
export const health = {
  check: () =>
    request<{ status: string; version: string; uptime: number }>("/health", { authenticated: false }),
};