import { useEffect, useState } from "react";
import { getWsClient, ConnectionState } from "@/lib/wsClient";
import { authFetch } from "@/lib/api";
import { useAIStore } from "@/stores/aiStore";
import { useActivityStore } from "@/stores/activityStore";
import type { SystemStatus, AIProviderStatus, WebSocketStatus, ChatStatus, VoiceStatus } from "@/stores/aiStore";

type ProviderStatus = "checking" | "starting" | "ready" | "model_missing" | "unavailable" | "error";

interface ProviderHealth {
  status?: ProviderStatus;
  healthy?: boolean;
  provider: string;
  configured_model: string | null;
  model_available: boolean;
  installed_models: string[];
  error: string | null;
  latency_ms: number | null;
  message?: string;
}

const API_ORIGIN = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1").replace(/\/api\/v1$/, "");

// Map connection states to store statuses
const mapWsConnectionToStore = (state: ConnectionState): WebSocketStatus => {
  switch (state) {
    case "connecting": return "connecting";
    case "connected": return "connected";
    case "reconnecting": return "reconnecting";
    case "disconnected": return "disconnected";
    default: return "disconnected";
  }
};

// Helper to get label and color for each status type
const getSystemStatusConfig = (status: SystemStatus) => {
  return status === "online" 
    ? { label: "SYSTEM ONLINE", color: "rgba(0, 255, 220, 0.95)" }
    : { label: "SYSTEM OFFLINE", color: "rgba(255, 90, 70, 0.95)" };
};

const getAIProviderStatusConfig = (status: AIProviderStatus) => {
  switch (status) {
    case "thinking": return { label: "AI ENGINE THINKING", color: "rgba(167, 139, 250, 0.95)" };
    case "responding": return { label: "AI ENGINE RESPONDING", color: "rgba(96, 165, 250, 0.95)" };
    case "ready": return { label: "AI ENGINE READY", color: "rgba(0, 255, 220, 0.95)" };
    case "error": return { label: "AI ENGINE ERROR", color: "rgba(255, 90, 70, 0.95)" };
    default: return { label: "AI ENGINE OFFLINE", color: "rgba(255, 90, 70, 0.95)" };
  }
};

const getWebSocketStatusConfig = (status: WebSocketStatus) => {
  switch (status) {
    case "connected": return { label: "CONNECTION CONNECTED", color: "rgba(0, 255, 220, 0.95)" };
    case "reconnecting": return { label: "CONNECTION RECONNECTING", color: "rgba(251, 191, 36, 0.95)" };
    case "connecting": return { label: "CONNECTION CONNECTING", color: "rgba(251, 191, 36, 0.95)" };
    default: return { label: "CONNECTION DISCONNECTED", color: "rgba(255, 90, 70, 0.95)" };
  }
};

const getChatStatusConfig = (status: ChatStatus) => {
  switch (status) {
    case "processing": return { label: "CHAT PROCESSING", color: "rgba(167, 139, 250, 0.95)" };
    case "idle": return { label: "CHAT IDLE", color: "rgba(0, 255, 220, 0.95)" };
    default: return { label: "CHAT ERROR", color: "rgba(255, 90, 70, 0.95)" };
  }
};

const getVoiceStatusConfig = (status: VoiceStatus) => {
  switch (status) {
    case "listening": return { label: "VOICE LISTENING", color: "rgba(74, 222, 128, 0.95)" };
    case "speaking": return { label: "VOICE SPEAKING", color: "rgba(74, 222, 128, 0.95)" };
    case "ready": return { label: "VOICE READY", color: "rgba(0, 255, 220, 0.95)" };
    case "error": return { label: "VOICE ERROR", color: "rgba(255, 90, 70, 0.95)" };
    default: return { label: "VOICE OFFLINE", color: "rgba(255, 90, 70, 0.95)" };
  }
};

