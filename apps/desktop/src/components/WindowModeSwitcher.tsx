import { useState, useEffect } from "react";
import { useAIStore } from "@/stores/aiStore";

type WindowMode = "full" | "floating" | "orb";

export default function WindowModeSwitcher() {
  const { windowMode, setWindowMode } = useAIStore();
  const [currentMode, setCurrentMode] = useState<WindowMode>("full");

  useEffect(() => {
    const initMode = async () => {
      try {
        const mode = await window.electronAPI?.window?.getMode?.();
        if (mode === "full" || mode === "floating" || mode === "orb") {
          setCurrentMode(mode);
          setWindowMode(mode);
        }
      } catch {
        // Ignore if not in Electron
      }
    };
    initMode();
  }, [setWindowMode]);

  // Sync local state with store
  useEffect(() => {
    setCurrentMode(windowMode);
  }, [windowMode]);

  // Escape key handler - restore to full mode from compact modes
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && currentMode !== "full") {
        setMode("full");
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [currentMode]);

  const setMode = async (mode: WindowMode) => {
    try {
      // @ts-ignore
      await window.electronAPI?.window?.setMode(mode);
      setCurrentMode(mode);
      setWindowMode(mode);
    } catch {
      console.error("Failed to set window mode");
    }
  };

  const handleOrbClick = async () => {
    if (currentMode === "orb") {
      await setMode("full");
    }
  };

  return (
    <>
      {/* Orb click handler - invisible overlay when in orb mode */}
      {currentMode === "orb" && (
        <div
          onClick={handleOrbClick}
          style={{
            position: "fixed",
            inset: 0,
            cursor: "pointer",
            zIndex: 1,
          }}
          title="Click to expand to full mode"
        />
      )}

      {/* Restore button in orb mode - always visible */}
      {currentMode === "orb" && (
        <button
          onClick={handleOrbClick}
          style={{
            position: "fixed",
            bottom: 20,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "10px 20px",
            background: "rgba(8, 10, 14, 0.85)",
            border: "1px solid rgba(255, 150, 0, 0.4)",
            borderRadius: 20,
            color: "rgba(255, 179, 71, 0.9)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            transition: "all 0.2s ease",
            zIndex: 100,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255, 150, 0, 0.2)";
            e.currentTarget.style.borderColor = "rgba(255, 179, 71, 0.6)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "rgba(8, 10, 14, 0.85)";
            e.currentTarget.style.borderColor = "rgba(255, 150, 0, 0.4)";
          }}
        >
          Expand
        </button>
      )}

      {/* Mode switcher buttons - hide in orb mode */}
      {currentMode !== "orb" && (
        <div
          style={{
            position: "fixed",
            bottom: 20,
            left: 20,
            display: "flex",
            gap: 8,
            zIndex: 50,
          }}
        >
          <button
            onClick={() => setMode("full")}
            style={{
              padding: "8px 12px",
              background: currentMode === "full"
                ? "radial-gradient(circle, rgba(0, 255, 255, 0.3), rgba(0, 255, 255, 0.1))"
                : "rgba(0, 10, 30, 0.8)",
              border: currentMode === "full"
                ? "1px solid rgba(0, 255, 255, 0.5)"
                : "1px solid rgba(0, 255, 255, 0.2)",
              borderRadius: 8,
              color: currentMode === "full" ? "rgba(0, 255, 255, 0.95)" : "rgba(0, 255, 255, 0.7)",
              fontSize: 11,
              fontWeight: 500,
              cursor: "pointer",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              transition: "all 0.2s ease",
              boxShadow: currentMode === "full" ? "0 0 15px rgba(0, 255, 255, 0.4)" : "none",
            }}
            title="Full Window"
          >
            Full
          </button>
          <button
            onClick={() => setMode("floating")}
            style={{
              padding: "8px 12px",
              background: currentMode === "floating"
                ? "radial-gradient(circle, rgba(100, 200, 255, 0.3), rgba(100, 200, 255, 0.1))"
                : "rgba(0, 10, 30, 0.8)",
              border: currentMode === "floating"
                ? "1px solid rgba(100, 200, 255, 0.5)"
                : "1px solid rgba(100, 200, 255, 0.2)",
              borderRadius: 8,
              color: currentMode === "floating" ? "rgba(100, 200, 255, 0.95)" : "rgba(100, 200, 255, 0.7)",
              fontSize: 11,
              fontWeight: 500,
              cursor: "pointer",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              transition: "all 0.2s ease",
              boxShadow: currentMode === "floating" ? "0 0 15px rgba(100, 200, 255, 0.4)" : "none",
            }}
            title="Floating Mode"
          >
            Float
          </button>
          <button
            onClick={() => setMode("orb")}
            style={{
              padding: "8px 12px",
              background: "rgba(0, 10, 30, 0.8)",
              border: "1px solid rgba(255, 0, 255, 0.3)",
              borderRadius: 8,
              color: "rgba(255, 0, 255, 0.7)",
              fontSize: 11,
              fontWeight: 500,
              cursor: "pointer",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(255, 0, 255, 0.1)";
              e.currentTarget.style.borderColor = "rgba(255, 0, 255, 0.5)";
              e.currentTarget.style.boxShadow = "0 0 15px rgba(255, 0, 255, 0.4)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(0, 10, 30, 0.8)";
              e.currentTarget.style.borderColor = "rgba(255, 0, 255, 0.3)";
              e.currentTarget.style.boxShadow = "none";
            }}
            title="Orb Mode"
          >
            Orb
          </button>
        </div>
      )}
    </>
  );
}
