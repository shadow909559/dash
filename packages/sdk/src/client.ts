import {
  API_ROUTES,
  APP_VERSION,
  DEFAULT_BACKEND_URL,
  type DashClientConfig,
  type HealthResponse,
} from '@dash/shared';

export interface DashClientOptions extends DashClientConfig {
  fetchImpl?: typeof fetch;
}

/**
 * Minimal HTTP client for the DASH backend.
 * Foundation milestone — health check only.
 */
export class DashClient {
  readonly version = APP_VERSION;

  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(options: DashClientOptions = { baseUrl: DEFAULT_BACKEND_URL }) {
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.timeoutMs = options.timeoutMs ?? 10_000;
    this.fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);
  }

  async health(): Promise<HealthResponse> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.fetchImpl(`${this.baseUrl}${API_ROUTES.HEALTH}`, {
        signal: controller.signal,
        headers: { Accept: 'application/json' },
      });

      if (!response.ok) {
        throw new Error(`Health check failed with status ${response.status}`);
      }

      return (await response.json()) as HealthResponse;
    } finally {
      clearTimeout(timeout);
    }
  }

  getWebSocketUrl(): string {
    const wsBase = this.baseUrl.replace(/^http/, 'ws');
    return `${wsBase}${API_ROUTES.WEBSOCKET}`;
  }
}
