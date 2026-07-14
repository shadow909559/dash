export const DEFAULT_BACKEND_URL = 'http://localhost:8000';
export const API_PREFIX = '/api/v1';
export const HEALTH_PATH = `${API_PREFIX}/health`;
export const WEBSOCKET_PATH = `${API_PREFIX}/ws`;
export const DEFAULT_WS_URL = `ws://localhost:8000${WEBSOCKET_PATH}`;

export enum AgentStatus {
  disconnected = 'disconnected',
  connecting = 'connecting',
  connected = 'connected',
  error = 'error',
}

export type MachineInfo = {
  hostname: string;
  platform: string;
  os: string;
  cpu: string;
  memory: string;
  uptime: string;
};

export type ConnectionDetails = {
  url: string;
  connectedAt: number | null;
  lastHeartbeatAt: number | null;
  heartbeatInterval: number | null;
  reconnecting: boolean;
  reconnectAttempts: number;
};

export type CommandResult = {
  stdout: string;
  stderr: string;
  exitCode: number;
  duration: number;
};

// Extend the Window interface to include the preload API
declare global {
  interface Window {
    dash?: {
      version: string;
      platform: string;
    };
  }
}

export type AgentState = {
  status: AgentStatus;
  url: string;
  machineInfo: MachineInfo | null;
  connectionDetails: ConnectionDetails;
  lastError: string | null;
  lastHeartbeatLatency: number | null;
  _reconnectAttempts: number;

  connect: (url?: string) => void;
  disconnect: () => void;
  sendMessage: (payload: Record<string, unknown>) => void;
  _fetchMachineInfo: () => Promise<void>;
  _scheduleReconnect: () => void;
};
