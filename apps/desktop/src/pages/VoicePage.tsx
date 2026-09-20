import { useState, useRef, useEffect, useCallback } from "react";
import { useAIStore } from "@/stores/aiStore";
import {
  installOrbAppearanceSync,
  resolveOrbColors,
  resolveOrbSpeed,
  resolveOrbWave,
  useOrbAppearanceStore,
} from "@/stores/orbAppearanceStore";
import { getWsClient } from "@/lib/wsClient";
import PlasmaRing from "@/components/PlasmaRing";
import { registerMicAmplitudeSource } from "@/lib/voice/micAmplitudeProducer";
import { Mic, MicOff, Send, Volume2, VolumeX, Square, RotateCcw, Sparkles } from "lucide-react";

/**
 * Shape one amplitude level (0..1) into a 32-bar voice profile (#133):
 * a soft arch across the bars with gentle per-bar flutter and a whisper
 * floor, so DASH's playback amplitude reads as a speaking voice rather
 * than a flat wall. Deterministic given `t` — the caller passes a time
 * seed so the flutter moves frame to frame.
 */
function shapeBars(level: number, barCount = 32, t = Date.now()): number[] {
  return Array.from({ length: barCount }, (_, i) => {
    const center = Math.abs(i - (barCount - 1) / 2) / ((barCount - 1) / 2); // 0 center → 1 edge
    const arch = 1 - center * 0.55;
    const flutter = 0.85 + 0.15 * Math.sin(t / 90 + i * 0.9);
    return Math.max(0.05, Math.min(1, level * arch * flutter));
  });
}

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
  // Backend wake-loop partials (decisions.md #118): interim transcripts
  // from the server-side loop, shown while the browser mic is not the
  // active capture surface. final:true clears the interim line.
  const voicePartial = useAIStore((s) => s.voicePartial);
  const [history, setHistory] = useState<
    Array<{ role: "user" | "dash"; text: string; time: number }>
  >([]);
  const [isMuted, setIsMuted] = useState(false);
  const [waveformAmplitudes, setWaveformAmplitudes] = useState<number[]>(
    Array(32).fill(0.1)
  );
  // Falling peak caps for the waveform (per-bar hold-and-decay peaks)
  const peaksRef = useRef<number[]>(Array(32).fill(0));
  const [ttsActive, setTtsActive] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const animationFrameRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // Live mic amplitude 0..1 for the plasma orb — ref-driven so the WebGL
  // component reads it per frame without React re-renders.
  const orbAmplitudeRef = useRef(0);
  // The mic's OWN amplitude is merged in by the shared producer's
  // 'micamplitude' events (#131); 'dashamplitude' (#130) merges DASH's
  // speech. This ref only needs the max-decay merge, no local overwrite.
  const micAmpHandleRef = useRef<import("@/lib/voice/micAmplitudeProducer").MicAmplitudeHandle | null>(null);
  // DASH's playback level for the WAVEFORM BARS (#133): fed by
  // 'dashamplitude' events, per-frame decay, max-merged into the bars so
  // they show DASH's speech instead of going idle while it talks.
  const dashLevelRef = useRef(0);
  useEffect(() => {
    const onDashAmp = (e: Event) => {
      const detail = (e as CustomEvent<number>).detail;
      if (typeof detail === "number" && Number.isFinite(detail)) {
        dashLevelRef.current = Math.max(0, Math.min(1, detail));
      }
    };
    window.addEventListener("dashamplitude", onDashAmp);
    return () => window.removeEventListener("dashamplitude", onDashAmp);
  }, []);

  // ─── Waveform Animation ───
  const animateWaveform = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) {
      // Mic off: idle breathing bars — unless DASH is speaking, in which
      // case the bars carry DASH's real playback amplitude (#133).
      dashLevelRef.current *= 0.92;
      const dash = dashLevelRef.current;
      if (dash > 0.01) {
        const shaped = shapeBars(dash);
        const peaks = peaksRef.current;
        for (let i = 0; i < peaks.length; i++) {
          peaks[i] = Math.max(shaped[i], peaks[i] - 0.03);
        }
        setWaveformAmplitudes(shaped);
        animationFrameRef.current = requestAnimationFrame(animateWaveform);
        return;
      }
      const idle = (i: number) => {
        const t = Date.now() / 1000;
        return (
          0.08 +
          0.04 * Math.sin(t * 1.5 + i * 0.3) +
          0.02 * Math.sin(t * 2.7 + i * 0.5)
        );
      };
      const peaks = peaksRef.current;
      for (let i = 0; i < peaks.length; i++) {
        peaks[i] = Math.max(idle(i), peaks[i] - 0.03);
      }
      setWaveformAmplitudes((prev) => prev.map((_, i) => idle(i)));
      animationFrameRef.current = requestAnimationFrame(animateWaveform);
      return;
    }

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(dataArray);

    // Sample 32 bars from the frequency data, log-spaced so voice
    // energy (low-mid) isn't crammed into the first few bars.
    const barCount = 32;
    const newAmplitudes = Array.from({ length: barCount }, (_, i) => {
      // Log-spaced bin centers across the frequency range
      const t0 = i / barCount, t1 = (i + 1) / barCount;
      const b0 = Math.floor(Math.pow(dataArray.length, t0));
      const b1 = Math.max(b0 + 1, Math.floor(Math.pow(dataArray.length, t1)));
      let peak = 0;
      for (let b = b0; b < b1 && b < dataArray.length; b++) peak = Math.max(peak, dataArray[b]);
      return Math.max(0.05, peak / 255);
    });

    // DASH's speech (#133) merges into the bars even while the mic is on
    // (e.g. echo during a reply): louder source wins per bar.
    dashLevelRef.current *= 0.92;
    const dash = dashLevelRef.current;
    if (dash > 0.01) {
      const shaped = shapeBars(dash);
      for (let i = 0; i < barCount; i++) {
        newAmplitudes[i] = Math.max(newAmplitudes[i], shaped[i]);
      }
    }

    // Falling peak caps: instant rise, ~500ms hold-free decay
    const peaks = peaksRef.current;
    for (let i = 0; i < barCount; i++) {
      peaks[i] = newAmplitudes[i] > peaks[i] ? newAmplitudes[i] : Math.max(newAmplitudes[i], peaks[i] - 0.035);
    }

    // Mic frequency bars + DASH's playback amplitude (#133) drive the
    // waveform; the ORB's amplitude comes from the event merges
    // (micamplitude #131 / dashamplitude #130), not from these bars.
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
      // Shared producer (#131): the home/floating orbs pulse with this mic
      // too, not just the local orb. Auto-detaches when tracks stop.
      micAmpHandleRef.current = registerMicAmplitudeSource(stream);

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
    micAmpHandleRef.current?.stop();
    micAmpHandleRef.current = null;
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
        {/* PlasmaRing renders at true pixel size — no CSS up-scaling, which
            would blur the wireframe and over-saturate the additive blend. */}
        <FullVoiceOrb state={orbState} amplitudeRef={orbAmplitudeRef} />
      </div>

      {/* Waveform visualization — frequency-mirrored bars with falling
          peak caps, per-state gradient, and a soft under-glow. */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 2,
          height: 56,
          marginTop: 32,
          zIndex: 5,
          position: "relative",
        }}
      >
        {(() => {
          const stateColor =
            orbState === "listening" ? "6,182,212"
            : orbState === "thinking" ? "168,85,247"
            : orbState === "speaking" ? "59,130,246"
            : null;
          const peaks = peaksRef.current;
          return waveformAmplitudes.map((amp, i) => {
            const h = Math.max(4, amp * 44);
            const cap = Math.max(amp + 0.04, peaks[i]);
            const capH = Math.max(2, cap * 44);
            const rgb = stateColor ?? "255,255,255";
            const alpha = stateColor ? 0.35 + amp * 0.65 : 0.1 + amp * 0.15;
            // Center-weighted energy for the glow
            const center = 1 - Math.abs(i - 15.5) / 16;
            return (
              <div key={i} style={{ position: "relative", width: 3, height: 56, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {/* Upper bar (mirrored spectrum) */}
                <div style={{
                  position: "absolute", bottom: 28, width: 3,
                  height: h / 2, borderRadius: "2px 2px 0 0",
                  background: `linear-gradient(to top, rgba(${rgb},${alpha}), rgba(${rgb},${alpha * 0.35}))`,
                  transition: "height 0.08s ease",
                }} />
                {/* Lower bar */}
                <div style={{
                  position: "absolute", top: 28, width: 3,
                  height: h / 2, borderRadius: "0 0 2px 2px",
                  background: `linear-gradient(to bottom, rgba(${rgb},${alpha}), rgba(${rgb},${alpha * 0.35}))`,
                  transition: "height 0.08s ease",
                }} />
                {/* Falling peak cap */}
                <div style={{
                  position: "absolute", bottom: 28 + capH / 2 - 1, width: 3, height: 2,
                  borderRadius: 1, background: `rgba(${rgb},${Math.min(1, alpha + 0.25)})`,
                  transition: "bottom 0.08s ease",
                }} />
                {/* Soft under-glow on live audio */}
                {stateColor && (
                  <div style={{
                    position: "absolute", top: "50%", left: "50%",
                    width: 6, height: 6, transform: "translate(-50%, -50%)",
                    borderRadius: "50%",
                    background: `rgba(${rgb},${0.10 * center * amp})`,
                    filter: "blur(4px)",
                  }} />
                )}
              </div>
            );
          });
        })()}
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
        {voicePartial && !liveTranscript ? (
          <div
            style={{
              fontSize: 18,
              fontWeight: 500,
              color: voicePartial.final
                ? "var(--dash-text-bright)"
                : "var(--dash-text-dim, var(--dash-text))",
              lineHeight: 1.5,
              fontStyle: voicePartial.final ? "normal" : "italic",
              animation: "fadeIn 0.3s ease",
            }}
          >
            "{voicePartial.text}"{!voicePartial.final && <span style={{ opacity: 0.55 }}> …</span>}
          </div>
        ) : liveTranscript ? (
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
        aria-label="Voice command input"
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

/** Full-voice Orb — WebGL PlasmaRing with the voice-state palette */
const VOICE_ORB_PALETTES: Record<string, string[]> = {
  listening: ["#06b6d4", "#0891b2"],
  thinking: ["#a855f7", "#7c3aed"],
  speaking: ["#3b82f6", "#2563eb"],
  error: ["#ef4444", "#7f1d1d"],
  disconnected: ["#6b7280", "#4b5563"],
};

const VOICE_ORB_SPEEDS: Record<string, number> = {
  listening: 120,
  thinking: 150,
  speaking: 100,
  error: 30,
  disconnected: 20,
};

function FullVoiceOrb({ state, amplitudeRef }: { state: string; amplitudeRef: { current: number } }) {
  const appearance = useOrbAppearanceStore();

  useEffect(() => installOrbAppearanceSync(), []);  // Amplitude into the WebGL orb (#130 + #131): DASH's own speech
  // ('dashamplitude') and the owner's mic ('micamplitude' from the shared
  // producer) both feed the same ref — max-decay merge, explicit 0 snaps
  // to idle.
  useEffect(() => {
    const onAmp = (e: Event) => {
      const detail = (e as CustomEvent<number>).detail;
      if (typeof detail === "number" && Number.isFinite(detail)) {
        amplitudeRef.current =
          detail === 0
            ? 0
            : Math.max(amplitudeRef.current * 0.75, Math.max(0, Math.min(1, detail)));
      }
    };
    window.addEventListener("dashamplitude", onAmp);
    window.addEventListener("micamplitude", onAmp);
    return () => {
      window.removeEventListener("dashamplitude", onAmp);
      window.removeEventListener("micamplitude", onAmp);
    };
  }, [amplitudeRef]);

  const statePalette = VOICE_ORB_PALETTES[state] ?? ["#4d94ff", "#3b82f6"];
  const stateSpeed = VOICE_ORB_SPEEDS[state] ?? 60;
  const stateWave = state === "listening" ? 30 : state === "thinking" ? 36 : 22;

  return (
    <PlasmaRing
      background="transparent"
      colors={resolveOrbColors(appearance, statePalette)}
      speed={resolveOrbSpeed(appearance, stateSpeed)}
      waveHeight={resolveOrbWave(appearance, stateWave)}
      amplitudeRef={amplitudeRef}
      scale={28}
      density={64}
      width={360}
      height={360}
    />
  );
}
