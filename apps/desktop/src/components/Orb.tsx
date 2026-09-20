import { useEffect, useMemo, useRef } from "react";
import { useAIStore } from "@/stores/aiStore";
import {
  installOrbAppearanceSync,
  resolveOrbColors,
  resolveOrbSpeed,
  resolveOrbWave,
  useOrbAppearanceStore,
} from "@/stores/orbAppearanceStore";
import PlasmaRing from "@/components/PlasmaRing";

/**
 * DASH Orb — Plasma Ring core.
 *
 * States: idle, listening, thinking, speaking, executing, error, disconnected
 * Visual: WebGL plasma wireframe sphere (PlasmaRing), state-driven palette,
 * with the state label overlaid in the core.
 */

const SIZE = 320;

const STATE_PALETTES: Record<string, string[]> = {
  idle: ["#3fa9f5", "#1a5276"],
  listening: ["#00d4ff", "#0e4d6e"],
  thinking: ["#a855f7", "#4c1d95"],
  speaking: ["#3b82f6", "#1e3a8a"],
  executing: ["#eab308", "#713f12"],
  error: ["#ef4444", "#7f1d1d"],
  disconnected: ["#4b5563", "#1f2937"],
};

const STATE_SPEEDS: Record<string, number> = {
  idle: 60,
  listening: 110,
  thinking: 140,
  speaking: 100,
  executing: 90,
  error: 30,
  disconnected: 20,
};

export default function Orb() {
  const { aiProviderStatus, websocketStatus, dashState } = useAIStore();
  const appearance = useOrbAppearanceStore();

  // Keep this window's store fresh when settings change in another window
  // (the floating orb is a separate Electron renderer).
  useEffect(() => installOrbAppearanceSync(), []);

  // Live audio amplitude (0..1) from both real sources: the owner's mic
  // ('micamplitude') and DASH's own speech ('dashamplitude' — server-side
  // Piper playback levels pushed over ws, or the client-side TTS analyser
  // tap in lib/ws.ts). Ref-driven: the WebGL loop reads it without
  // re-renders, and it decays to 0 when no producer is dispatching.
  const orbAmplitudeRef = useRef(0);
  useEffect(() => {
    // Max-decay merge: the louder source wins, and the pulse decays
    // smoothly when producers stop rather than holding a stale value.
    // An explicit 0 (producer stopped) snaps fully to idle.
    const setAmp = (e: Event) => {
      const detail = (e as CustomEvent<number>).detail;
      if (typeof detail === "number" && Number.isFinite(detail)) {
        orbAmplitudeRef.current =
          detail === 0
            ? 0
            : Math.max(
                orbAmplitudeRef.current * 0.75,
                Math.max(0, Math.min(1, detail)),
              );
      }
    };
    window.addEventListener("micamplitude", setAmp);
    window.addEventListener("dashamplitude", setAmp);
    return () => {
      window.removeEventListener("micamplitude", setAmp);
      window.removeEventListener("dashamplitude", setAmp);
    };
  }, []);

  const state = useMemo(() => {
    if (websocketStatus === "disconnected") return "disconnected";
    if (aiProviderStatus === "error" || dashState === "error") return "error";
    if (dashState === "thinking" || aiProviderStatus === "thinking") return "thinking";
    if (dashState === "speaking" || aiProviderStatus === "responding") return "speaking";
    if (dashState === "listening" || aiProviderStatus === "listening") return "listening";
    if (dashState === "executing") return "executing";
    return "idle";
  }, [aiProviderStatus, websocketStatus, dashState]);

  const statePalette = STATE_PALETTES[state] ?? STATE_PALETTES.idle;
  const stateSpeed = STATE_SPEEDS[state] ?? STATE_SPEEDS.idle;
  const colors = resolveOrbColors(appearance, statePalette);
  const speed = resolveOrbSpeed(appearance, stateSpeed);
  const waveHeight = resolveOrbWave(
    appearance,
    state === "thinking" ? 34 : state === "listening" ? 26 : 20,
  );
  const label =
    state === "idle" ? "DASH" : state === "disconnected" ? "OFFLINE" : state.toUpperCase();
  const subtitle =
    state === "thinking"
      ? "Processing..."
      : state === "speaking"
        ? "Responding..."
        : state === "listening"
          ? "Listening..."
          : state === "executing"
            ? "Running tool..."
            : state === "error"
              ? "System error"
              : "";

  return (
    <div
      style={{
        position: "relative",
        width: SIZE,
        height: SIZE,
        cursor: "pointer",
        filter: "drop-shadow(0 0 30px rgba(63,169,245,0.15))",
      }}
    >
      <PlasmaRing
        background="transparent"
        colors={resolveOrbColors(appearance, statePalette)}
        speed={resolveOrbSpeed(appearance, stateSpeed)}
        waveHeight={waveHeight}
        amplitudeRef={orbAmplitudeRef}
        scale={30}
        density={64}
      />
      {/* State label overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none",
        }}
      >
        <span
          style={{
            fontSize: 14,
            fontWeight: 600,
            fontFamily: "Inter, sans-serif",
            color: "rgba(255,255,255,0.85)",
            textShadow: "0 0 12px rgba(0,0,0,0.8)",
            letterSpacing: "0.08em",
          }}
        >
          {label}
        </span>
        {subtitle && (
          <span
            style={{
              fontSize: 9,
              fontWeight: 400,
              fontFamily: "Inter, sans-serif",
              color: "rgba(255,255,255,0.40)",
              marginTop: 4,
              textShadow: "0 0 8px rgba(0,0,0,0.8)",
            }}
          >
            {subtitle}
          </span>
        )}
      </div>
    </div>
  );
}
