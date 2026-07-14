import { DEFAULT_BACKEND_URL, API_PREFIX } from '../features/agent/agentTypes';

export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  body?: Record<string, unknown>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status: number };

function getBaseUrl(): string {
  try {
    const stored = localStorage.getItem('dash-settings');
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed?.general?.backendUrl) return parsed.general.backendUrl;
    }
  } catch { /* ignore */ }
  return DEFAULT_BACKEND_URL;
}

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  try {
    const token = localStorage.getItem('dash-auth-token');
    if (token) headers['Authorization'] = `Bearer ${token}`;
  } catch { /* ignore */ }
  return headers;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiResult<T>> {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}${API_PREFIX}${path}`;

  try {
    const response = await fetch(url, {
      method: options.method ?? 'GET',
      headers: {
        ...getAuthHeaders(),
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });

    if (!response.ok) {
      let errorMsg = `Request failed with status ${response.status}`;
      try {
        const body = await response.json();
        errorMsg = body.detail ?? body.message ?? errorMsg;
      } catch { /* use default */ }
      return { ok: false, error: errorMsg, status: response.status };
    }

    if (response.status === 204) {
      return { ok: true, data: undefined as T };
    }

    const data = await response.json();
    return { ok: true, data: data as T };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Network error';
    return { ok: false, error: message, status: 0 };
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<ApiResult<T>> {
  return apiRequest<T>(path, { signal });
}

export async function apiPost<T>(
  path: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<ApiResult<T>> {
  return apiRequest<T>(path, { method: 'POST', body, signal });
}

export async function apiPut<T>(
  path: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<ApiResult<T>> {
  return apiRequest<T>(path, { method: 'PUT', body, signal });
}

export async function apiDelete<T>(path: string, signal?: AbortSignal): Promise<ApiResult<T>> {
  return apiRequest<T>(path, { method: 'DELETE', signal });
}

export { getBaseUrl, getAuthHeaders };