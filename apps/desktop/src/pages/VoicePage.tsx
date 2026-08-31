import { useState, useRef, useEffect, useCallback } from "react";
import { useAIStore } from "@/stores/aiStore";
import { getWsClient } from "@/lib/wsClient";
import { Mic, MicOff, Send, Volume2, VolumeX, Square, RotateCcw, Sparkles } from "lucide-react";

/**
 * VoicePage — full-screen immersive voice interface for DASH.
 *
 * Features:
 * - Massive centered Orb with breathing animation
 * - Live microphone visualization (animated waveform bars)
 * - Real-time transcription display
 * - Push-to-talk and continuous listening modes
 * - Voice command history
 * - TTS audio playback visualization
 */
export default function VoicePage() {
  const {
    aiProviderStatus,
    websocketStatus,
    voiceStatus,
    setVoiceStatus,
    orbMode,
    setOrbMode,
    setCurrentReply,
  } = useAIStore();

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [liveTranscript, setLiveTranscript] = useState("");
  const [history, setHistory] = useState<
    Array<{ role: "user" | "dash"; text: string; time: number }>
  >([]);
  const [isMuted, setIsMuted] = useState(false);
  const [waveformAmplitudes, setWaveformAmplitudes] = useState<number[]>(
    Array(32).fill(0.1)
  );
  const [ttsActive, setTtsActive] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const animationFrameRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // ─── Waveform Animation ───
  const animateWaveform = useCallback(() => {
    if (!analyserRef.current) {
      // Idle breathing animation
      setWaveformAmplitudes((prev) =>
        prev.map((_, i) => {
          const t = Date.now() / 1000;
          return (
            0.08 +
            0.04 * Math.sin(t * 1.5 + i * 0.3) +
            0.02 * Math.sin(t * 2.7 + i * 0.5)
          );
        })
      );
      animationFrameRef.current = requestAnimationFrame(animateWaveform);
      return;
    }

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);

    // Sample 32 bars from the frequency data
    const barCount = 32;
    const step = Math.floor(dataArray.length / barCount);
    const newAmplitudes = Array.from({ length: barCount }, (_, i) => {
      const value = dataArray[i * step] || 0;
      return Math.max(0.05, value / 255);
    });

    setWaveformAmplitudes(newAmplitudes);
    animationFrameRef.current = requestAnimationFrame(animateWaveform);
  }, []);

  useEffect(() => {
    animationFrameRef.current = requestAnimationFrame(animateWaveform);
    return () => cancelAnimationFrame(animationFrameRef.current);
  }, [animateWaveform]);

  // ─── Microphone Access ───
  const startMicrophone = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Start recording for STT
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });
        // Convert to base64 and send via WebSocket
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64 = (reader.result as string).split(",")[1];
          if (base64) {
            const requestId = `stt_${Date.now()}`;
            getWsClient().sendVoiceSTT(requestId, base64);
          }
        };
        reader.readAsDataURL(audioBlob);
      };

      mediaRecorder.start(1000); // Collect in 1-second chunks
      setIsListening(true);
      setVoiceStatus("listening");
      setOrbMode("listening");
    } catch (err) {
      console.error("Microphone access denied:", err);
      setVoiceStatus("error");
    }
  }, [setVoiceStatus, setOrbMode]);

  const stopMicrophone = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    setIsListening(false);
    setVoiceStatus("ready");
    setOrbMode("standby");
  }, [setVoiceStatus, setOrbMode]);

  // ─── Send text command (fallback) ───
  const sendTextCommand = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      setHistory((prev) => [
        ...prev,
        { role: "user", text: text.trim(), time: Date.now() },
      ]);
      setTranscript("");
      setLiveTranscript("");
      setVoiceStatus("listening");
      setOrbMode("thinking");
      const ws = getWsClient();
      ws.sendChatMessage(`cmd_${Date.now()}`, text.trim());
    },
    [setVoiceStatus, setOrbMode]
  );

  // ─── Listen for STT results via WebSocket ───
  useEffect(() => {
    const ws = getWsClient();
    const handler = (msg: Record<string, unknown>) => {
      const type = msg.type as string;
      if (type === "voice.stt.done") {
        const text = (msg.text as string) || "";
        setLiveTranscript(text);
        setHistory((prev) => [
          ...prev,
          { role: "user", text, time: Date.now() },
        ]);
        ws.sendChatMessage(`stt_${Date.now()}`, text);
        setVoiceStatus("listening");
        setOrbMode("thinking");
      }
      if (type === "chat.done") {
        setVoiceStatus("ready");
        setOrbMode("standby");
      }
      if (type === "voice.tts_ready" || type === "voice.tts.done") {
        setTtsActive(true);
        setVoiceStatus("speaking");
        setOrbMode("executing");
        setTimeout(() => {
          setTtsActive(false);
          setVoiceStatus("ready");
          setOrbMode("standby");
        }, 3000);
      }
    };
    ws.on("voice.stt.done", handler);
    ws.on("chat.done", handler);
    ws.on("voice.tts_ready", handler);
    ws.on("voice.tts.done", handler);
    return () => {
      ws.off("voice.stt.done", handler);
      ws.off("chat.done", handler);
      ws.off("voice.tts_ready", handler);
      ws.off("voice.tts.done", handler);
    };
  }, [setVoiceStatus, setOrbMode]);

  const wsConnected = websocketStatus === "connected";
  const orbState =
    !wsConnected
      ? "disconnected"
      : isListening
      ? "listening"
      : voiceStatus === "listening"
      ? "thinking"
      : voiceStatus === "speaking"
      ? "speaking"
      : "idle";

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
        background: `
          radial-gradient(ellipse at 50% 30%, rgba(77,148,255,0.06), transparent 60%),
          radial-gradient(ellipse at 30% 70%, rgba(159,122,250,0.04), transparent 50%),
          radial-gradient(ellipse at 70% 80%, rgba(6,182,212,0.03), transparent 50%),
          var(--dash-bg)
        `,
      }}
    >
      {/* Background grid lines */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
          pointerEvents: "none",
        }}
      />

      {/* Atmospheric glow behind Orb */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -55%)",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background:
            orbState === "listening"
              ? "radial-gradient(circle, rgba(6,182,212,0.12), transparent 70%)"
              : orbState === "thinking"
              ? "radial-gradient(circle, rgba(168,85,247,0.12), transparent 70%)"
              : orbState === "speaking"
              ? "radial-gradient(circle, rgba(59,130,246,0.12), transparent 70%)"
              : "radial-gradient(circle, rgba(77,148,255,0.06), transparent 70%)",
          transition: "background 0.8s ease",
          pointerEvents: "none",
        }}
      />

      {/* Top status bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 12,
          padding: "16px 24px",
          zIndex: 10,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 14px",
            borderRadius: 20,
            background: "var(--dash-surface)",
            border: "1px solid var(--dash-border)",
          }}
        >
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: wsConnected ? "#10b981" : "#3fa9f5",
              boxShadow: wsConnected
                ? "0 0 8px rgba(16,185,129,0.6)"
                : "0 0 8px rgba(63,169,245,0.6)",
            }}
          />
          <span
            style={{
              fontSize: 11,
              fontFamily: "JetBrains Mono, monospace",
              color: "var(--dash-text-muted)",
              letterSpacing: "0.05em",
            }}
          >
            {wsConnected ? "DASH ONLINE" : "OFFLINE"}
          </span>
        </div>

        <div
          style={{
            fontSize: 11,
            fontFamily: "JetBrains Mono, monospace",
            color:
              orbState === "listening"
                ? "#06b6d4"
                : orbState === "thinking"
                ? "#a855f7"
                : orbState === "speaking"
                ? "#3b82f6"
                : "var(--dash-text-muted)",
            letterSpacing: "0.08em",
            textTransform: "uppercase" as const,
            transition: "color 0.3s",
          }}
        >
          {orbState === "listening"
            ? "LISTENING"
            : orbState === "thinking"
            ? "THINKING"
            : orbState === "speaking"
            ? "SPEAKING"
            : "VOICE READY"}
        </div>
      </div>

      {/* Central Orb — massive */}
      <div
        className="animate-breathe"
        style={{
          transform: `scale(${isListening ? 1.1 : 1.0})`,
          transition: "transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)",
          zIndex: 5,
        }}
      >
        {/* The Orb is rendered by its Canvas at 240px. We scale it up. */}
        <div style={{ transform: "scale(1.8)", transformOrigin: "center" }}>
          {/* Inline Orb rendering for full control */}
          <FullVoiceOrb state={orbState} />
        </div>
      </div>

      {/* Waveform visualization */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 2,
          height: 48,
          marginTop: 32,
          zIndex: 5,
        }}
      >
        {waveformAmplitudes.map((amp, i) => (
          <div
            key={i}
            style={{
              width: 3,
              height: `${Math.max(4, amp * 44)}px`,
              borderRadius: 2,
              background:
                orbState === "listening"
                  ? `rgba(6,182,212,${0.3 + amp * 0.7})`
                  : orbState === "thinking"
                  ? `rgba(168,85,247,${0.3 + amp * 0.7})`
                  : orbState === "speaking"
                  ? `rgba(59,130,246,${0.3 + amp * 0.7})`
                  : `rgba(255,255,255,${0.08 + amp * 0.15})`,
              transition: "height 0.08s ease, background 0.3s ease",
            }}
          />
        ))}
      </div>

      {/* Live transcription */}
      <div
        style={{
          marginTop: 24,
          padding: "12px 32px",
          maxWidth: 600,
          textAlign: "center",
          minHeight: 48,
          zIndex: 5,
        }}
      >
        {liveTranscript ? (
          <div
            style={{
              fontSize: 18,
              fontWeight: 500,
              color: "var(--dash-text)",
              lineHeight: 1.5,
              animation: "fadeIn 0.3s ease",
            }}
          >
            "{liveTranscript}"
          </div>
        ) : isListening ? (
          <div
            style={{
              fontSize: 14,
              color: "var(--dash-text-muted)",
              fontStyle: "italic",
            }}
          >
            Listening...
          </div>
        ) : (
          <div
            style={{
              fontSize: 13,
              color: "var(--dash-text-muted)",
              opacity: 0.6,
            }}
          >
            Tap the microphone or type a command
          </div>
        )}
      </div>

      {/* Control buttons */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginTop: 28,
          zIndex: 10,
        }}
      >
        {/* Mute toggle */}
        <button
          onClick={() => setIsMuted(!isMuted)}
          style={{
            width: 44,
            height: 44,
            borderRadius: "50%",
            border: "1px solid var(--dash-border)",
            background: "var(--dash-surface)",
            color: isMuted ? "#3fa9f5" : "var(--dash-text-muted)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            transition: "all 0.2s",
          }}
          title={isMuted ? "Unmute TTS" : "Mute TTS"}
        >
          {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
        </button>

        {/* Main mic button */}
        <button
          onClick={isListening ? stopMicrophone : startMicrophone}
          style={{
            width: 72,
            height: 72,
            borderRadius: "50%",
            border: `2px solid ${
              isListening ? "#06b6d4" : "var(--dash-border)"
            }`,
            background: isListening
              ? "linear-gradient(135deg, #06b6d4, #0891b2)"
              : "var(--dash-surface)",
            color: isListening ? "#fff" : "var(--dash-text)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            boxShadow: isListening
              ? "0 0 30px rgba(6,182,212,0.4), 0 0 60px rgba(6,182,212,0.15)"
              : "0 4px 20px rgba(0,0,0,0.3)",
            transition: "all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)",
            transform: isListening ? "scale(1.05)" : "scale(1)",
          }}
          title={isListening ? "Stop listening" : "Start listening"}
        >
          {isListening ? <Square size={24} /> : <Mic size={28} />}
        </button>

        {/* Text input toggle */}
        <VoiceTextInput onSend={sendTextCommand} />
      </div>

      {/* Chat history */}
      {history.length > 0 && (
        <div
          style={{
            position: "absolute",
            bottom: 20,
            left: 24,
            right: 24,
            maxHeight: 180,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 6,
            padding: "12px 16px",
            borderRadius: 16,
            background: "rgba(0,0,0,0.4)",
            backdropFilter: "blur(12px)",
            border: "1px solid var(--dash-border)",
            zIndex: 10,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontFamily: "JetBrains Mono, monospace",
              color: "var(--dash-text-muted)",
              letterSpacing: "0.1em",
              textTransform: "uppercase" as const,
              marginBottom: 4,
            }}
          >
            VOICE HISTORY
          </div>
          {history.slice(-6).map((entry, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
              }}
            >
              <span
                style={{
                  fontSize: 10,
                  fontFamily: "JetBrains Mono, monospace",
                  color:
                    entry.role === "user" ? "#06b6d4" : "var(--dash-accent)",
                  fontWeight: 600,
                  flexShrink: 0,
                  marginTop: 2,
                }}
              >
                {entry.role === "user" ? "YOU" : "DASH"}
              </span>
              <span
                style={{
                  fontSize: 12,
                  color: "var(--dash-text-secondary)",
                  lineHeight: 1.4,
                }}
              >
                {entry.text.length > 80
                  ? entry.text.slice(0, 80) + "..."
                  : entry.text}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Voice-specific CSS animations */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

/** Voice text input with send button */
function VoiceTextInput({ onSend }: { onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={{
          width: 44,
          height: 44,
          borderRadius: "50%",
          border: "1px solid var(--dash-border)",
          background: "var(--dash-surface)",
          color: "var(--dash-text-muted)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          transition: "all 0.2s",
        }}
        title="Type a voice command"
      >
        <Sparkles size={18} />
      </button>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 12px",
        borderRadius: 24,
        background: "var(--dash-surface)",
        border: "1px solid var(--dash-border)",
      }}
    >
      <input
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && text.trim()) {
            onSend(text);
            setText("");
            setIsOpen(false);
          }
          if (e.key === "Escape") setIsOpen(false);
        }}
        placeholder="Type a command..."
        style={{
          background: "none",
          border: "none",
          color: "var(--dash-text)",
          fontSize: 13,
          /* a11y: removed outline:none — global :focus-visible handles focus */
          width: 180,
          fontFamily: "inherit",
        }}
      />
      <button
        onClick={() => {
          if (text.trim()) {
            onSend(text);
            setText("");
            setIsOpen(false);
          }
        }}
        style={{
          width: 30,
          height: 30,
          borderRadius: "50%",
          border: "none",
          background: text.trim() ? "var(--dash-accent)" : "transparent",
          color: text.trim() ? "#000" : "var(--dash-text-muted)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          transition: "all 0.2s",
        }}
      >
        <Send size={14} />
      </button>
    </div>
  );
}

