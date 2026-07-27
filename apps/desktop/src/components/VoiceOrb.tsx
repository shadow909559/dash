import { useState, useEffect, useRef } from "react";

interface VoiceOrbProps {
  isListening?: boolean;
  onToggle?: () => void;
}

export default function VoiceOrb({ isListening = false, onToggle }: VoiceOrbProps) {
  const [active, setActive] = useState(isListening);
  const [waveforms, setWaveforms] = useState<number[]>([]);
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    setActive(isListening);
  }, [isListening]);

  useEffect(() => {
    if (!active) {
      setWaveforms([]);
      return;
    }
    const generateWaveform = () => {
      const bars = 5;
      const newWaveforms = Array.from({ length: bars }, () =>
        Math.random() * 40 + 10
      );
      setWaveforms(newWaveforms);
      animFrameRef.current = requestAnimationFrame(generateWaveform);
    };
    generateWaveform();
    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [active]);

  const handleClick = () => {
    setActive(!active);
    onToggle?.();
  };

  return (
    <div
      onClick={handleClick}
      title={active ? "Voice active - click to stop" : "Click to activate voice"}
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 999,
        cursor: "pointer",
        userSelect: "none",
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: "50%",
          background: active
            ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
            : "var(--bg-glass)",
          border: active
            ? "2px solid var(--accent-secondary)"
            : "1px solid var(--border-glass)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: active
            ? "0 0 30px var(--accent-glow), 0 0 60px var(--accent-glow)"
            : "var(--shadow-glass)",
          transition: "all 0.3s ease",
          animation: active ? "glow 2s ease-in-out infinite" : "none",
        }}
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={active ? "white" : "var(--text-muted)"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="22" />
        </svg>
      </div>
      {active && (
        <div
          style={{
            position: "absolute",
            bottom: 72,
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--bg-glass)",
            backdropFilter: "blur(12px)",
            border: "1px solid var(--border-glass)",
            borderRadius: 12,
            padding: "12px 16px",
            whiteSpace: "nowrap",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 30 }}>
            {waveforms.map((h, i) => (
              <div
                key={i}
                style={{
                  width: 4,
                  height: h,
                  borderRadius: 2,
                  background: "var(--accent-primary)",
                  transition: "height 0.1s ease",
                }}
              />
            ))}
          </div>
          <span style={{ fontSize: 13, color: "var(--text-primary)" }}>
            Listening...
          </span>
        </div>
      )}
    </div>
  );
}
