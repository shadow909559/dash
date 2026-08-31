import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, Send, Volume2 } from "lucide-react";
import { useAIStore } from "@/stores/aiStore";
import { useChatStore } from "@/stores/chatStore";
import { getWsClient } from "@/lib/wsClient";
import DASHSpeechSynthesis from "@/lib/voice/SpeechSynthesis";
import { DesktopSpeechCommands } from "@/lib/voice/DesktopSpeechCommands";

/**
 * Voice-first input + response display for the DASH orb interface.
 *
 * - Mic button uses the browser Web Speech API (SpeechRecognition) for
 *   transcription. The backend noop STT is NOT used as the primary path.
 * - Typed or transcribed text is checked for desktop command intents
 *   ("open notepad", "set volume to 30", "take a screenshot", ...). If a
 *   command intent matches, it is routed to the backend `command` handler
 *   (which executes the action) and the result is shown as a small
 *   confirmation plus spoken feedback.
 * - Non-command text goes through `chat.send` → `chat.token` streaming.
 * - `voice.tts_ready` (Piper) playback with browser-speech fallback.
 * - Errors are kept internal (status pill only) and NEVER inserted into the
 *   chat input or conversation.
 * - A tiny top-right status indicator reflects listening/thinking/speaking.
 */
export default function VoiceInterface() {
  const [isListening, setIsListening] = useState(false);
  const [text, setText] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isWakeActive, setIsWakeActive] = useState(false);
  const [response, setResponse] = useState("");
  const { setAIState, setCoreStatus, setCurrentSpeech, setVoiceStatus } = useAIStore();
  const inputRef = useRef<HTMLInputElement>(null);

  const messageIdRef = useRef<string>("");
  const responseRef = useRef<string>("");
  const spokenForRef = useRef<string>("");
const ttsRef = useRef<DASHSpeechSynthesis | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastTtsAudioKeyRef = useRef<string>("");
  // Guard: a given assistant message may only be played once (via Piper).
  // Prevents the same response from being spoken twice.
  const playedTtsMessageIdsRef = useRef<Set<string>>(new Set());

  // Browser Web Speech API recognition (fallback only)
  const recognitionRef = useRef<any>(null);
  const commandsRef = useRef<DesktopSpeechCommands | null>(null);

  // Media recorder for backend STT
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Speak the provided text using the browser speech synthesis engine.
  const speakText = useCallback(async (textToSpeak: string) => {
    if (!textToSpeak || !textToSpeak.trim()) return;
    try {
      if (!ttsRef.current) {
        ttsRef.current = new DASHSpeechSynthesis({});
        await ttsRef.current.initialize();
      }
      setCoreStatus("speaking");
      setAIState("talking");
      await ttsRef.current.speak(textToSpeak);
    } catch (err) {
      console.warn("[VoiceInterface] TTS speak failed:", err);
    } finally {
      setCoreStatus("idle");
      setAIState("idle");
    }
  }, [setAIState, setCoreStatus]);

