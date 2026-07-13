/** Shared type definitions for DASH clients and services. */

export type DashEnvironment = 'development' | 'staging' | 'production' | 'test';

export type HealthStatus = 'ok' | 'degraded' | 'down';

export interface HealthResponse {
  status: HealthStatus;
  service: string;
  version: string;
  environment: DashEnvironment;
  timestamp: string;
}

export interface WebSocketMessage<T = unknown> {
  type: string;
  received?: T;
  payload?: T;
}

export interface DashClientConfig {
  baseUrl: string;
  apiPrefix?: string;
  timeoutMs?: number;
}

export type Platform = 'win32' | 'darwin' | 'linux' | 'android' | 'ios' | 'unknown';
