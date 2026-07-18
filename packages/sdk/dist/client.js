import { API_ROUTES, APP_VERSION, DEFAULT_BACKEND_URL, } from '@dash/shared';
/**
 * Minimal HTTP client for the DASH backend.
 * Foundation milestone — health check only.
 */
export class DashClient {
    version = APP_VERSION;
    baseUrl;
    timeoutMs;
    fetchImpl;
    constructor(options = { baseUrl: DEFAULT_BACKEND_URL }) {
        this.baseUrl = options.baseUrl.replace(/\/$/, '');
        this.timeoutMs = options.timeoutMs ?? 10_000;
        this.fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);
    }
    async health() {
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
            return (await response.json());
        }
        finally {
            clearTimeout(timeout);
        }
    }
    getWebSocketUrl() {
        const wsBase = this.baseUrl.replace(/^http/, 'ws');
        return `${wsBase}${API_ROUTES.WEBSOCKET}`;
    }
}
//# sourceMappingURL=client.js.map