export default function AIStatusIndicator() {
  const [health, setHealth] = useState<ProviderHealth>({
    provider: "ollama",
    configured_model: null,
    model_available: false,
    installed_models: [],
    error: null,
    latency_ms: null,
  });
  
  const { 
    systemStatus,
    aiProviderStatus, 
    websocketStatus,
    chatStatus,
    voiceStatus,
    setSystemStatus,
    setAIProviderStatus, 
    setWebSocketStatus,
    setChatStatus,
    setVoiceStatus 
  } = useAIStore();

  useEffect(() => {
    const ws = getWsClient();
    
    // Subscribe to WebSocket connection status changes
    const handleWsStatusChange = (connected: boolean, authenticated: boolean, state: ConnectionState) => {
      setWebSocketStatus(mapWsConnectionToStore(state));
    };
    ws.onStatus(handleWsStatusChange);

    const handleProviderStatus = (data: Record<string, unknown>) => {
      setHealth(data as unknown as ProviderHealth);
      const status = String(data.status || "");
      if (status === "ready") {
        setSystemStatus("online");
        if (chatStatus === "idle") setAIProviderStatus("ready");
        useActivityStore.getState().push("AI engine ready", "ai");
      } else if (status === "checking" || status === "starting") {
        if (chatStatus === "idle") setAIProviderStatus("offline");
      } else if (status === "unavailable" || status === "error" || status === "model_missing") {
        setAIProviderStatus("error");
      }
    };

    ws.on("ai.provider.status", handleProviderStatus);

    // Subscribe to chat status events from WebSocket
    const handleChatStatus = (data: Record<string, unknown>) => {
      const status = String(data.status || "");
      if (status === "thinking") {
        setAIProviderStatus("thinking");
        setChatStatus("processing");
      } else if (status === "responding") {
        setAIProviderStatus("responding");
        setChatStatus("processing");
      } else if (status === "speaking") {
        setVoiceStatus("speaking");
        setChatStatus("processing");
      } else if (status === "done" || status === "idle") {
        setAIProviderStatus("ready");
        setChatStatus("idle");
        setVoiceStatus("ready");
      } else if (status === "error") {
        setAIProviderStatus("error");
        setChatStatus("error");
        setVoiceStatus("error");
      }
    };
    ws.on("chat.status", handleChatStatus);

    // Subscribe to voice status events
    const handleVoiceStatus = (data: Record<string, unknown>) => {
      const status = String(data.status || "");
      if (status === "listening") {
        setVoiceStatus("listening");
      } else if (status === "ready") {
        setVoiceStatus("ready");
      } else if (status === "error") {
        setVoiceStatus("error");
      }
    };
    ws.on("voice.status", handleVoiceStatus);

    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`${API_ORIGIN}/health`, { signal: AbortSignal.timeout(4000) });
        if (res.ok) {
          setSystemStatus("online");
        } else {
          setSystemStatus("offline");
        }
        
        const aiRes = await authFetch(`${API_ORIGIN}/health/ai-provider`, { signal: AbortSignal.timeout(4000) });
        if (!aiRes.ok || cancelled) return;
        const data = (await aiRes.json()) as ProviderHealth;
        setHealth(data);
        if (data.healthy || data.model_available) {
          if (useAIStore.getState().chatStatus === "idle" && useAIStore.getState().aiProviderStatus !== "thinking") {
            setAIProviderStatus("ready");
          }
        } else if (useAIStore.getState().chatStatus === "idle") {
          setAIProviderStatus("error");
        }
      } catch {
        setSystemStatus("offline");
        /* provider poll is best-effort */
      }
    };
    void poll();
    const timer = setInterval(poll, 15000);

    return () => {
      cancelled = true;
      clearInterval(timer);
      ws.off("ai.provider.status", handleProviderStatus);
      ws.off("chat.status", handleChatStatus);
      ws.off("voice.status", handleVoiceStatus);
    };
  }, [setAIProviderStatus, setWebSocketStatus, setChatStatus, setVoiceStatus, setSystemStatus, chatStatus]);

  // Get all status configs
  const systemConfig = getSystemStatusConfig(systemStatus);
  const aiConfig = getAIProviderStatusConfig(aiProviderStatus);
  const wsConfig = getWebSocketStatusConfig(websocketStatus);
  const chatConfig = getChatStatusConfig(chatStatus);
  const voiceConfig = getVoiceStatusConfig(voiceStatus);

  const statusItems = [
    { ...systemConfig, key: "system" },
    { ...aiConfig, key: "ai" },
    { ...wsConfig, key: "websocket" },
    { ...chatConfig, key: "chat" },
    { ...voiceConfig, key: "voice" },
  ];

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: "8px",
      padding: "12px",
      borderRadius: "8px",
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
      backgroundColor: "rgba(0, 0, 0, 0.6)",
      border: "1px solid rgba(0, 255, 255, 0.2)",
      boxShadow: "0 0 20px rgba(0, 255, 255, 0.1), 0 4px 16px rgba(0, 0, 0, 0.5)",
      minWidth: "180px",
    }}>
      {statusItems.map((item) => (
        <div key={item.key} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span 
            style={{ 
              width: "8px", 
              height: "8px", 
              borderRadius: "50%",
              backgroundColor: item.color, 
              boxShadow: `0 0 8px ${item.color}` 
            }}
          />
          <span style={{ 
            fontSize: "11px", 
            fontWeight: 500, 
            color: "rgba(255, 255, 255, 0.9)",
            letterSpacing: "0.5px",
            textTransform: "uppercase"
          }}>{item.label}</span>
        </div>
      ))}
    </div>
  );
}