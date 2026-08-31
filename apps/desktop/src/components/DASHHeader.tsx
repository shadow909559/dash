import React, { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAIStore } from "@/stores/aiStore";
import { initializeWebSocket } from "@/lib/ws";
import { Cpu, Wifi, Minus, Square, Copy, X, RefreshCw, WifiOff } from "lucide-react";

interface DASHHeaderProps {
  sidebarExpanded?: boolean;
}

export const DASHHeader: React.FC<DASHHeaderProps> = () => {
  const location = useLocation();
  const [isMaximized, setIsMaximized] = useState(false);
  const { systemStatus, websocketStatus, aiProviderStatus, dashState } = useAIStore();
  const [retrying, setRetrying] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  // Reset dismiss when status recovers
  useEffect(() => {
    if (websocketStatus === "connected") setBannerDismissed(false);
  }, [websocketStatus]);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      initializeWebSocket();
      // Give it a moment to connect
      await new Promise((resolve) => setTimeout(resolve, 2000));
    } finally {
      setRetrying(false);
    }
  };

  useEffect(() => {
    const initMaximizeState = async () => {
      try {
        const maximized = await window.electronAPI?.window?.isMaximized();
        setIsMaximized(!!maximized);
      } catch {
        // Fallback if not in Electron
      }
    };
    initMaximizeState();

    let unsubscribe: (() => void) | null = null;
    try {
      unsubscribe = window.electronAPI?.window?.onMaximizeChange?.((maximized: boolean) => {
        setIsMaximized(maximized);
      }) ?? null;
    } catch {
      // Ignore
    }

    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, []);

  const handleMinimize = async () => {
    try {
      await window.electronAPI?.window?.minimize();
    } catch (e) {
      console.warn("Minimize not available", e);
    }
  };

  const handleMaximize = async () => {
    try {
      await window.electronAPI?.window?.maximize();
    } catch (e) {
      console.warn("Maximize not available", e);
    }
  };

  const handleClose = async () => {
    try {
      await window.electronAPI?.window?.close();
    } catch (e) {
      console.warn("Close not available", e);
    }
  };

  // Convert pathname to title
  const getPageTitle = (path: string) => {
    const clean = path.replace("/", "").toLowerCase();
    if (!clean || clean === "home") return "Dashboard";
    return clean.charAt(0).toUpperCase() + clean.slice(1);
  };

  const getStatusColor = (status: string) => {
    if (status === "online" || status === "connected" || status === "ready") return "var(--dash-success)";
    if (status === "connecting" || status === "reconnecting" || status === "thinking") return "var(--dash-warning)";
    return "var(--dash-danger)";
  };

  const showBanner = websocketStatus !== "connected" && !bannerDismissed;

  return (
    <>
    <header
      role="banner"
      aria-label="DASH status bar"
      className="dash-jarvis-header"
      style={{
        height: 48,
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 16px",
        borderBottom: showBanner ? "none" : undefined,
        WebkitAppRegion: "drag",
        userSelect: "none",
        zIndex: 40,
      } as React.CSSProperties}
    >
      {/* Left: Breadcrumb / Page Title */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--dash-text)",
            letterSpacing: "-0.01em",
          }}
        >
          {getPageTitle(location.pathname)}
        </span>
        <span
          style={{
            fontSize: 11,
            padding: "2px 8px",
            borderRadius: "var(--dash-radius-full)",
            backgroundColor: "rgba(255, 255, 255, 0.05)",
            color: "var(--dash-text-muted)",
            border: "1px solid var(--dash-border-subtle)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {dashState}
        </span>
      </div>

      {/* Center / Right: System & AI Connection Indicators */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          WebkitAppRegion: "no-drag",
        } as React.CSSProperties}
      >
        {/* Connection status pills */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Backend Status */}
          <div
            title={`Backend: ${systemStatus}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11,
              color: "var(--dash-text-secondary)",
            }}
          >
            <div
              style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              backgroundColor: getStatusColor(systemStatus),
              boxShadow: systemStatus === "online" ? "0 0 8px rgba(34, 197, 94, 0.5)" : "0 0 8px rgba(239, 68, 68, 0.4)",
              animation: systemStatus === "online" ? "jarvis-status-pulse 2s ease-in-out infinite" : "none",
              }}
            />
            <span>Core</span>
          </div>

          {/* AI Provider Status */}
          <div
            title={`AI Provider: ${aiProviderStatus}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11,
              color: "var(--dash-text-secondary)",
            }}
          >
            <Cpu size={12} style={{ color: getStatusColor(aiProviderStatus) }} />
            <span>AI</span>
          </div>

          {/* WebSocket Status */}
          <div
            title={`WebSocket: ${websocketStatus}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11,
              color: "var(--dash-text-secondary)",
            }}
          >
            <Wifi size={12} style={{ color: getStatusColor(websocketStatus) }} />
            <span>WS</span>
          </div>
        </div>

        <div style={{ width: 1, height: 16, backgroundColor: "var(--dash-border)" }} />

        {/* Window controls */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 2,
          }}
        >
          <button
            onClick={handleMinimize}
            title="Minimize"
            aria-label="Minimize"
            style={{
              width: 32,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              borderRadius: "var(--dash-radius-xs)",
              color: "var(--dash-text-secondary)",
              cursor: "pointer",
              transition: "all var(--dash-transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)";
              e.currentTarget.style.color = "var(--dash-text)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "transparent";
              e.currentTarget.style.color = "var(--dash-text-secondary)";
            }}
          >
            <Minus size={14} />
          </button>

          <button
            onClick={handleMaximize}
            title={isMaximized ? "Restore" : "Maximize"}
            aria-label={isMaximized ? "Restore" : "Maximize"}
            style={{
              width: 32,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              borderRadius: "var(--dash-radius-xs)",
              color: "var(--dash-text-secondary)",
              cursor: "pointer",
              transition: "all var(--dash-transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)";
              e.currentTarget.style.color = "var(--dash-text)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "transparent";
              e.currentTarget.style.color = "var(--dash-text-secondary)";
            }}
          >
            {isMaximized ? <Copy size={12} /> : <Square size={12} />}
          </button>

          <button
            onClick={handleClose}
            title="Close"
            aria-label="Close"
            style={{
              width: 32,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              borderRadius: "var(--dash-radius-xs)",
              color: "var(--dash-text-secondary)",
              cursor: "pointer",
              transition: "all var(--dash-transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "rgba(63, 169, 245, 0.2)";
              e.currentTarget.style.color = "var(--dash-danger)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "transparent";
              e.currentTarget.style.color = "var(--dash-text-secondary)";
            }}
          >
            <X size={14} />
          </button>
        </div>
      </div>
    </header>
      {/* ─── Reconnection Banner ─── */}
      {websocketStatus !== "connected" && !bannerDismissed && (
        <div
          role="alert"
          aria-live="assertive"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            padding: "6px 16px",
            backgroundColor:
              websocketStatus === "disconnected"
                ? "rgba(63, 169, 245, 0.10)"
                : "rgba(234, 179, 8, 0.08)",
            borderBottom: `1px solid ${
              websocketStatus === "disconnected"
                ? "rgba(63, 169, 245, 0.25)"
                : "rgba(234, 179, 8, 0.20)"
            }`,
            width: "100%",
            WebkitAppRegion: "no-drag",
            animation: "fadeIn 0.2s ease",
          } as React.CSSProperties}
        >
          {websocketStatus === "disconnected" ? (
            <WifiOff size={12} style={{ color: "var(--dash-danger)" }} />
          ) : (
            <RefreshCw
              size={12}
              className={retrying ? "animate-rotate" : undefined}
              style={{ color: "var(--dash-warning)" }}
            />
          )}
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              color:
                websocketStatus === "disconnected"
                  ? "var(--dash-danger)"
                  : "var(--dash-warning)",
              fontFamily: "'JetBrains Mono', monospace",
              letterSpacing: "0.03em",
            }}
          >
            {websocketStatus === "disconnected"
              ? "Backend disconnected"
              : retrying
                ? "Reconnecting..."
                : "Connection lost — attempting to reconnect"}
          </span>

          {/* Retry button (only when fully disconnected) */}
          {websocketStatus === "disconnected" && (
            <button
              onClick={handleRetry}
              disabled={retrying}
              aria-label="Retry connection"
              style={{
                padding: "3px 10px",
                borderRadius: "var(--dash-radius-sm)",
                border: "1px solid rgba(63, 169, 245, 0.3)",
                background: retrying
                  ? "rgba(63, 169, 245, 0.05)"
                  : "rgba(63, 169, 245, 0.12)",
                color: retrying
                  ? "var(--dash-text-muted)"
                  : "var(--dash-danger)",
                cursor: retrying ? "default" : "pointer",
                fontSize: 11,
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: 5,
                transition: "all var(--dash-transition-fast)",
                opacity: retrying ? 0.6 : 1,
              }}
            >
              <RefreshCw
                size={10}
                className={retrying ? "animate-rotate" : undefined}
              />
              {retrying ? "Retrying..." : "Retry"}
            </button>
          )}

          {/* Dismiss button (auto-reconnecting only) */}
          {websocketStatus === "reconnecting" && (
            <button
              onClick={() => setBannerDismissed(true)}
              aria-label="Dismiss"
              style={{
                padding: "3px 8px",
                borderRadius: "var(--dash-radius-sm)",
                border: "1px solid rgba(234, 179, 8, 0.2)",
                background: "transparent",
                color: "var(--dash-text-muted)",
                cursor: "pointer",
                fontSize: 10,
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <X size={10} />
              Dismiss
            </button>
          )}
        </div>
      )}
    </>
  );
};

export default DASHHeader;
