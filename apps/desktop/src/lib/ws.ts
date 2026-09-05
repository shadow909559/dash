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
