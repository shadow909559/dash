/**
 * SystemMonitorService – real-time desktop monitoring via WebSocket.
 *
 * Connects to /ws/system on the backend, receives live CPU/RAM/GPU/Storage/
 * Network/Battery/System info every second.
 *
 * Features:
 *  - Auto-connects on creation
 *  - Never crashes (all errors caught)
 *  - Exponential backoff reconnection
 *  - Callback-based data delivery
 */

export interface SystemSnapshot {
  cpu: {
    percentage: number | null;
    cores_physical: number | null;
    cores_logical: number | null;
    frequency_current_mhz: number | null;
    frequency_max_mhz: number | null;
    temperature_celsius: number | null;
    brand: string | null;
    architecture: string | null;
  };
  ram: {
    total_bytes: number | null;
    used_bytes: number | null;
    free_bytes: number | null;
    percent: number | null;
    total_gb: number | null;
    used_gb: number | null;
    free_gb: number | null;
  };
  gpu: Array<{
    name: string | null;
    usage_percent: number | null;
    memory_total_mb: number | null;
    memory_used_mb: number | null;
    temperature_celsius: number | null;
    vram_total_mb: number | null;
    vram_used_mb: number | null;
  }>;
  storage: {
    drives: Array<{
      device: string;
      mountpoint: string;
      fstype: string;
      total_gb: number;
      used_gb: number;
      free_gb: number;
      percent: number;
    }>;
    total_gb: number | null;
    used_gb: number | null;
    free_gb: number | null;
  };
  network: {
    download_speed_bps: number | null;
    upload_speed_bps: number | null;
    download_speed_mbps: number | null;
    upload_speed_mbps: number | null;
    ip_address: string | null;
    hostname: string | null;
  };
  battery: {
    percent: number | null;
    charging: boolean | null;
    remaining_seconds: number | null;
    remaining_minutes: number | null;
  };
  system: {
    os: string | null;
    os_version: string | null;
    os_release: string | null;
    hostname: string | null;
    username: string | null;
    uptime_seconds: number | null;
    uptime_formatted: string | null;
    platform: string | null;
  };
  processes: Array<{
    pid: number;
    name: string;
    cpu_percent: number;
    memory_percent: number;
    memory_mb: number | null;
    status: string;
  }>;
}

type OnDataCallback = (data: SystemSnapshot) => void;
type OnStatusCallback = (connected: boolean) => void;

export class SystemMonitorService {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = Number.MAX_SAFE_INTEGER;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private disconnected = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private onData: OnDataCallback;
  private onStatus: OnStatusCallback;
  private lastData: SystemSnapshot | null = null;

  constructor(
    onData: OnDataCallback,
    onStatus?: OnStatusCallback,
    url?: string
  ) {
    this.onData = onData;
    this.onStatus = onStatus || (() => {});
    this.url = url || "ws://127.0.0.1:8000/api/v1/ws/system";
    this.connect();
  }

  connect(): void {
    if (this.disconnected) return;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      console.error("[SystemMonitor] Failed to create WebSocket:", err);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log("[SystemMonitor] Connected");
      this.reconnectAttempts = 0;
      this.onStatus(true);
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data);

        // Handle ping from server
        if (msg.type === "ping") {
          try {
            this.ws?.send(JSON.stringify({ type: "pong" }));
          } catch {}
          return;
        }

        // Handle pong response
        if (msg.type === "pong") return;

        // Handle system data
        if (msg.type === "system" && msg.data) {
          this.lastData = msg.data as SystemSnapshot;
          try {
            this.onData(msg.data as SystemSnapshot);
          } catch (err) {
            console.error("[SystemMonitor] onData callback error:", err);
          }
        }
      } catch (err) {
        console.error("[SystemMonitor] Error parsing message:", err);
      }
    };

    this.ws.onerror = () => {
      console.error("[SystemMonitor] WebSocket error");
    };

    this.ws.onclose = () => {
      console.log("[SystemMonitor] Disconnected");
      this.ws = null;
      this.onStatus(false);
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (this.disconnected) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;

    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );

    console.log(`[SystemMonitor] Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = setTimeout(() => {
      if (!this.disconnected) {
        this.connect();
      }
    }, delay);
  }

  /** Get the last received snapshot (or null if never received). */
  getLastData(): SystemSnapshot | null {
    return this.lastData;
  }

  /** Is the service currently connected? */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /** Disconnect and stop reconnecting. */
  disconnect(): void {
    this.disconnected = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch {}
      this.ws = null;
    }
    this.onStatus(false);
  }
}