/** Full-voice Orb with Canvas2D — larger, more dramatic than the sidebar Orb */
function FullVoiceOrb({ state }: { state: string }) {
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

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const size = 240;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const maxRadius = size * 0.36;

    const getColors = () => {
      switch (state) {
        case "thinking":
          return {
            core: "#a855f7",
            ring: "#7c3aed",
            glow: "rgba(168,85,247,0.45)",
            particle: "#c084fc",
            atmosphere: "rgba(168,85,247,0.08)",
          };
        case "speaking":
          return {
            core: "#3b82f6",
            ring: "#2563eb",
            glow: "rgba(59,130,246,0.50)",
            particle: "#60a5fa",
            atmosphere: "rgba(59,130,246,0.08)",
          };
        case "listening":
          return {
            core: "#06b6d4",
            ring: "#0891b2",
            glow: "rgba(6,182,212,0.45)",
            particle: "#22d3ee",
            atmosphere: "rgba(6,182,212,0.08)",
          };
        case "error":
          return {
            core: "#3fa9f5",
            ring: "#3fa9f5",
            glow: "rgba(63,169,245,0.45)",
            particle: "#f87171",
            atmosphere: "rgba(63,169,245,0.08)",
          };
        case "disconnected":
          return {
            core: "#6b7280",
            ring: "#4b5563",
            glow: "rgba(107,114,128,0.20)",
            particle: "#9ca3af",
            atmosphere: "rgba(107,114,128,0.04)",
          };
        default:
          return {
            core: "#4d94ff",
            ring: "#3b82f6",
            glow: "rgba(77,148,255,0.35)",
            particle: "#93c5fd",
            atmosphere: "rgba(77,148,255,0.05)",
          };
      }
    };

    // Initialize particles
    if (particlesRef.current.length === 0) {
      for (let i = 0; i < 40; i++) {
        particlesRef.current.push({
          x: cx + (Math.random() - 0.5) * maxRadius * 2,
          y: cy + (Math.random() - 0.5) * maxRadius * 2,
          vx: (Math.random() - 0.5) * 0.3,
          vy: (Math.random() - 0.5) * 0.3,
          life: Math.random() * 200,
          maxLife: 150 + Math.random() * 100,
          size: 1 + Math.random() * 2.5,
        });
      }
    }

    const draw = () => {
      timeRef.current += 0.016;
      const t = timeRef.current;
      const colors = getColors();

      ctx.clearRect(0, 0, size, size);

      // Atmospheric glow
      const atmosGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxRadius * 1.6);
      atmosGrad.addColorStop(0, colors.atmosphere);
      atmosGrad.addColorStop(1, "transparent");
      ctx.fillStyle = atmosGrad;
      ctx.fillRect(0, 0, size, size);

      // Outer ring
      const breathScale = 1 + Math.sin(t * 1.2) * 0.03;
      ctx.beginPath();
      ctx.arc(cx, cy, maxRadius * 1.1 * breathScale, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Rotating dashed ring
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(t * 0.3);
      ctx.beginPath();
      ctx.arc(0, 0, maxRadius * 1.25 * breathScale, 0, Math.PI * 2);
      ctx.setLineDash([8, 12]);
      ctx.strokeStyle = colors.ring + "60";
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // Second rotating ring (reverse)
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-t * 0.2);
      ctx.beginPath();
      ctx.arc(0, 0, maxRadius * 1.35 * breathScale, 0, Math.PI * 2);
      ctx.setLineDash([5, 10]);
      ctx.strokeStyle = colors.ring + "40";
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // Inner shell
      ctx.beginPath();
      ctx.arc(cx, cy, maxRadius * 0.88, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(10,10,10,0.9)";
      ctx.fill();
      ctx.strokeStyle = colors.core + "30";
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // Core gradient
      const coreGrad = ctx.createLinearGradient(
        cx - maxRadius * 0.5,
        cy - maxRadius * 0.5,
        cx + maxRadius * 0.5,
        cy + maxRadius * 0.5
      );
      coreGrad.addColorStop(0, colors.core);
      coreGrad.addColorStop(0.5, colors.core + "70");
      coreGrad.addColorStop(1, colors.ring);
      ctx.beginPath();
      ctx.arc(cx, cy, maxRadius * 0.55, 0, Math.PI * 2);
      ctx.fillStyle = coreGrad;
      ctx.fill();

      // Specular highlight
      ctx.beginPath();
      ctx.arc(cx, cy, maxRadius * 0.18, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,0.25)";
      ctx.fill();

      // Glow ring for listening state
      if (state === "listening") {
        const pulseR = maxRadius * (0.9 + Math.sin(t * 3) * 0.15);
        ctx.beginPath();
        ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(6,182,212,${0.2 + Math.sin(t * 3) * 0.15})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Particles
      particlesRef.current.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.life++;

        if (p.life > p.maxLife) {
          p.x = cx + (Math.random() - 0.5) * maxRadius * 1.5;
          p.y = cy + (Math.random() - 0.5) * maxRadius * 1.5;
          p.vx = (Math.random() - 0.5) * 0.4;
          p.vy = (Math.random() - 0.5) * 0.4;
          p.life = 0;
        }

        const alpha = Math.sin((p.life / p.maxLife) * Math.PI) * 0.6;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = colors.particle + Math.round(alpha * 255).toString(16).padStart(2, "0");
        ctx.fill();
      });

      animRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animRef.current);
  }, [state]);

  return (
    <canvas
      ref={canvasRef}
      style={{ display: "block" }}
    />
  );
}
