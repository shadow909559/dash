import { create } from 'zustand';
import {
  AgentStatus,
  DEFAULT_WS_URL,
  HEALTH_PATH,
  MachineInfo,
  AgentState,
} from './agentTypes';

// ── Safe command allowlist ──────────────────────────────────────────────
// Only read-only / informational commands are allowed.
// No destructive operations (rm, kill, shutdown, write, etc.).
const SAFE_COMMANDS = new Set([
  'ls', 'dir', 'pwd', 'whoami', 'hostname', 'uname', 'uptime',
  'date', 'cal', 'df', 'du', 'free', 'ps', 'top', 'stat',
  'cat', 'head', 'tail', 'wc', 'echo', 'which', 'type',
  'env', 'printenv', 'id', 'groups', 'users', 'finger',
  'lscpu', 'lsblk', 'lspci', 'lsusb', 'lsof',
  'ip', 'ifconfig', 'netstat', 'ss', 'ping', 'traceroute',
  'nslookup', 'dig', 'curl', 'wget',
  'git status', 'git log', 'git diff', 'git branch', 'git remote',
  'npm list', 'npm outdated', 'pip list', 'pip show',
  'docker ps', 'docker images', 'docker stats',
  'systemctl list-units', 'journalctl',
  'find', 'locate', 'grep', 'awk', 'sed', 'sort', 'uniq',
  'history', 'last', 'w', 'who',
]);

const UNSAFE_PATTERNS = [
  /rm\s+-[rf]/i, /mkfs/i, /dd\s+if=/i, /:(){ :\|:& };:/i,
  /chmod\s+777/i, /chown/i, /kill\s+-9/i, /shutdown/i,
  /reboot/i, /halt/i, /poweroff/i, /init\s+0/i, /init\s+6/i,
  />\s*\//, />>\s*\//, /sudo/i, /su\s/, /passwd/i,
  /wget\s+.*\|\s*(bash|sh)/i, /curl\s+.*\|\s*(bash|sh)/i,
  /eval/i, /exec/i, /source\s+\//i, /\.\s+\//i,
  /format/i, /fdisk/i, /parted/i, /mkswap/i,
  /iptables/i, /ufw/i, /firewall/i,
  /crontab/i, /at\s+/i, /batch/i,
  /ddos/i, /attack/i, /flood/i,
  /proxy/i, /tunnel/i, /reverse.*shell/i,
  /nc\s+-[e]/i, /ncat/i, /socat/i,
  /install/i, /apt/i, /yum/i, /dnf/i, /pacman/i, /brew/i,
  /wget\s+.*-O/i, /curl\s+.*-o/i,
];

