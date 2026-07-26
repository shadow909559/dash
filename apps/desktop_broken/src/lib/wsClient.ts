/**
 * WebSocket client for DASH real-time chat.
 *
 * Protocol:
 *   client -> server: { type: "auth", access_token: "..." }
 *   server -> client: { type: "session.info", session_id, client_id, ... }
 *   client -> server: { type: "chat.send", conversation_id?: string, message_id: string, content: string }
 *   server -> client: { type: "chat.token", message_id: string, content: string }
 *   server -> client: { type: "chat.done", message_id: string, conversation_id?: string }
 *   server -> client: { type: "chat.error", message_id?: string, error: string }
 */

type WSEventHandler = (data: Record<string, unknown>) => void;

export interface WSChatCallbacks {
  onToken: (messageId: string, token: string) => void;
  onDone: (messageId: string, conversationId?: string) => void;
  onError: (messageId: string | null, error: string) => void;
}

export class WsClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private disconnected = false;
  private authenticated = false;
  private pendingAuthResolve: (() => void) | null = null;
  private authPromise: Promise<void> | null = null;
  private eventHandlers = new Map<string, Set<WSEventHandler>>();
  private chatCallbacks: WSChatCallbacks | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(url?: string) {
    this.url = url || "ws://127.0.0.1:8000/api/v1/ws";
  }

  /**
   * Connect to the WebSocket server and authenticate.
   * Returns a promise that resolves when authentication succeeds.
   */
  async connect(): Promise<void> {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return this.authPromise || Promise.resolve();
    }

    this.disconnected = false;
    this.authenticated = false;

    const token = localStorage.getItem("dash_access_token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    this.ws = new WebSocket(this.url);

    this.authPromise = new Promise<void>((resolve, reject) => {
      this.pendingAuthResolve = resolve;

      const timeout = setTimeout(() => {
        reject(new Error("WebSocket authentication timeout"));
      }, 10000);

      this.ws!.addEventListener("open", () => {
        // Send auth message immediately on connect
        this.ws!.send(JSON.stringify({ type: "auth", access_token: token }));
      });

      this.ws!.addEventListener("message", (event) => {
        try {
          const data = JSON.parse(event.data) as Record<string, unknown>;
          const msgType = data.type as string;

          // Handle auth response
          if (msgType === "session.info" || msgType === "sync.registered") {
            this.authenticated = true;
            clearTimeout(timeout);
            if (this.pendingAuthResolve) {
              this.pendingAuthResolve();
              this.pendingAuthResolve = null;
            }
            return;
          }

          // Handle auth error
          if (msgType === "chat.error" && data.error && String(data.error).includes("Auth")) {
            clearTimeout(timeout);
            reject(new Error(String(data.error)));
            return;
          }

          // Handle pong
          if (msgType === "pong") return;

          // Dispatch to registered handlers
          this.dispatchEvent(msgType, data);

          // Forward chat events to callbacks
          if (this.chatCallbacks) {
            if (msgType === "chat.token") {
              this.chatCallbacks.onToken(
                data.message_id as string,
                data.content as string
              );
            } else if (msgType === "chat.done") {
              this.chatCallbacks.onDone(
                data.message_id as string,
                data.conversation_id as string | undefined
              );
            } else if (msgType === "chat.error") {
              this.chatCallbacks.onError(
                (data.message_id as string | null) || null,
                data.error as string
              );
            }
          }
        } catch {
          // Ignore parse errors
        }
      });

      this.ws!.addEventListener("close", () => {
        clearTimeout(timeout);
        this.authenticated = false;
        this.handleDisconnect();
      });

      this.ws!.addEventListener("error", () => {
        clearTimeout(timeout);
        this.authenticated = false;
        this.handleDisconnect();
      });
    });

    return this.authPromise;
  }

  /**
   * Set callbacks for chat message streaming.
   */
  setChatCallbacks(callbacks: WSChatCallbacks): void {
    this.chatCallbacks = callbacks;
  }

  /**
   * Register a handler for a specific message type.
   */
  on(eventType: string, handler: WSEventHandler): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(handler);
  }

  /**
   * Remove a handler for a specific message type.
   */
  off(eventType: string, handler: WSEventHandler): void {
    this.eventHandlers.get(eventType)?.delete(handler);
  }

  /**
   * Send a chat message via WebSocket.
   */
  sendChat(conversationId: string | null, messageId: string, content: string): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }

    this.ws.send(
      JSON.stringify({
        type: "chat.send",
        conversation_id: conversationId || undefined,
        message_id: messageId,
        content,
      })
    );
    return true;
  }

  /**
   * Send a raw JSON message.
   */
  send(data: Record<string, unknown>): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }
    this.ws.send(JSON.stringify(data));
    return true;
  }

  /**
   * Check if connected and authenticated.
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN && this.authenticated;
  }

  /**
   * Disconnect the WebSocket.
   */
  disconnect(): void {
    this.disconnected = true;
    this.authenticated = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private dispatchEvent(eventType: string, data: Record<string, unknown>): void {
    this.eventHandlers.get(eventType)?.forEach((handler) => {
      try {
        handler(data);
      } catch {
        // Ignore handler errors
      }
    });
  }

  private handleDisconnect(): void {
    if (this.disconnected) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;

    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1),
      30000
    );

    this.reconnectTimer = setTimeout(() => {
      if (!this.disconnected) {
        this.connect().catch(() => {
          // Reconnect failures are handled by handleDisconnect
        });
      }
    }, delay);
  }
}

/**
 * Singleton WebSocket client instance.
 */
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

