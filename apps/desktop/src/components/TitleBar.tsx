/**
 * TitleBar — Minimal frameless window controls.
 * Thin bar at top with drag area + close/minimize/maximize.
 */
import React, { useState, useEffect } from "react";
import { Minus, Square, X, Copy } from "lucide-react";

export const TitleBar: React.FC = () => {
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    const init = async () => {
      try {
        const maximized = await window.electronAPI?.window?.isMaximized();
        setIsMaximized(!!maximized);
      } catch {}
    };
    init();

    let unsubscribe: (() => void) | null = null;
    try {
      unsubscribe = window.electronAPI?.window?.onMaximizeChange?.((maximized: boolean) => {
        setIsMaximized(maximized);
      }) ?? null;
    } catch {}
    return () => { unsubscribe?.(); };
  }, []);

  const handleMinimize = async () => {
    try { await window.electronAPI?.window?.minimize(); } catch {}
  };
  const handleMaximize = async () => {
    try { await window.electronAPI?.window?.maximize(); } catch {}
  };
  const handleClose = async () => {
    try { await window.electronAPI?.window?.close(); } catch {}
  };

  return (
    <div
      style={{
        height: 32,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "var(--dash-bg-subtle)",
        borderBottom: "1px solid var(--dash-border-subtle)",
        // @ts-ignore — Electron drag region
        WebkitAppRegion: "drag",
        flexShrink: 0,
        position: "relative",
        zIndex: 50,
      }}
    >
      {/* Drag area / brand */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          paddingLeft: 12,
          fontFamily: "'Orbitron', monospace",
          fontSize: 11,
          fontWeight: 600,
          color: "var(--dash-accent)",
          letterSpacing: "0.15em",
        }}
      >
        <span style={{ opacity: 0.6 }}>DASH</span>
      </div>

      {/* Window controls */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          height: "100%",
          // @ts-ignore — Electron drag region
          WebkitAppRegion: "no-drag",
        }}
      >
        <button
          onClick={handleMinimize}
          style={{
            width: 46,
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "transparent",
            border: "none",
            color: "var(--dash-text-muted)",
            cursor: "pointer",
            transition: "all 150ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.08)";
            e.currentTarget.style.color = "var(--dash-text)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--dash-text-muted)";
          }}
        >
          <Minus size={14} />
        </button>
        <button
          onClick={handleMaximize}
          style={{
            width: 46,
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "transparent",
            border: "none",
            color: "var(--dash-text-muted)",
            cursor: "pointer",
            transition: "all 150ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.08)";
            e.currentTarget.style.color = "var(--dash-text)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--dash-text-muted)";
          }}
        >
          {isMaximized ? <Copy size={12} /> : <Square size={12} />}
        </button>
        <button
          onClick={handleClose}
          style={{
            width: 46,
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "transparent",
            border: "none",
            color: "var(--dash-text-muted)",
            cursor: "pointer",
            transition: "all 150ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(239, 68, 68, 0.8)";
            e.currentTarget.style.color = "#fff";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--dash-text-muted)";
          }}
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
};