function isCommandSafe(command: string): boolean {
  const trimmed = command.trim();
  if (!trimmed) return false;

  // Check unsafe patterns
  for (const pattern of UNSAFE_PATTERNS) {
    if (pattern.test(trimmed)) return false;
  }

  // Check if the base command is in the allowlist
  const baseCommand = trimmed.split(/\s+/)[0]?.toLowerCase();
  if (!baseCommand) return false;
  if (SAFE_COMMANDS.has(baseCommand)) return true;

  // Allow some common safe patterns
  if (/^ls\b/.test(trimmed)) return true;
  if (/^echo\s/.test(trimmed)) return true;
  if (/^cat\s/.test(trimmed)) return true;
  if (/^head\s/.test(trimmed)) return true;
  if (/^tail\s/.test(trimmed)) return true;
  if (/^grep\s/.test(trimmed)) return true;
  if (/^find\s/.test(trimmed)) return true;
  if (/^ps\s/.test(trimmed)) return true;
  if (/^df\s/.test(trimmed)) return true;
  if (/^du\s/.test(trimmed)) return true;
  if (/^free\s/.test(trimmed)) return true;
  if (/^which\s/.test(trimmed)) return true;
  if (/^whoami\b/.test(trimmed)) return true;
  if (/^hostname\b/.test(trimmed)) return true;
  if (/^uptime\b/.test(trimmed)) return true;
  if (/^date\b/.test(trimmed)) return true;
  if (/^uname\b/.test(trimmed)) return true;
  if (/^id\b/.test(trimmed)) return true;
  if (/^pwd\b/.test(trimmed)) return true;
  if (/^env\b/.test(trimmed)) return true;
  if (/^printenv\b/.test(trimmed)) return true;
  if (/^dir\b/.test(trimmed)) return true;
  if (/^type\b/.test(trimmed)) return true;
  if (/^stat\b/.test(trimmed)) return true;
  if (/^wc\b/.test(trimmed)) return true;
  if (/^sort\b/.test(trimmed)) return true;
  if (/^uniq\b/.test(trimmed)) return true;
  if (/^history\b/.test(trimmed)) return true;
  if (/^last\b/.test(trimmed)) return true;
  if (/^w\b/.test(trimmed)) return true;
  if (/^who\b/.test(trimmed)) return true;
  if (/^cal\b/.test(trimmed)) return true;
  if (/^lscpu\b/.test(trimmed)) return true;
  if (/^lsblk\b/.test(trimmed)) return true;
  if (/^lspci\b/.test(trimmed)) return true;
  if (/^lsusb\b/.test(trimmed)) return true;
  if (/^lsof\b/.test(trimmed)) return true;
  if (/^ip\s/.test(trimmed)) return true;
  if (/^ifconfig\b/.test(trimmed)) return true;
  if (/^netstat\b/.test(trimmed)) return true;
  if (/^ss\b/.test(trimmed)) return true;
  if (/^ping\b/.test(trimmed)) return true;
  if (/^nslookup\b/.test(trimmed)) return true;
  if (/^dig\b/.test(trimmed)) return true;
  if (/^git\s/.test(trimmed)) return true;
  if (/^npm\s/.test(trimmed)) return true;
  if (/^pip\s/.test(trimmed)) return true;
  if (/^docker\s/.test(trimmed)) return true;
  if (/^systemctl\s/.test(trimmed)) return true;
  if (/^journalctl\b/.test(trimmed)) return true;
  if (/^locate\b/.test(trimmed)) return true;

  return false;
}

// ── Agent Store ─────────────────────────────────────────────────────────
const MAX_RECONNECT_ATTEMPTS = 5;
const HEARTBEAT_INTERVAL_MS = 15000;
const RECONNECT_BASE_DELAY_MS = 2000;

type MessageListener = (data: Record<string, unknown>) => void;

type AgentStore = AgentState & {
  _ws: WebSocket | null;
  _heartbeatTimer: ReturnType<typeof setInterval> | null;
  _reconnectTimer: ReturnType<typeof setTimeout> | null;
  _connectedAt: number | null;
  _lastHeartbeatAt: number | null;
  _pendingResolve: ((value: boolean) => void) | null;
  _messageListeners: Set<MessageListener>;

  /** Subscribe to incoming WebSocket messages */
  onMessage: (listener: MessageListener) => () => void;
};

