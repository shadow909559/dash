import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Mic,
  MicOff,
  Send,
  Settings,
  Monitor,
  Brain,
  Zap,
  Volume2,
  Wifi,
  WifiOff,
  Clock,
  Activity,
} from "lucide-react";
import { useAIStore } from "@/stores/aiStore";
import { useChatStore } from "@/stores/chatStore";
import { useActivityStore } from "@/stores/activityStore";
import Orb from "@/components/Orb";

/**
 * DASH Home — Orb-first experience.
 * Large animated Orb centered, minimal HUD, command input below.
 */
export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const {
    dashState,
    systemStatus,
    aiProviderStatus,
    websocketStatus,
    systemStats,
  } = useAIStore();
  const { input, setInput, sendMessage, isProcessing, messages } =
    useChatStore();
  const { items: activities } = useActivityStore();
  const [currentTime, setCurrentTime] = useState(new Date());
  const [isListening, setIsListening] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const getStateLabel = () => {
    if (websocketStatus === "disconnected") return "DASH OFFLINE";
    if (websocketStatus === "connecting" || websocketStatus === "reconnecting")
      return "CONNECTING...";
    if (isProcessing) return "THINKING...";
    if (dashState === "listening") return "LISTENING";
    if (dashState === "speaking") return "SPEAKING";
    if (dashState === "executing") return "EXECUTING";
    if (aiProviderStatus === "error") return "SYSTEM ERROR";
    return "DASH ONLINE";
  };

  const getStateColor = () => {
    if (websocketStatus === "disconnected") return "#6b7280";
    if (isProcessing) return "#dc2626";
    if (dashState === "listening") return "#f97316";
    if (dashState === "speaking") return "#ef4444";
    if (aiProviderStatus === "error") return "#dc2626";
    return "#dc2626";
  };

  const handleSend = useCallback(() => {
    if (!input.trim() || isProcessing) return;
    sendMessage();
  }, [input, isProcessing, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleVoice = () => {
    setIsListening((prev) => !prev);
  };

  // Get the last assistant message
  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        boxSizing: "border-box",
        overflow: "hidden",
        position: "relative",
        background: "var(--dash-bg)",
      }}
    >
      {/* ─── HUD Grid Background ─── */}
      <div
        className="dash-hud-grid"
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.4,
          pointerEvents: "none",
        }}
      />

      {/* ─── Scanline effect ─── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 1,
          background:
            "linear-gradient(90deg, transparent, rgba(220,38,38,0.15), transparent)",
          animation: "scanLine 8s linear infinite",
          pointerEvents: "none",
        }}
      />

      {/* ─── Top Status Bar ─── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 24px",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: getStateColor(),
              boxShadow: `0 0 8px ${getStateColor()}`,
              animation:
                websocketStatus === "connected" && !isProcessing
                  ? "statusPulse 3s ease-in-out infinite"
                  : undefined,
            }}
          />
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: "0.12em",
              color: getStateColor(),
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {getStateLabel()}
          </span>
        </div>

        <div
          style={{
            fontSize: 10,
            color: "var(--dash-text-muted)",
            fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: "0.05em",
          }}
        >
          {currentTime.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </div>
      </div>

      {/* ─── System HUD Indicators (top-right) ─── */}
      <div
        style={{
          position: "absolute",
          top: 44,
          right: 24,
          display: "flex",
          flexDirection: "column",
          gap: 6,
          zIndex: 10,
        }}
      >
        {[
          {
            icon: Monitor,
            label: "BACKEND",
            ok: systemStatus === "online",
          },
          {
            icon: Brain,
            label: "LLM",
            ok: aiProviderStatus !== "offline" && aiProviderStatus !== "error",
          },
          {
            icon: Wifi,
            label: "WS",
            ok: websocketStatus === "connected",
          },
          {
            icon: Activity,
            label: "TOOLS",
            ok: aiProviderStatus !== "error",
          },
        ].map(({ icon: Icon, label, ok }) => (
          <div
            key={label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 9,
              fontFamily: "'JetBrains Mono', monospace",
              color: ok ? "var(--dash-success)" : "var(--dash-danger)",
              letterSpacing: "0.06em",
              opacity: 0.7,
            }}
          >
            <Icon size={10} />
            <span>{label}</span>
            <div
              style={{
                width: 4,
                height: 4,
                borderRadius: "50%",
                background: ok ? "var(--dash-success)" : "var(--dash-danger)",
              }}
            />
          </div>
        ))}
      </div>

      {/* ─── Center: Orb + Branding ─── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
          zIndex: 5,
        }}
      >
        {/* Brand label */}
        <div
          style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.25em",
            color: "var(--ultron-text)",
            textTransform: "uppercase",
            opacity: 0.6,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          DASH CORE
        </div>

        {/* Orb */}
        <div onClick={toggleVoice} style={{ position: "relative" }}>
          <Orb />
        </div>

        {/* Status */}
        <div
          style={{
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: "0.15em",
            color: getStateColor(),
            fontFamily: "'JetBrains Mono', monospace",
            textTransform: "uppercase",
            opacity: 0.8,
          }}
        >
          {getStateLabel()}
        </div>
      </div>

      {/* ─── Last Response Display ─── */}
      {lastMessage && lastMessage.role === "assistant" && (
        <div
          style={{
            position: "absolute",
            bottom: 160,
            left: "50%",
            transform: "translateX(-50%)",
            maxWidth: 600,
            textAlign: "center",
            zIndex: 5,
          }}
        >
          <div
            style={{
              fontSize: 13,
              color: "var(--dash-text-secondary)",
              lineHeight: 1.5,
              opacity: 0.7,
              maxHeight: 60,
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {lastMessage.content.slice(0, 120)}
            {lastMessage.content.length > 120 ? "..." : ""}
          </div>
        </div>
      )}

      {/* ─── Command Input ─── */}
      <div
        style={{
          position: "absolute",
          bottom: 60,
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          alignItems: "center",
          gap: 10,
          width: "min(520px, 85vw)",
          zIndex: 10,
        }}
      >
        {/* Voice button */}
        <button
          onClick={toggleVoice}
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            border: `1px solid ${isListening ? "var(--ultron-core)" : "var(--dash-border)"}`,
            background: isListening
              ? "var(--ultron-surface)"
              : "var(--dash-surface)",
            color: isListening
              ? "var(--ultron-core-bright)"
              : "var(--dash-text-muted)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            flexShrink: 0,
            transition: "all 0.2s",
            boxShadow: isListening ? "0 0 16px var(--ultron-glow)" : undefined,
          }}
          title="Toggle voice input"
        >
          {isListening ? <Mic size={18} /> : <MicOff size={16} />}
        </button>

        {/* Text input */}
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            background: "var(--dash-surface)",
            border: "1px solid var(--dash-border)",
            borderRadius: 24,
            padding: "0 16px",
            height: 44,
          }}
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask DASH anything..."
            aria-label="Ask DASH anything"
            disabled={isProcessing}
            style={{
              flex: 1,
              background: "none",
              border: "none",
              outline: "none",
              color: "var(--dash-text)",
              fontSize: 13,
              fontFamily: "Inter, sans-serif",
              letterSpacing: "0.01em",
            }}
          />
        </div>

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!input.trim() || isProcessing}
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            border: "1px solid var(--ultron-border)",
            background:
              input.trim() && !isProcessing
                ? "var(--ultron-surface-hover)"
                : "var(--dash-surface)",
            color:
              input.trim() && !isProcessing
                ? "var(--ultron-core-bright)"
                : "var(--dash-text-muted)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: input.trim() && !isProcessing ? "pointer" : "default",
            flexShrink: 0,
            transition: "all 0.2s",
          }}
          title="Send message"
        >
          <Send size={16} />
        </button>
      </div>

      {/* ─── Bottom Navigation Shortcuts ─── */}
      <div
        style={{
          position: "absolute",
          bottom: 16,
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          gap: 20,
          zIndex: 10,
        }}
      >
        {[
          { label: "Chat", path: "/chat" },
          { label: "Memory", path: "/memory" },
          { label: "System", path: "/system-monitor" },
          { label: "Settings", path: "/settings" },
        ].map(({ label, path }) => (
          <button
            key={path}
            onClick={() => navigate(path)}
            style={{
              background: "none",
              border: "none",
              color: "var(--dash-text-muted)",
              fontSize: 10,
              fontWeight: 500,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              cursor: "pointer",
              padding: "4px 8px",
              borderRadius: 4,
              transition: "all 0.2s",
              fontFamily: "'JetBrains Mono', monospace",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--ultron-text)";
              e.currentTarget.style.background = "var(--ultron-surface)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--dash-text-muted)";
              e.currentTarget.style.background = "none";
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ─── Activity Log (bottom-left, subtle) ─── */}
      {activities.length > 0 && (
        <div
          style={{
            position: "absolute",
            bottom: 16,
            left: 24,
            display: "flex",
            flexDirection: "column",
            gap: 3,
            zIndex: 10,
          }}
        >
          {activities.slice(-3).map((item, i) => (
            <div
              key={i}
              style={{
                fontSize: 9,
                color: "var(--dash-text-muted)",
                fontFamily: "'JetBrains Mono', monospace",
                opacity: 0.4,
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <div
                style={{
                  width: 3,
                  height: 3,
                  borderRadius: "50%",
                  background:
                    item.kind === "error"
                      ? "var(--dash-danger)"
                      : item.kind === "ai"
                        ? "var(--ultron-core)"
                        : "var(--dash-text-muted)",
                }}
              />
              {item.message}
            </div>
          ))}
        </div>
      )}

      {/* ─── System stats (bottom-right, subtle) ─── */}
      {systemStats && (
        <div
          style={{
            position: "absolute",
            bottom: 16,
            right: 24,
            display: "flex",
            gap: 16,
            zIndex: 10,
          }}
        >
          {[
            { label: "CPU", value: systemStats.cpu },
            { label: "RAM", value: systemStats.ram },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{
                fontSize: 9,
                color: "var(--dash-text-muted)",
                fontFamily: "'JetBrains Mono', monospace",
                opacity: 0.4,
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {label}: {value.toFixed(0)}%
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default HomePage;
