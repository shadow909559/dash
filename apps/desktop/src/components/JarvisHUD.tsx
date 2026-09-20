import { useEffect, useMemo, useRef, useState } from "react";
import { useAIStore, type AICoreStatus } from "@/stores/aiStore";
import {
  installOrbAppearanceSync,
  resolveOrbColors,
  resolveOrbSpeed,
  useOrbAppearanceStore,
} from "@/stores/orbAppearanceStore";
import { DASH_ANIMATIONS, type DASHState } from "@/stores/dashState";
import PlasmaRing from "@/components/PlasmaRing";
import "./JarvisHUD.css";

/**
 * Floating-orb HUD core — PlasmaRing edition.
 *
 * The old SVG ring HUD is replaced by the same WebGL PlasmaRing used by the
 * home Orb and the voice orb, so all three orb surfaces match. What is kept
 * from the original: the aiStore wiring (coreStatus text, DASH_COLORS-derived
 * palette, DASH_ANIMATIONS drive speed/wave height) and the mic-amplitude
 * reactivity, now expressed as plasma wave height instead of an SVG scale.
 */

const STATUS_TEXT: Record<AICoreStatus, string> = {
  idle: "READY",
  listening: "LISTENING",
  thinking: "THINKING",
  speaking: "SPEAKING",
  executing: "EXECUTING",
  error: "ERROR",
  provider_checking: "CHECKING",
  provider_starting: "STARTING",
  provider_unavailable: "OFFLINE",
};

/** DASH_COLORS stores rgba() strings; PlasmaRing wants hex ramps. The hex
 * values here are the exact conversions of dashState.ts's rgb triplets. */
const STATE_HEX: Record<DASHState, [string, string]> = {
  idle: ["#60a5fa", "#90caf9"],
  listening: ["#ff9600", "#ffb347"],
  thinking: ["#ff8c00", "#ffb347"],
  speaking: ["#ff9600", "#ffb347"],
  coding: ["#22c55e", "#4ade80"],
  researching: ["#3b82f6", "#60a5fa"],
  debugging: ["#a855f7", "#c084fc"],
  executing: ["#eab308", "#facc15"],
  success: ["#22c55e", "#4ade80"],
  warning: ["#3fa9f5", "#fb923c"],
  error: ["#3fa9f5", "#f87171"],
  offline: ["#6b7280", "#9ca3af"],
  connecting: ["#3b82f6", "#60a5fa"],
  background: ["#60a5fa", "#90caf9"],
};

const STATE_SPEED: Record<DASHState, number> = {
  idle: 60,
  listening: 110,
  thinking: 90,
  speaking: 100,
  coding: 105,
  researching: 130,
  debugging: 100,
  executing: 140,
  success: 95,
  warning: 80,
  error: 150,
  offline: 25,
  connecting: 85,
  background: 30,
};

export default function JarvisHUD() {
  const { coreStatus, dashState } = useAIStore();
  const appearance = useOrbAppearanceStore();
  const [amplitude, setAmplitude] = useState(0);
  const hostRef = useRef<HTMLDivElement>(null);
  const draggedRef = useRef(false);

  // Live palette/speed sync when settings change in the main window.
  useEffect(() => installOrbAppearanceSync(), []);

  // Owner's mic ('micamplitude') and DASH's own speech ('dashamplitude')
  // both drive the pulse — the louder of the two wins per event; an
  // explicit 0 (producer stopped) snaps to idle.
  useEffect(() => {
    const handleAmplitude = (e: any) =>
      setAmplitude((prev) => (e.detail === 0 ? 0 : Math.max(prev * 0.7, e.detail)));
    window.addEventListener('micamplitude', handleAmplitude);
    window.addEventListener('dashamplitude', handleAmplitude);
    return () => {
      window.removeEventListener('micamplitude', handleAmplitude);
      window.removeEventListener('dashamplitude', handleAmplitude);
    };
  }, []);

  const state = dashState as DASHState;
  const colors = resolveOrbColors(appearance, STATE_HEX[state] ?? STATE_HEX.idle);
  const speed = resolveOrbSpeed(appearance, STATE_SPEED[state] ?? STATE_SPEED.idle);
  const anim = DASH_ANIMATIONS[state] ?? DASH_ANIMATIONS.idle;

  // Mic amplitude drives the wave height — voice reactivity, plasma edition.
  const waveHeight = useMemo(() => {
    const base = 18 + anim.intensity * 22;
    return Math.min(60, base + amplitude * 30);
  }, [anim.intensity, amplitude]);

  const isError = coreStatus === "error" || state === "error";
  const statusText = STATUS_TEXT[coreStatus] ?? coreStatus.toUpperCase();
  const statusColor = isError ? "#ff4444" : colors[0];

  // Pointer tracking so drag-orbiting the PlasmaRing does not trigger the
  // orb-mode click handler (which activates the voice interface).
  const onPointerDown = () => { draggedRef.current = false; };
  const onPointerMove = (e: React.PointerEvent) => {
    if (e.buttons > 0) draggedRef.current = true;
  };
  const onClick = () => {
    if (draggedRef.current) return;
    const voiceButton = document.getElementById('voice-mic-button') as HTMLButtonElement | null;
    if (voiceButton) voiceButton.click();
  };

  return (
    <div
      ref={hostRef}
      className={`hud-container hud--${coreStatus}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onClick={onClick}
      style={{ cursor: "pointer" }}
    >
      <PlasmaRing
        background="transparent"
        colors={colors}
        speed={speed}
        waveHeight={waveHeight}
        scale={28}
        density={64}
      />
      {/* Status overlay — same content the SVG HUD rendered */}
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
          className="hud-center-text"
          style={{
            fontSize: 26,
            fontWeight: 700,
            fontFamily: "'Orbitron', 'Segoe UI', 'Roboto', sans-serif",
            color: statusColor,
            letterSpacing: 4,
            textShadow: `0 0 10px ${statusColor}cc, 0 0 20px ${statusColor}80`,
          }}
        >
          DASH
        </span>
        <span
          className="hud-center-subtext"
          style={{
            fontSize: 10,
            fontFamily: "'Orbitron', 'Segoe UI', 'Roboto', sans-serif",
            color: colors[1],
            letterSpacing: 2,
            marginTop: 6,
            textShadow: `0 0 5px ${colors[1]}99`,
          }}
        >
          {statusText}
        </span>
      </div>
    </div>
  );
}