export const useAgentStore = create<AgentStore>((set, get) => ({
  status: AgentStatus.disconnected,
  url: DEFAULT_WS_URL,
  machineInfo: null,
  connectionDetails: {
    url: DEFAULT_WS_URL,
    connectedAt: null,
    lastHeartbeatAt: null,
    heartbeatInterval: HEARTBEAT_INTERVAL_MS,
    reconnecting: false,
    reconnectAttempts: 0,
  },
  lastError: null,
  lastHeartbeatLatency: null,

  _ws: null,
  _heartbeatTimer: null,
  _reconnectTimer: null,
  _reconnectAttempts: 0,
  _connectedAt: null,
  _lastHeartbeatAt: null,
  _pendingResolve: null,
  _messageListeners: new Set(),
  onMessage: (listener) => {
    get()._messageListeners.add(listener);
    return () => {
      get()._messageListeners.delete(listener);
    };
  },

  // ── Connect ──────────────────────────────────────────────────────────
  connect: (url?: string) => {
    const state = get();
    const wsUrl = url || state.url;

    // Clean up any existing connection
    if (state._ws) {
      state._ws.close();
    }
    if (state._heartbeatTimer) {
      clearInterval(state._heartbeatTimer);
    }
    if (state._reconnectTimer) {
      clearTimeout(state._reconnectTimer);
    }

    set({
      status: AgentStatus.connecting,
      url: wsUrl,
      lastError: null,
      _ws: null,
      _heartbeatTimer: null,
      _reconnectTimer: null,
    });

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        const now = Date.now();
        set({
          status: AgentStatus.connected,
          _ws: ws,
          _connectedAt: now,
          _lastHeartbeatAt: now,
          _reconnectAttempts: 0,
          connectionDetails: {
            url: wsUrl,
            connectedAt: now,
            lastHeartbeatAt: now,
            heartbeatInterval: HEARTBEAT_INTERVAL_MS,
            reconnecting: false,
            reconnectAttempts: 0,
          },
        });

        // Start heartbeat
        const timer = setInterval(() => {
          const currentState = get();
          if (currentState._ws?.readyState === WebSocket.OPEN) {
            const heartbeatPayload = {
              type: 'heartbeat',
              timestamp: Date.now(),
            };
            try {
              currentState._ws.send(JSON.stringify(heartbeatPayload));
            } catch {
              // Connection may have dropped
            }
          }
        }, HEARTBEAT_INTERVAL_MS);
        set({ _heartbeatTimer: timer });

        // Fetch machine info via REST health endpoint
        get()._fetchMachineInfo();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);
          const currentState = get();

          if (data.type === 'heartbeat_ack' || data.type === 'pong') {
            const now = Date.now();
            const latency = data.timestamp ? now - data.timestamp : null;
            set({
              _lastHeartbeatAt: now,
              lastHeartbeatLatency: latency,
              connectionDetails: {
                ...currentState.connectionDetails,
                lastHeartbeatAt: now,
              },
            });
          } else if (data.type === 'echo') {
            // Handle echo responses from the backend
            // The backend echoes back whatever we send
          } else if (data.type === 'machine_info') {
            set({ machineInfo: data.info as MachineInfo });
          } else if (data.type === 'command_result') {
            // Command results are handled via the chat store integration
            // This is for direct agent-level command results
          }

          // Forward all parsed messages to registered listeners
          get()._messageListeners.forEach((listener) => {
            try {
              listener(data as Record<string, unknown>);
            } catch {
              // Isolate listener failures
            }
          });
        } catch {
          // Non-JSON messages are ignored at the agent level
        }
      };

      ws.onerror = () => {
        set({
          status: AgentStatus.error,
          lastError: 'WebSocket connection error',
        });
      };

      ws.onclose = () => {
        const currentState = get();
        if (currentState._heartbeatTimer) {
          clearInterval(currentState._heartbeatTimer);
        }
        set({
          status: AgentStatus.disconnected,
          _ws: null,
          _heartbeatTimer: null,
        });
        get()._scheduleReconnect();
      };
    } catch (error) {
      set({
        status: AgentStatus.error,
        lastError: error instanceof Error ? error.message : 'Failed to connect',
      });
      get()._scheduleReconnect();
    }
  },

  // ── Disconnect ───────────────────────────────────────────────────────
  disconnect: () => {
    const state = get();
    if (state._heartbeatTimer) {
      clearInterval(state._heartbeatTimer);
    }
    if (state._reconnectTimer) {
      clearTimeout(state._reconnectTimer);
    }
    if (state._ws) {
      state._ws.onclose = null; // Prevent reconnect on intentional close
      state._ws.close();
    }
    set({
      status: AgentStatus.disconnected,
      _ws: null,
      _heartbeatTimer: null,
      _reconnectTimer: null,
      _reconnectAttempts: 0,
      _connectedAt: null,
      _lastHeartbeatAt: null,
      machineInfo: null,
      lastError: null,
      connectionDetails: {
        url: state.url,
        connectedAt: null,
        lastHeartbeatAt: null,
        heartbeatInterval: HEARTBEAT_INTERVAL_MS,
        reconnecting: false,
        reconnectAttempts: 0,
      },
    });
  },

  // ── Send Message ─────────────────────────────────────────────────────
  sendMessage: (payload: Record<string, unknown>) => {
    const state = get();
    if (state._ws?.readyState !== WebSocket.OPEN) {
      return;
    }
    try {
      state._ws.send(JSON.stringify(payload));
    } catch {
      // Silently fail - connection may have dropped
    }
  },

  // ── Internal: Fetch machine info ─────────────────────────────────────
  _fetchMachineInfo: async () => {
    try {
      const backendUrl = get().url.replace(/^ws:/, 'http:').replace(/\/api\/v1\/ws$/, '');
      const healthUrl = `${backendUrl}${HEALTH_PATH}`;
      const response = await fetch(healthUrl);
      if (!response.ok) return;

      const healthData = await response.json();

      // Build machine info from available data + navigator
      const info: MachineInfo = {
        hostname: window.dash?.platform || navigator.platform || 'unknown',
        platform: navigator.platform || 'unknown',
        os: navigator.userAgent || 'unknown',
        cpu: navigator.hardwareConcurrency
          ? `${navigator.hardwareConcurrency} cores`
          : 'unknown',
        memory: (navigator as unknown as { deviceMemory?: number }).deviceMemory
          ? `${(navigator as unknown as { deviceMemory: number }).deviceMemory} GB`
          : 'unknown',
        uptime: healthData.timestamp
          ? `Server: ${healthData.timestamp}`
          : 'unknown',
      };
      set({ machineInfo: info });
    } catch {
      // Machine info is best-effort
    }
  },

  // ── Internal: Schedule reconnect ─────────────────────────────────────
  _scheduleReconnect: () => {
    const state = get();
    if (state._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      set({
        lastError: `Max reconnect attempts (${MAX_RECONNECT_ATTEMPTS}) reached`,
        connectionDetails: {
          ...state.connectionDetails,
          reconnecting: false,
          reconnectAttempts: state._reconnectAttempts,
        },
      });
      return;
    }

    const attempts = state._reconnectAttempts + 1;
    const delay = RECONNECT_BASE_DELAY_MS * Math.min(attempts, 5);

    set({
      _reconnectAttempts: attempts,
      connectionDetails: {
        ...state.connectionDetails,
        reconnecting: true,
        reconnectAttempts: attempts,
      },
    });

    const timer = setTimeout(() => {
      const currentState = get();
      if (currentState.status !== AgentStatus.connected) {
        currentState.connect();
      }
    }, delay);
    set({ _reconnectTimer: timer });
  },
}));

// ── Helper: Execute a safe command via the agent ────────────────────────
export function executeSafeCommand(
  command: string,
): { safe: false; reason: string } | { safe: true; command: string } {
  if (!isCommandSafe(command)) {
    return {
      safe: false,
      reason: 'Command rejected: not in the safe allowlist or matches an unsafe pattern.',
    };
  }
  return { safe: true, command };
}

// ── Helper: Get agent status display info ──────────────────────────────
export function getAgentStatusLabel(status: AgentStatus): string {
  switch (status) {
    case AgentStatus.disconnected:
      return 'Disconnected';
    case AgentStatus.connecting:
      return 'Connecting…';
    case AgentStatus.connected:
      return 'Connected';
    case AgentStatus.error:
      return 'Error';
  }
}

export { isCommandSafe };