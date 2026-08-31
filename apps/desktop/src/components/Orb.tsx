import { useRef, useEffect, useCallback } from "react";
import { useAIStore } from "@/stores/aiStore";

/**
 * DASH Orb — Ultron-inspired dark energy core.
 *
 * States: idle, listening, thinking, speaking, executing, error, disconnected
 * Visual: dark industrial core with crimson energy, rotating rings, particles
 */
export default function Orb() {
  const { aiProviderStatus, websocketStatus, dashState } = useAIStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const timeRef = useRef(0);
  const particlesRef = useRef<
    Array<{
      x: number;
      y: number;
      vx: number;
      vy: number;
      life: number;
      maxLife: number;
      size: number;
    }>
  >([]);

  const getState = useCallback(() => {
    if (websocketStatus === "disconnected") return "disconnected";
    if (aiProviderStatus === "error" || dashState === "error") return "error";
    if (dashState === "thinking" || aiProviderStatus === "thinking") return "thinking";
    if (dashState === "speaking" || aiProviderStatus === "responding") return "speaking";
    if (dashState === "listening" || aiProviderStatus === "listening") return "listening";
    if (dashState === "executing") return "executing";
    return "idle";
  }, [aiProviderStatus, websocketStatus, dashState]);

  const getColors = useCallback((state: string) => {
    switch (state) {
      case "thinking":
        return {
          core: "#3fa9f5",
          coreInner: "#1a5276",
          ring: "#b91c1c",
          glow: "rgba(63,169,245,0.45)",
          particle: "#fca5a5",
          atmosphere: "rgba(63,169,245,0.10)",
          ringCount: 5,
          ringSpeed: 2.5,
        };
      case "speaking":
        return {
          core: "#3fa9f5",
          coreInner: "#b91c1c",
          ring: "#3fa9f5",
          glow: "rgba(63,169,245,0.50)",
          particle: "#fca5a5",
          atmosphere: "rgba(63,169,245,0.08)",
          ringCount: 4,
          ringSpeed: 1.8,
        };
      case "listening":
        return {
          core: "#00d4ff",
          coreInner: "#c2410c",
          ring: "#ea580c",
          glow: "rgba(249,115,22,0.45)",
          particle: "#fdba74",
          atmosphere: "rgba(249,115,22,0.08)",
          ringCount: 4,
          ringSpeed: 1.5,
        };
      case "executing":
        return {
          core: "#eab308",
          coreInner: "#a16207",
          ring: "#ca8a04",
          glow: "rgba(234,179,8,0.40)",
          particle: "#fde047",
          atmosphere: "rgba(234,179,8,0.08)",
          ringCount: 4,
          ringSpeed: 1.2,
        };
      case "error":
        return {
          core: "#3fa9f5",
          coreInner: "#7f1d1d",
          ring: "#1a5276",
          glow: "rgba(63,169,245,0.35)",
          particle: "#f87171",
          atmosphere: "rgba(63,169,245,0.06)",
          ringCount: 3,
          ringSpeed: 0.8,
        };
      case "disconnected":
        return {
          core: "#374151",
          coreInner: "#1f2937",
          ring: "#4b5563",
          glow: "rgba(75,85,99,0.15)",
          particle: "#6b7280",
          atmosphere: "rgba(75,85,99,0.04)",
          ringCount: 2,
          ringSpeed: 0.2,
        };
      default: // idle
        return {
          core: "#3fa9f5",
          coreInner: "#7f1d1d",
          ring: "#1a5276",
          glow: "rgba(63,169,245,0.30)",
          particle: "#fca5a5",
          atmosphere: "rgba(63,169,245,0.06)",
          ringCount: 3,
          ringSpeed: 0.4,
        };
    }
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const size = 320;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const maxRadius = size * 0.34;

    const spawnParticle = (colors: ReturnType<typeof getColors>) => {
      const angle = Math.random() * Math.PI * 2;
      const dist = maxRadius * (0.3 + Math.random() * 0.9);
      particlesRef.current.push({
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        vx: (Math.random() - 0.5) * 0.8,
        vy: (Math.random() - 0.5) * 0.8,
        life: 0,
        maxLife: 60 + Math.random() * 160,
        size: 0.8 + Math.random() * 2.5,
      });
    };

    const draw = () => {
      timeRef.current += 0.016;
      const t = timeRef.current;
      const state = getState();
      const colors = getColors(state);

      ctx.clearRect(0, 0, size, size);

      // ─── Outer atmospheric glow ───
      const glowRadius = maxRadius * 1.8;
      const glow = ctx.createRadialGradient(cx, cy, maxRadius * 0.3, cx, cy, glowRadius);
      glow.addColorStop(0, colors.glow);
      glow.addColorStop(0.4, colors.atmosphere);
      glow.addColorStop(1, "transparent");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2);
      ctx.fill();

      // ─── Rotating energy rings ───
      for (let i = 0; i < colors.ringCount; i++) {
        const ringRadius = maxRadius * (0.58 + i * 0.12);
        const speed = colors.ringSpeed * (i % 2 === 0 ? 1 : -1);
        const ringAngle = t * speed + (i * Math.PI * 2) / colors.ringCount;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(ringAngle);

        // Dashed energy ring
        ctx.beginPath();
        ctx.ellipse(0, 0, ringRadius, ringRadius * 0.22, 0, 0, Math.PI * 2);
        ctx.strokeStyle = colors.ring;
        ctx.globalAlpha = 0.10 + 0.10 * Math.sin(t * 2 + i);
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 6 + i * 2]);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.restore();
      }

      // ─── Inner energy field ───
      const energyCount = state === "thinking" ? 14 : state === "speaking" ? 10 : 8;
      ctx.globalAlpha = 0.20;
      for (let i = 0; i < energyCount; i++) {
        const angle =
          (i / energyCount) * Math.PI * 2 +
          t * (state === "thinking" ? 1.5 : state === "speaking" ? 1.0 : 0.3);
        const dist = maxRadius * (0.15 + 0.10 * Math.sin(t * 1.8 + i * 0.7));
        const x = cx + Math.cos(angle) * dist;
        const y = cy + Math.sin(angle) * dist;

        const energyGrad = ctx.createRadialGradient(x, y, 0, x, y, 6);
        energyGrad.addColorStop(0, colors.particle);
        energyGrad.addColorStop(1, "transparent");
        ctx.fillStyle = energyGrad;
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      // ─── Core sphere ───
      const coreGrad = ctx.createRadialGradient(
        cx - maxRadius * 0.12,
        cy - maxRadius * 0.12,
        0,
        cx,
        cy,
        maxRadius,
      );
      coreGrad.addColorStop(0, colors.core);
      coreGrad.addColorStop(0.45, colors.coreInner);
      coreGrad.addColorStop(0.8, "rgba(0,0,0,0.60)");
      coreGrad.addColorStop(1, "rgba(0,0,0,0.85)");
      ctx.fillStyle = coreGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, maxRadius, 0, Math.PI * 2);
      ctx.fill();

      // ─── Inner core detail — concentric dark rings ───
      for (let r = 0; r < 3; r++) {
        const rr = maxRadius * (0.25 + r * 0.15);
        ctx.beginPath();
        ctx.arc(cx, cy, rr, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(63,169,245,${0.06 + 0.03 * Math.sin(t + r)})`;
        ctx.lineWidth = 0.8;
        ctx.stroke();
      }

      // ─── Core highlight ───
      const highlight = ctx.createRadialGradient(
        cx - maxRadius * 0.22,
        cy - maxRadius * 0.28,
        0,
        cx,
        cy,
        maxRadius * 0.65,
      );
      highlight.addColorStop(0, "rgba(255,255,255,0.12)");
      highlight.addColorStop(0.3, "rgba(255,255,255,0.03)");
      highlight.addColorStop(1, "transparent");
      ctx.fillStyle = highlight;
      ctx.beginPath();
      ctx.arc(cx, cy, maxRadius, 0, Math.PI * 2);
      ctx.fill();

      // ─── Specular glint ───
      const glintAlpha = 0.08 + 0.06 * Math.sin(t * 0.7);
      ctx.fillStyle = `rgba(255,255,255,${glintAlpha})`;
      ctx.beginPath();
      ctx.ellipse(
        cx - maxRadius * 0.2,
        cy - maxRadius * 0.25,
        maxRadius * 0.15,
        maxRadius * 0.08,
        -0.5,
        0,
        Math.PI * 2,
      );
      ctx.fill();

      // ─── Particles ───
      const spawnRate =
        state === "thinking" ? 0.5 : state === "speaking" ? 0.4 : state === "listening" ? 0.25 : 0.06;
      if (Math.random() < spawnRate) spawnParticle(colors);

      particlesRef.current = particlesRef.current.filter((p) => {
        p.life++;
        p.x += p.vx;
        p.y += p.vy;
        p.vy -= 0.01; // slight upward drift
        const alpha = 1 - p.life / p.maxLife;
        if (alpha <= 0) return false;

        ctx.globalAlpha = alpha * 0.6;
        ctx.fillStyle = colors.particle;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
        return true;
      });
      ctx.globalAlpha = 1;

      // ─── State label ───
      const label =
        state === "idle"
          ? "DASH"
          : state === "disconnected"
            ? "OFFLINE"
            : state.toUpperCase();
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.font = "600 14px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, cx, cy);

      // ─── Subtle subtitle for non-idle states ───
      if (state !== "idle" && state !== "disconnected") {
        ctx.fillStyle = "rgba(255,255,255,0.40)";
        ctx.font = "400 9px Inter, sans-serif";
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
        if (subtitle) ctx.fillText(subtitle, cx, cy + 18);
      }

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [getState, getColors]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        cursor: "pointer",
        display: "block",
        filter: "drop-shadow(0 0 30px rgba(63,169,245,0.15))",
      }}
    />
  );
}