// Play backend-generated TTS audio (voice.tts_ready / Piper).
  const playTtsAudio = useCallback((audioBase64: string, messageId?: string) => {
    if (!audioBase64) return;
    // Duplicate-speech guard: a given assistant message may only be played
    // once. This ensures the same reply is never spoken twice (e.g. if a
    // duplicate voice.tts_ready arrives for the same message_id).
    if (messageId) {
      if (playedTtsMessageIdsRef.current.has(messageId)) return;
      playedTtsMessageIdsRef.current.add(messageId);
    }
    try {
      const src = `data:audio/wav;base64,${audioBase64}`;
      if (lastTtsAudioKeyRef.current === src) return;
      lastTtsAudioKeyRef.current = src;
      if (audioRef.current) {
        audioRef.current.pause();
      }
      const audio = new Audio(src);
      audioRef.current = audio;
      setCoreStatus("speaking");
      setAIState("talking");
      audio.onended = () => {
        setCoreStatus("idle");
        setAIState("idle");
        setIsProcessing(false);
      };
      audio.onerror = () => {
        setCoreStatus("idle");
        setAIState("idle");
        setIsProcessing(false);
      };
      audio.play().catch((err) => {
        console.warn("[VoiceInterface] TTS audio play failed:", err);
        setCoreStatus("idle");
        setAIState("idle");
        setIsProcessing(false);
      });
    } catch (err) {
      console.warn("[VoiceInterface] TTS audio decode failed:", err);
      setCoreStatus("idle");
      setAIState("idle");
    }
  }, [setAIState, setCoreStatus]);

  /**
   * Route a text phrase to a backend desktop command if it is a clear
   * action intent. Returns true if handled as a command.
   */
  const tryExecuteCommand = useCallback(async (
    raw: string,
  ): Promise<{ handled: boolean; message?: string }> => {
    const lower = raw.trim().toLowerCase();
    if (!lower) return { handled: false };

    const ws = getWsClient();
    if (!ws.isConnected()) return { handled: false };

    // Open / launch an application
    const openMatch = lower.match(/^(?:open|launch|start)\s+(.+)$/);
    if (openMatch) {
      const app = openMatch[1].trim();
      setCoreStatus("executing");
      if (ws.sendCommand("launch_app", { app })) {
        return { handled: true, message: `Opening ${app}.` };
      }
      setCoreStatus("idle");
      return { handled: false };
    }

    // Close / quit an application
    const closeMatch = lower.match(/^(?:close|quit|exit)\s+(.+)$/);
    if (closeMatch) {
      const app = closeMatch[1].trim();
      setCoreStatus("executing");
      if (ws.sendCommand("close_window", { title: app })) {
        return { handled: true, message: `Closing ${app}.` };
      }
      setCoreStatus("idle");
      return { handled: false };
    }

    // Set volume to N
    const volumeSetMatch = lower.match(/set\s+volume\s+to\s+(\d{1,3})/);
    if (volumeSetMatch) {
      const level = Math.max(0, Math.min(100, parseInt(volumeSetMatch[1], 10)));
      setCoreStatus("executing");
      if (ws.sendCommand("set_volume", { level })) {
        return { handled: true, message: `Volume set to ${level}.` };
      }
      setCoreStatus("idle");
      return { handled: false };
    }

    // Volume up / down
    if (/volume\s*up/.test(lower)) {
      setCoreStatus("executing");
      if (ws.sendCommand("volume_up", { amount: 5 })) {
        return { handled: true, message: "Volume up." };
      }
      setCoreStatus("idle");
      return { handled: false };
    }
    if (/volume\s*down/.test(lower)) {
      setCoreStatus("executing");
      if (ws.sendCommand("volume_down", { amount: 5 })) {
        return { handled: true, message: "Volume down." };
      }
      setCoreStatus("idle");
      return { handled: false };
    }

    // Take a screenshot
    if (/take\s+a?\s*screenshot/.test(lower)) {
      setCoreStatus("executing");
      if (ws.sendCommand("take_screenshot", {})) {
        return { handled: true, message: "Screenshot captured." };
      }
      setCoreStatus("idle");
      return { handled: false };
    }

    // Lock / sleep / restart / shutdown
    if (/^lock\s*(the)?\s*(desktop|pc|computer)?$/.test(lower)) {
      setCoreStatus("executing");
      if (ws.sendCommand("lock_desktop", {})) {
        return { handled: true, message: "Locking desktop." };
      }
      setCoreStatus("idle");
      return { handled: false };
    }
    if (/^sleep\s*(the)?\s*(desktop|pc|computer)?$/.test(lower)) {
      setCoreStatus("executing");
      if (ws.sendCommand("sleep_desktop", {})) {
        return { handled: true, message: "Sleeping desktop." };
      }
      setCoreStatus("idle");
      return { handled: false };
    }

    return { handled: false };
  }, [setCoreStatus]);

  /**
   * Submit a message. Detects desktop commands first; otherwise sends as
   * chat. Never turns errors into conversational text.
   */
  const submitText = useCallback(async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed || isProcessing) return;

    setIsProcessing(true);
    setAIState("thinking");
    setCoreStatus("thinking");
    setCurrentSpeech(trimmed);

    // Try to execute as a desktop command first.
    const cmd = await tryExecuteCommand(trimmed);
    if (cmd.handled) {
      setResponse(cmd.message || "Done.");
      setCoreStatus("idle");
      setAIState("idle");
      setIsProcessing(false);
      setText("");
      speakText(cmd.message || "Done.");
      return;
    }

    const messageId = `msg_${Date.now()}`;
    messageIdRef.current = messageId;
    responseRef.current = "";
    setResponse("");

    const ws = getWsClient();
    const sent = ws.sendChatMessage(messageId, trimmed);
    if (!sent) {
      const chatStore = useChatStore.getState();
      chatStore.setProcessing(false);
      chatStore.setCurrentMessageId(null);
      setIsProcessing(false);
      setCoreStatus("idle");
      setAIState("idle");
      setText("");
      // Show a small status-only error; do not write technical text to chat.
      setResponse("");
      return;
    }
    setText("");
  }, [isProcessing, setAIState, setCoreStatus, setCurrentSpeech, tryExecuteCommand, speakText]);

  // Connect the singleton WebSocket client on mount.
  useEffect(() => {
    const ws = getWsClient();

    // VoiceInterface only needs to handle TTS audio playback
    // Chat callbacks are already set globally in App.tsx via initializeWebSocket()
    const onTtsReady = (data: Record<string, unknown>) => {
      const msgId = (data.message_id as string) || messageIdRef.current;
      // Only play if this is the current active message
      if (msgId === messageIdRef.current) {
        playTtsAudio(
          data.audio_base64 as string,
          msgId
        );
        // Reset processing after audio playback completes
        setTimeout(() => {
          setIsProcessing(false);
          setCoreStatus("idle");
          setAIState("idle");
        }, 5000);
      }
    };

    const onCommandResult = (data: Record<string, unknown>) => {
      const result = (data.result as string) || "";
      if (result) {
        setResponse(result);
        // Speak the command result
        speakText(result);
      }
    };

    ws.on("voice.tts_ready", onTtsReady);
    ws.on("command_result", onCommandResult);

    return () => {
      try {
        ws.off("voice.tts_ready", onTtsReady);
        ws.off("command_result", onCommandResult);

        // Stop TTS on unmount
        if (ttsRef.current) {
          ttsRef.current.stop();
          ttsRef.current = null;
        }

        // Stop audio playback
        if (audioRef.current) {
          audioRef.current.pause();
          audioRef.current = null;
        }

        // Stop speech recognition
        if (recognitionRef.current) {
          try {
            recognitionRef.current.stop();
          } catch {
            // ignore if already stopped
          }
          recognitionRef.current = null;
        }

        // Stop media recorder
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
          try {
            mediaRecorderRef.current.stop();
          } catch {
            // ignore
          }
          mediaRecorderRef.current = null;
        }

        // Clear audio chunks
        audioChunksRef.current = [];

        // Clear played message IDs
        playedTtsMessageIdsRef.current.clear();
      } catch {
        // ignore cleanup errors
      }
    };
  }, [setAIState, setCoreStatus, setCurrentSpeech, speakText, playTtsAudio]);

  /**
   * Stop any active speech recognition.
   */
  const stopListening = useCallback(() => {
    // Stop media recorder (backend STT)
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // ignore
      }
      mediaRecorderRef.current = null;
    }

    // Stop browser recognition (fallback)
    try {
      recognitionRef.current?.stop();
    } catch {
      // ignore
    }
    setIsListening(false);
    setAIState("idle");
    setCoreStatus("idle");
  }, [setAIState, setCoreStatus]);

  /**
   * Start speech recognition using backend STT via MediaRecorder.
   */
  const startListening = useCallback(async () => {
    setCoreStatus("listening");
    setAIState("listening");

    const ws = getWsClient();
    if (!ws.isConnected()) {
      console.warn("[VoiceInterface] WebSocket not connected, cannot use backend STT");
      setIsListening(false);
      setCoreStatus("error");
      setAIState("idle");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4'
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        setIsListening(false);
        setCoreStatus("idle");
        setAIState("idle");

        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());

        // Send audio to backend for STT
        if (audioChunksRef.current.length > 0) {
          const audioBlob = new Blob(audioChunksRef.current, {
            type: mediaRecorder.mimeType
          });

          try {
            const reader = new FileReader();
            reader.onloadend = () => {
              const base64Audio = (reader.result as string).split(',')[1];
              const requestId = `stt_${Date.now()}`;

              // Send to backend STT
              ws.sendVoiceSTT(requestId, base64Audio);

              // Handle STT response via WebSocket event
              const handleSttDone = (data: any) => {
                if (data.request_id === requestId) {
                  const transcript = data.text || "";
                  if (transcript && transcript.trim()) {
                    setCurrentSpeech(transcript);
                    setText(transcript);
                    submitText(transcript);
                  }
                  ws.off("voice.stt.done", handleSttDone);
                  ws.off("voice.stt.error", handleSttError);
                }
              };

              const handleSttError = (data: any) => {
                if (data.request_id === requestId) {
                  console.warn("[VoiceInterface] STT error:", data.error);
                  ws.off("voice.stt.done", handleSttDone);
                  ws.off("voice.stt.error", handleSttError);
                  // Isolate STT errors to only the voice system
                  setIsListening(false);
                  setCoreStatus("idle");
                  setAIState("idle");
                  setVoiceStatus("error");
                  setTimeout(() => setVoiceStatus("ready"), 3000);
                }
              };

              ws.on("voice.stt.done", handleSttDone);
              ws.on("voice.stt.error", handleSttError);
            };
            reader.readAsDataURL(audioBlob);
          } catch (err) {
            console.warn("[VoiceInterface] Failed to process audio:", err);
          }
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsListening(true);
      setVoiceStatus("listening"); // Mark voice system as listening

      // Auto-stop after 10 seconds of recording
      setTimeout(() => {
        if (mediaRecorder.state === "recording") {
          mediaRecorder.stop();
        }
      }, 10000);

    } catch (err) {
      console.warn("[VoiceInterface] Failed to access microphone:", err);
      setIsListening(false);
      // Only update voice-specific state - never affect main chat or AI state
      setVoiceStatus("error");
      // Auto-reset voice status after 3 seconds
      setTimeout(() => setVoiceStatus("ready"), 3000);

      // Fallback to browser SpeechRecognition if backend STT fails
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SR) {
        try {
          const recognition = new SR();
          recognition.lang = "en-US";
          recognition.interimResults = false;
          recognition.maxAlternatives = 1;
          recognition.continuous = false;

          recognition.onresult = (event: any) => {
            const transcript = (event.results[0]?.[0]?.transcript || "").trim();
            setIsListening(false);
            setVoiceStatus("ready");
            if (transcript) {
              setCurrentSpeech(transcript);
              setText(transcript);
              submitText(transcript);
            }
          };
          recognition.onerror = (event: any) => {
            console.warn("[VoiceInterface] Fallback SpeechRecognition error:", event?.error);
            setIsListening(false);
            // Only mark voice system as error - never affect main chat connection
            setVoiceStatus("error");
            // Auto-reset voice status after 3 seconds
            setTimeout(() => setVoiceStatus("ready"), 3000);
          };
          recognition.onend = () => {
            setIsListening(false);
            // Reset voice status to ready when recognition ends normally
            setVoiceStatus("ready");
          };

          recognitionRef.current = recognition;
          recognition.start();
          setIsListening(true);
          setVoiceStatus("listening");
        } catch (fallbackErr) {
          console.warn("[VoiceInterface] Fallback SpeechRecognition failed:", fallbackErr);
          setVoiceStatus("error");
          setTimeout(() => setVoiceStatus("ready"), 3000);
        }
      }
    }
  }, [setAIState, setCoreStatus, setCurrentSpeech, submitText]);

  const handleSubmit = useCallback(() => {
    submitText(text);
  }, [text, submitText]);

  const handleCancel = useCallback(() => {
    setIsProcessing(false);
    setCoreStatus("idle");
    setAIState("idle");
    setResponse("");
    // Clear the assistant message from chat store
    useChatStore.getState().clearMessages();
  }, [setAIState, setCoreStatus]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        bottom: 40,
        left: "50%",
        transform: "translateX(-50%)",
        width: "min(480px, calc(100vw - 32px))",
        zIndex: 30,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        alignItems: "center",
      }}
    >
      {/* Assistant response display — small elegant panel */}
      <AnimatePresence>
        {response && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            style={{
              width: "100%",
              maxHeight: 140,
              overflowY: "auto",
              padding: "12px 18px",
              borderRadius: 14,
              background: "rgba(10, 12, 16, 0.72)",
              border: "1px solid rgba(255, 150, 0, 0.22)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              color: "rgba(255, 255, 255, 0.95)",
              fontSize: 14,
              lineHeight: 1.5,
              whiteSpace: "pre-wrap",
              maxWidth: "100%",
            }}
          >
            {response}
          </motion.div>
        )}
      </AnimatePresence>

      <div style={{ display: "flex", gap: 12, alignItems: "center", width: "100%" }}>
        {/* Mic button — click to start recording, click again to stop */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => (isListening ? stopListening() : startListening())}
          disabled={isProcessing}
          aria-label={isListening ? "Stop listening" : "Start listening"}
          id="voice-mic-button"
          style={{
            width: 52,
            height: 52,
            borderRadius: "50%",
            flexShrink: 0,
            background: isListening
              ? "radial-gradient(circle, rgba(255, 138, 0, 0.3), rgba(255, 138, 0, 0.08))"
              : isWakeActive
                ? "radial-gradient(circle, rgba(255, 179, 71, 0.22), rgba(255, 179, 71, 0.06))"
                : "radial-gradient(circle, rgba(255, 138, 0, 0.2), rgba(255, 138, 0, 0.06))",
            border: isListening
              ? "2px solid rgba(255, 138, 0, 0.5)"
              : isWakeActive
                ? "2px solid rgba(255, 179, 71, 0.4)"
                : "2px solid rgba(255, 138, 0, 0.3)",
            backdropFilter: "blur(30px)",
            WebkitBackdropFilter: "blur(30px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            boxShadow: isListening
              ? "0 0 30px rgba(255, 138, 0, 0.35)"
              : isWakeActive
                ? "0 0 24px rgba(255, 179, 71, 0.25)"
                : "0 0 20px rgba(255, 138, 0, 0.2)",
            transition: "all 0.3s ease",
          }}
        >
          <motion.div
            animate={isListening ? { scale: [1, 1.3, 1] } : isWakeActive ? { scale: [1, 1.1, 1] } : {}}
            transition={{ duration: isListening ? 0.5 : 2, repeat: Infinity, ease: [0.34, 1.56, 0.64, 1] }}
          >
            {isListening ? (
              <Mic size={22} color="#ff8a00" strokeWidth={2} />
            ) : isWakeActive ? (
              <Volume2 size={22} color="#ffb347" strokeWidth={2} />
            ) : (
              <Mic size={22} color="#ff9f1c" strokeWidth={2} />
            )}
          </motion.div>
        </motion.button>

        {/* Text input */}
        <div style={{ flex: 1, position: "relative" }}>
          <input
            ref={inputRef}
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={isListening ? "Listening..." : "Ask DASH anything..."}
            disabled={isProcessing}
            style={{
              width: "100%",
              padding: "16px 22px",
              borderRadius: 30,
              background: "rgba(10, 12, 16, 0.72)",
              border: "1px solid rgba(255, 150, 0, 0.22)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              color: "rgba(255, 255, 255, 0.95)",
              fontSize: 15,
              /* a11y: removed outline:none — global :focus-visible handles focus */
              transition: "all 0.3s ease",
            }}
          />
          {isProcessing && (
            <motion.div
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1, repeat: Infinity }}
              style={{
                position: "absolute",
                right: 22,
                top: "50%",
                transform: "translateY(-50%)",
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: "#ff9f1c",
                boxShadow: "0 0 16px rgba(255, 150, 0, 0.5)",
              }}
            />
          )}
        </div>

        {/* Send button - hide during processing, show cancel instead */}
        {!isProcessing ? (
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleSubmit}
            disabled={!text.trim()}
            style={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              flexShrink: 0,
              background: text.trim()
                ? "radial-gradient(circle, rgba(255, 179, 71, 0.22), rgba(255, 179, 71, 0.06))"
                : "radial-gradient(circle, rgba(255, 138, 0, 0.16), rgba(255, 138, 0, 0.05))",
              border: text.trim()
                ? "2px solid rgba(255, 179, 71, 0.4)"
                : "2px solid rgba(255, 138, 0, 0.25)",
              backdropFilter: "blur(30px)",
              WebkitBackdropFilter: "blur(30px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: text.trim() ? "pointer" : "not-allowed",
              opacity: text.trim() ? 1 : 0.5,
              transition: "all 0.3s ease",
            }}
          >
            <Send size={20} color={text.trim() ? "#ffb347" : "#ff9f1c"} strokeWidth={2} />
          </motion.button>
        ) : (
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleCancel}
            style={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              flexShrink: 0,
              background: "radial-gradient(circle, rgba(239, 68, 68, 0.22), rgba(239, 68, 68, 0.06))",
              border: "2px solid rgba(239, 68, 68, 0.4)",
              backdropFilter: "blur(30px)",
              WebkitBackdropFilter: "blur(30px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              transition: "all 0.3s ease",
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </motion.button>
        )}
      </div>
    </div>
  );
}