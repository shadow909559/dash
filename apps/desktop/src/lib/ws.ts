import { getWsClient } from "@/lib/wsClient";
import { useChatStore } from "@/stores/chatStore";
import { useAIStore } from "@/stores/aiStore";
import { useActivityStore } from "@/stores/activityStore";
import { useOrchestratorStore } from "@/stores/orchestratorStore";

let initialized = false;

export function initializeWebSocket() {
  const wsClient = getWsClient();

  wsClient.onStatus((connected, authenticated, state) => {
    if (state === "connected" && authenticated) {
      useAIStore.getState().setWebSocketStatus("connected");
      useAIStore.getState().setSystemStatus("online");
      useActivityStore.getState().push("Connection connected", "system");
    } else if (state === "reconnecting" || state === "connecting") {
      useAIStore.getState().setWebSocketStatus("reconnecting");
    } else {
      useAIStore.getState().setWebSocketStatus("disconnected");
    }
  });

  wsClient.setChatCallbacks({
    onStatus: (messageId, status, detail) => {
      const chatStore = useChatStore.getState();
      if (messageId && chatStore.currentMessageId && messageId !== chatStore.currentMessageId) return;
      if (detail) chatStore.setStatusDetail(detail);
      if (status === "thinking") {
        useAIStore.getState().setAIProviderStatus("thinking");
        useAIStore.getState().setCoreStatus("thinking");
        useAIStore.getState().setChatStatus("processing");
        useActivityStore.getState().push("Thinking", "ai");
      } else if (status === "responding") {
        useAIStore.getState().setAIProviderStatus("responding");
        useAIStore.getState().setDashState("speaking");
        useActivityStore.getState().push("Response generated", "ai");
      }
    },
    onToken: (messageId, token) => {
      const chatStore = useChatStore.getState();
      if (!chatStore.currentMessageId || messageId === chatStore.currentMessageId) {
        chatStore.updateAssistantMessage(token);
        useAIStore.getState().setAIProviderStatus("responding");
        useAIStore.getState().setChatStatus("processing");
      }
    },
    onDone: (messageId, conversationId) => {
      const chatStore = useChatStore.getState();
      if (!chatStore.currentMessageId || messageId === chatStore.currentMessageId) {
        chatStore.commitAssistantMessage();
        if (conversationId) chatStore.setConversationId(conversationId);
      } else {
        chatStore.setProcessing(false);
      }
      useAIStore.getState().setCoreStatus("idle");
      useAIStore.getState().setAIProviderStatus("ready");
      useAIStore.getState().setChatStatus("idle");
      useAIStore.getState().setDashState("idle");
      useActivityStore.getState().push("Response complete", "ai");
    },
    onError: (messageId, error) => {
      const chatStore = useChatStore.getState();
      const relevant =
        !messageId ||
        messageId === chatStore.currentMessageId ||
        chatStore.isProcessing;
      if (!relevant) return;
      console.error(`Chat error for message ${messageId}: ${error}`);
      chatStore.resetOnError(error);
      useAIStore.getState().setChatStatus("error");
      useAIStore.getState().setCoreStatus("error");
      useAIStore.getState().setAIProviderStatus("error");
      useActivityStore.getState().push("Chat error: " + error, "error");
      // Always clear processing state on error
      chatStore.setProcessing(false);
      chatStore.setCurrentMessageId(null);
      setTimeout(() => {
        useAIStore.getState().setChatStatus("idle");
        useAIStore.getState().setAIProviderStatus("ready");
        useAIStore.getState().setCoreStatus("idle");
      }, 3000);
    },
  });

  // Orchestrator events
  const orchEvents = [
    "orchestrator.status", "orchestrator.plan", "orchestrator.step_start",
    "orchestrator.step_token", "orchestrator.step_done", "orchestrator.step_error",
    "orchestrator.complete", "orchestrator.error", "orchestrator.cancelled",
  ];
  for (const evt of orchEvents) {
    wsClient.on(evt, (data) => {
      useOrchestratorStore.getState().handleEvent(evt, data);
    });
  }

  // DASH's own speech drives the orb (#130). Server-side Piper playback
  // arrives as voice.amplitude — the backend's real PCM measurement while
  // the speaker plays. Client-played TTS (voice.tts_ready) is measured
  // locally with a WebAudio analyser tap. Both forward the same window
  // event the orb surfaces consume.
  wsClient.on("voice.amplitude", (data) => {
    const level = (data as { level?: number }).level;
    if (typeof level !== "number" || !Number.isFinite(level)) return;
    window.dispatchEvent(
      new CustomEvent("dashamplitude", { detail: Math.max(0, Math.min(1, level)) }),
    );
  });

  // Real amplitude of client-played TTS: analyser tap on the audio graph
  // (replaces the old simulated waveform). The analyser is wired as a
  // pass-through to the destination so the element keeps playing once its
  // output is routed through the context.
  let ttsAudioCtx: AudioContext | null = null;
  const emitClientTtsAmplitude = (analyser: AnalyserNode, audio: HTMLAudioElement) => {
    if (audio.ended || audio.paused) return;
    const buf = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) {
      const v = (buf[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / buf.length);
    const level = Math.min(1, Math.sqrt(rms) * 1.6);
    window.dispatchEvent(new CustomEvent("dashamplitude", { detail: level }));
    requestAnimationFrame(() => emitClientTtsAmplitude(analyser, audio));
  };

  // Voice TTS — play audio when backend sends voice.tts_ready
  wsClient.on("voice.tts_ready", (data) => {
    const audioB64 = (data.audio_base64 as string) || (data.audio as string) || "";
    if (!audioB64) return;
    try {
      const bytes = Uint8Array.from(atob(audioB64), (c) => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: "audio/wav" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        window.dispatchEvent(new CustomEvent("dashamplitude", { detail: 0 }));
      };
      audio
        .play()
        .then(() => {
          try {
            const Ctx = window.AudioContext || (window as any).webkitAudioContext;
            ttsAudioCtx = ttsAudioCtx || new Ctx();
            if (ttsAudioCtx.state === "suspended") void ttsAudioCtx.resume();
            const source = ttsAudioCtx.createMediaElementSource(audio);
            const analyser = ttsAudioCtx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            analyser.connect(ttsAudioCtx.destination);
            requestAnimationFrame(() => emitClientTtsAmplitude(analyser, audio));
          } catch (err) {
            console.warn("TTS analyser tap failed:", err);
          }
        })
        .catch((err) => console.warn("TTS playback failed:", err));
      useActivityStore.getState().push("Speaking response", "voice");
    } catch (err) {
      console.warn("TTS decode failed:", err);
    }
  });

  if (!initialized) {
    initialized = true;
    useAIStore.getState().setWebSocketStatus("connecting");
    useActivityStore.getState().push("System online", "system");
    wsClient.connect().catch((err) => {
      console.error("Failed to connect WebSocket:", err);
      useAIStore.getState().setWebSocketStatus("disconnected");
    });
  } else if (!wsClient.isConnected()) {
    wsClient.connect().catch(() => {
      useAIStore.getState().setWebSocketStatus("disconnected");
    });
  }
}
