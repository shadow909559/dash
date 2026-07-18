import { type DashClientConfig, type HealthResponse } from '@dash/shared';
export interface DashClientOptions extends DashClientConfig {
    fetchImpl?: typeof fetch;
}
/**
 * Minimal HTTP client for the DASH backend.
 * Foundation milestone — health check only.
 */
export declare class DashClient {
    readonly version: "0.1.0";
    private readonly baseUrl;
    private readonly timeoutMs;
    private readonly fetchImpl;
    constructor(options?: DashClientOptions);
    health(): Promise<HealthResponse>;
    getWebSocketUrl(): string;
}
//# sourceMappingURL=client.d.ts.map