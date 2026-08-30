import React from "react";
import ReactDOM from "react-dom/client";
import JarvisHUD from "./components/JarvisHUD";
import VoiceInterface from "./components/VoiceInterface";
import AIStatusIndicator from "./components/AIStatusIndicator";
import { initializeWebSocket } from "./lib/ws";
import { startSystemStatsPolling } from "./stores/aiStore";
import "./index.css";

// Dedicated Orb Mode - minimal UI with just the DASH core
function OrbMode() {
  React.useEffect(() => {
    initializeWebSocket();
    const statsInterval = startSystemStatsPolling(5000);
    return () => {
      if (statsInterval) clearInterval(statsInterval);
    };
  }, []);

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        position: "relative",
        overflow: "hidden",
        backgroundColor: "#000510",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Centered DASH Core */}
      <div
        style={{
          position: "relative",
          width: "300px",
          height: "300px",
          cursor: "pointer",
        }}
        onClick={() => {
          // Trigger voice interface when orb is clicked
          const voiceButton = document.getElementById('voice-mic-button') as HTMLButtonElement;
          if (voiceButton) voiceButton.click();
        }}
        title="Click to activate voice"
      >
        <JarvisHUD />
      </div>

      {/* Minimal Voice Interface */}
      <VoiceInterface />

      {/* Minimal Status Indicator */}
      <AIStatusIndicator />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <OrbMode />
  </React.StrictMode>
);