/**
 * WebSocket client for DASH real-time chat.
 *
 * SINGLETON — one connection for the entire app lifetime.
 *
 * Protocol:
 *   client -> server: { type: "chat.send", conversation_id?: string, message_id: string, content: string }
 *   server -> client: { type: "chat.status", message_id, status, detail? }
 *   server -> client: { type: "chat.token", message_id, content }
 *   server -> client: { type: "chat.done", message_id, conversation_id? }
 *   server -> client: { type: "chat.error", message_id?, error }
 */

type WSEventHandler = (data: Record<string, unknown>) => void;

export type ConnectionState = "idle" | "connecting" | "connected" | "reconnecting" | "disconnected";

export interface WSChatCallbacks {
  onToken: (messageId: string, token: string) => void;
  onDone: (messageId: string, conversationId?: string) => void;
  onError: (messageId: string | null, error: string) => void;
  onStatus?: (messageId: string, status: string, detail?: string) => void;
}

export class WsClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 60;
  private baseReconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private disconnected = false;
  private authenticated = false;
  private pendingAuthResolve: (() => void) | null = null;
  private pendingAuthReject: ((err: Error) => void) | null = null;
  private authPromise: Promise<void> | null = null;
  private eventHandlers = new Map<string, Set<WSEventHandler>>();
  private chatCallbacks: WSChatCallbacks | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isConnecting = false;
  private socketGeneration = 0;

  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private lastPongTime = 0;
  private activeRequestIds = new Map<string, { timestamp: number; timeout: ReturnType<typeof setTimeout> }>();
  private readonly HEARTBEAT_INTERVAL = 20000;
  private readonly STALE_THRESHOLD = 120000; // 2 minutes for idle connections
  private readonly ACTIVE_STALE_THRESHOLD = 20 * 60 * 1000; // 20 minutes for active requests
  private readonly REQUEST_TIMEOUT = 5 * 60 * 1000; // 5 minutes for individual requests

  private pingSentAt = 0;
  private currentLatencyMs = 0;
  private latencyWindow: number[] = [];
  private readonly LATENCY_WINDOW_SIZE = 30;

  private pendingMessages: Array<{ conversationId: string | null; messageId: string; content: string }> = [];
  private pendingSendTimer: ReturnType<typeof setTimeout> | null = null;

  private onStatusChange: ((connected: boolean, authenticated: boolean, state: ConnectionState) => void) | null = null;
  private connectionState: ConnectionState = "idle";
  private apiUrl: string;

  constructor(url?: string) {
    this.apiUrl = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";
    this.url = url || this.apiUrl.replace(/^http/, "ws") + "/ws";
  }

  onStatus(callback: (connected: boolean, authenticated: boolean, state: ConnectionState) => void): void {
    this.onStatusChange = callback;
  }

  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  private setState(state: ConnectionState): void {
    this.connectionState = state;
    const connected = state === "connected";
    this.onStatusChange?.(connected, this.authenticated && connected, state);
  }

  async connect(): Promise<void> {
    if (this.disconnected) return;
    if (this.isConnecting && this.authPromise) return this.authPromise;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return this.authPromise || Promise.resolve();
    }

    this.isConnecting = true;
    this.setState(this.reconnectAttempts > 0 ? "reconnecting" : "connecting");

    // Attach the local device token to the handshake (backend rejects
    // unauthenticated sockets with close code 4401).
    let wsUrl = this.url;
    try {
      const res = await window.electronAPI?.auth?.deviceToken();
      if (res?.ok && res.token) {
        const sep = wsUrl.includes("?") ? "&" : "?";
        wsUrl = `${wsUrl}${sep}token=${encodeURIComponent(res.token)}`;
      }
    } catch {
      /* proceed without token; backend will reject and we surface the error */
    }

    const generation = ++this.socketGeneration;
    const socket = new WebSocket(wsUrl);
    this.ws = socket;

    this.authPromise = new Promise<void>((resolve, reject) => {
      this.pendingAuthResolve = resolve;
      this.pendingAuthReject = reject;

      const timeout = setTimeout(() => {
        if (this.socketGeneration !== generation) return;
        this.isConnecting = false;
        reject(new Error("WebSocket connection timeout"));
        try {
          socket.close();
        } catch {
          /* ignore */
        }
      }, 15000);

      const isCurrent = () => this.ws === socket && this.socketGeneration === generation;

      socket.addEventListener("close", (event) => {
        if (!isCurrent()) return;
        // 4401 = device token missing/invalid. Do NOT fast-loop retries.
        if ((event as CloseEvent).code === 4401) {
          this.isConnecting = false;
          this.authenticated = false;
          clearTimeout(timeout);
          this.pendingAuthReject?.(new Error("DASH rejected the device token (4401)"));
          this.pendingAuthReject = null;
          this.setState("disconnected");
          return;
        }
      });
      socket.addEventListener("open", () => {
        if (!isCurrent()) return;
        // Authenticated only once the server greets with session.info —
        // the handshake token was validated server-side at that point.
        const onFirst = (msgEvent: MessageEvent) => {
          try {
            const data = JSON.parse(msgEvent.data);
            if (data?.type === "session.info") {
              socket.removeEventListener("message", onFirst);
              this.authenticated = true;
              this.isConnecting = false;
              this.reconnectAttempts = 0;
              clearTimeout(timeout);
              this.pendingAuthResolve?.();
              this.pendingAuthResolve = null;
              this.pendingAuthReject = null;
              this.setState("connected");
              this.startHeartbeat();
              this.flushPendingMessages();
            }
          } catch {
            /* non-JSON first frame; ignore */
          }
        };
        socket.addEventListener("message", onFirst);
      });

      socket.addEventListener("message", (event) => {
        if (!isCurrent()) return;
        try {
          const data = JSON.parse(event.data) as Record<string, unknown>;
          const msgType = data.type as string;

          if (msgType === "pong") {
            this.lastPongTime = Date.now();
            if (this.pingSentAt > 0) {
              this.currentLatencyMs = this.lastPongTime - this.pingSentAt;
              this.pingSentAt = 0;
              this.latencyWindow.push(this.currentLatencyMs);
              if (this.latencyWindow.length > this.LATENCY_WINDOW_SIZE) {
                this.latencyWindow.shift();
              }
            }
            return;
          }

          if (msgType === "session.info" || msgType === "sync.registered") {
            this.authenticated = true;
            clearTimeout(timeout);
            this.pendingAuthResolve?.();
            this.pendingAuthResolve = null;
            this.setState("connected");
            this.startHeartbeat();
            this.flushPendingMessages();
          }

          this.dispatchEvent(msgType, data);

          if (!this.chatCallbacks) return;

          if (msgType === "chat.status") {
            this.chatCallbacks.onStatus?.(
              String(data.message_id || ""),
              String(data.status || ""),
              data.detail as string | undefined,
            );
          } else if (msgType === "chat.token") {
            this.chatCallbacks.onToken(data.message_id as string, data.content as string);
          } else if (msgType === "chat.done") {
            this.clearActiveRequest(data.message_id as string);
            this.chatCallbacks.onDone(data.message_id as string, data.conversation_id as string | undefined);
          } else if (msgType === "chat.error") {
            this.clearActiveRequest((data.message_id as string) || null);
            this.chatCallbacks.onError((data.message_id as string | null) || null, data.error as string);
          }
        } catch {
          /* ignore parse errors */
        }
      });

      socket.addEventListener("close", () => {
        if (!isCurrent()) return;
        clearTimeout(timeout);
        this.authenticated = false;
        this.isConnecting = false;
        this.stopHeartbeat();
        this.ws = null;
        this.setState(this.disconnected ? "disconnected" : "reconnecting");
        if (this.activeRequestIds.size > 0) {
          const ids = [...this.activeRequestIds.keys()];
          this.activeRequestIds.clear();
          for (const id of ids) {
            this.chatCallbacks?.onError(id, "Connection lost while waiting for a response.");
          }
        }
        this.handleDisconnect();
      });

      socket.addEventListener("error", () => {
        if (!isCurrent()) return;
        clearTimeout(timeout);
        this.isConnecting = false;
        this.pendingAuthReject?.(new Error("WebSocket connection error"));
        this.pendingAuthReject = null;
        // close handler performs reconnect; do not double-schedule
      });
    });

    return this.authPromise.catch((err) => {
      if (this.socketGeneration === generation) {
        this.handleDisconnect();
      }
      throw err;
    });
  }

  setChatCallbacks(callbacks: WSChatCallbacks): void {
    this.chatCallbacks = callbacks;
  }

  on(eventType: string, handler: WSEventHandler): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(handler);
  }

  off(eventType: string, handler: WSEventHandler): void {
    this.eventHandlers.get(eventType)?.delete(handler);
  }

  send(data: Record<string, unknown>): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(data));
    return true;
  }

  sendOrchestratorRun(task: string, runId?: string): boolean {
    const id = runId || `orch_${Date.now()}`;
    return this.send({ type: "orchestrator.run", task, run_id: id });
  }

  sendChatMessage(messageId: string, content: string, conversationId?: string, agentMode?: string): boolean {
    // Set up request timeout
    const timeout = setTimeout(() => {
      if (this.activeRequestIds.has(messageId)) {
        this.activeRequestIds.delete(messageId);
        this.chatCallbacks?.onError(messageId, "Request timeout - no response received within expected time.");
      }
    }, this.REQUEST_TIMEOUT);

    this.activeRequestIds.set(messageId, { timestamp: Date.now(), timeout });

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "chat.send",
          conversation_id: conversationId || null,
          message_id: messageId,
          content,
          agent_mode: agentMode || "general",
        }),
      );
      return true;
    }
    this.pendingMessages.push({ conversationId: conversationId || null, messageId, content });
    if (!this.isConnecting && !this.disconnected) {
      void this.connect();
    }
    return true;
  }

  sendVoiceSTT(requestId: string, audioBase64: string): boolean {
    return this.send({
      type: "voice.stt",
      request_id: requestId,
      audio_base64: audioBase64,
    });
  }

  sendCommand(command: string, payload: Record<string, unknown> = {}, commandId?: string): boolean {
    return this.send({
      type: "command",
      command,
      command_id: commandId || `cmd_${Date.now()}`,
      payload,
    });
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN && this.authenticated;
  }

  hasActiveRequest(): boolean {
    return this.activeRequestIds.size > 0;
  }

  clearActiveRequest(messageId: string | null): void {
    if (messageId) {
      const request = this.activeRequestIds.get(messageId);
      if (request) {
        clearTimeout(request.timeout);
        this.activeRequestIds.delete(messageId);
      }
    } else {
      // Clear all requests and their timeouts
      for (const [id, request] of this.activeRequestIds) {
        clearTimeout(request.timeout);
      }
      this.activeRequestIds.clear();
    }
  }

  disconnect(): void {
    this.disconnected = true;
    this.authenticated = false;
    this.isConnecting = false;
    this.socketGeneration += 1;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopHeartbeat();
    if (this.pendingSendTimer) {
      clearTimeout(this.pendingSendTimer);
      this.pendingSendTimer = null;
    }
    if (this.ws) {
      const socket = this.ws;
      this.ws = null;
      try {
        socket.close();
      } catch {
        /* ignore */
      }
    }
    this.setState("disconnected");
  }

  private dispatchEvent(eventType: string, data: Record<string, unknown>): void {
    this.eventHandlers.get(eventType)?.forEach((handler) => {
      try {
        handler(data);
      } catch {
        /* ignore handler errors */
      }
    });
  }

  private handleDisconnect(): void {
    if (this.disconnected) return;
    if (this.reconnectTimer) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;

    this.reconnectAttempts += 1;
    const delay = Math.min(
      this.baseReconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1),
      this.maxReconnectDelay,
    );
    this.setState("reconnecting");
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.disconnected) {
        this.connect().catch(() => {
          /* handleDisconnect via close/error */
        });
      }
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.lastPongTime = Date.now();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.pingSentAt = Date.now();
        try {
          this.ws.send(JSON.stringify({ type: "ping" }));
        } catch {
          /* closing */
        }
      }
      const threshold = this.activeRequestIds.size > 0 ? this.ACTIVE_STALE_THRESHOLD : this.STALE_THRESHOLD;
      const timeSinceLastPong = Date.now() - this.lastPongTime;
      if (timeSinceLastPong > threshold) {
        console.warn(
          `[WsClient] Connection stale (no pong for ${Math.round(timeSinceLastPong / 1000)}s), reconnecting...`,
        );
        // Always mark active requests as errored before closing, regardless of how long they've been active
        if (this.activeRequestIds.size > 0) {
          const ids = [...this.activeRequestIds.keys()];
          this.activeRequestIds.clear();
          for (const id of ids) {
            this.chatCallbacks?.onError(id, "Connection stale while waiting for a response.");
          }
        }
        this.ws?.close();
      }
    }, this.HEARTBEAT_INTERVAL);
  }

  getLatency(): number {
    return this.currentLatencyMs;
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  sendChat(conversationId: string | null, messageId: string, content: string): boolean {
    return this.sendChatMessage(messageId, content, conversationId || undefined);
  }

  private flushPendingMessages(): void {
    if (this.pendingMessages.length === 0) return;
    const messages = [...this.pendingMessages];
    this.pendingMessages = [];
    let idx = 0;
    const sendNext = () => {
      if (idx >= messages.length) return;
      const msg = messages[idx++];
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(
          JSON.stringify({
            type: "chat.send",
            conversation_id: msg.conversationId || undefined,
            message_id: msg.messageId,
            content: msg.content,
          }),
        );
      }
      this.pendingSendTimer = setTimeout(sendNext, 50);
    };
    sendNext();
  }
}

let _instance: WsClient | null = null;

export function getWsClient(): WsClient {
  if (!_instance) {
    _instance = new WsClient();
  }
  return _instance;
}

export function resetWsClient(): void {
  if (_instance) {
    _instance.disconnect();
    _instance = null;
  }
}