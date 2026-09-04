import { create } from "zustand";
import { getWsClient } from "@/lib/wsClient";
import { useAIStore } from "./aiStore";
import { usePanelStore } from "./panelStore";
import { useActivityStore } from "./activityStore";
import { detectIntent } from "@/lib/intent";
import { runResearch } from "@/lib/research";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatState {
  messages: ChatMessage[];
  assistantMessage: ChatMessage | null;
  input: string;
  conversationId: string | null;
  isProcessing: boolean;
  currentMessageId: string | null;
  requestTimeout: ReturnType<typeof setTimeout> | null;
  statusDetail: string;
  setInput: (input: string) => void;
  sendMessage: (override?: string, agentMode?: string) => void;
  addMessage: (message: ChatMessage) => void;
  updateAssistantMessage: (token: string) => void;
  commitAssistantMessage: () => void;
  setConversationId: (id: string | null) => void;
  clearMessages: () => void;
  setProcessing: (processing: boolean) => void;
  setCurrentMessageId: (id: string | null) => void;
  resetOnError: (message?: string) => void;
  clearTimeout: () => void;
  cancelRequest: () => void;
  setStatusDetail: (detail: string) => void;
}

function newMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `msg_${crypto.randomUUID()}`;
  }
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  assistantMessage: null,
  input: "",
  conversationId: null,
  isProcessing: false,
  currentMessageId: null,
  requestTimeout: null,
  statusDetail: "",
  setInput: (input) => set({ input }),
  setProcessing: (processing) => set({ isProcessing: processing }),
  setCurrentMessageId: (id) => set({ currentMessageId: id }),
  setStatusDetail: (detail) => set({ statusDetail: detail }),
  sendMessage: (override, agentMode?: string) => {
    const text = (override ?? get().input).trim();
    if (!text) return;
    if (get().isProcessing) return;

    const messageId = newMessageId();
    const userMessage: ChatMessage = { id: messageId, role: "user", content: text };

    get().clearTimeout();
    get().addMessage(userMessage);

    const timeoutId = setTimeout(() => {
      const state = get();
      if (state.isProcessing && state.currentMessageId === messageId) {
        console.warn("[ChatStore] Request timeout for message:", messageId);
        state.resetOnError("Request timed out. Try again.");
      }
    }, 180000);

    set({
      currentMessageId: messageId,
      isProcessing: true,
      input: "",
      requestTimeout: timeoutId,
      statusDetail: "THINKING...",
      assistantMessage: { id: `assistant_${messageId}`, role: "assistant", content: "" },
    });

    useAIStore.getState().setCoreStatus("thinking");
    useAIStore.getState().setAIProviderStatus("thinking");
    useAIStore.getState().setChatStatus("processing");
    useAIStore.getState().setDashState("thinking");
    useActivityStore.getState().push("User command received", "chat");
    useActivityStore.getState().push("Thinking", "ai");

    const intent = detectIntent(text);
    if (intent.type === "research") {
      useAIStore.getState().setDashState("researching");
      useAIStore.getState().setCoreStatus("thinking");
      usePanelStore.getState().openPanel("research", "Research", {
        query: intent.query,
        status: "searching",
        action: "Starting web search",
        progress: 10,
      });
      useActivityStore.getState().push("Researching", "ai");
      void (async () => {
        try {
          usePanelStore.getState().openPanel("research", "Research", {
            query: intent.query,
            status: "searching",
            action: "Querying sources",
            progress: 40,
          });
          const data = await runResearch(intent.query);
          usePanelStore.getState().openPanel("research", "Research", {
            query: intent.query,
            status: data.ok ? "complete" : "error",
            action: data.ok ? "Analysis complete" : data.error || "Search failed",
            progress: 100,
            abstract: data.abstract,
            summary: data.summary,
            results: data.results,
          });
          useActivityStore.getState().push("Research results ready", "tool");
        } catch (err) {
          usePanelStore.getState().openPanel("research", "Research", {
            query: intent.query,
            status: "error",
            action: err instanceof Error ? err.message : "Research failed",
            progress: 100,
          });
        }
      })();
    } else if (intent.type === "system") {
      usePanelStore.getState().openPanel("system", "System Monitor");
      useActivityStore.getState().push("Opened system monitor", "system");
    } else if (intent.type === "files") {
      usePanelStore.getState().openPanel("files", "Files");
    } else if (intent.type === "coding") {
      useAIStore.getState().setDashState("coding");
      usePanelStore.getState().openPanel("coding", "Code");
    } else if (intent.type === "memory") {
      usePanelStore.getState().openPanel("memory", "Memory");
    }

    const wsClient = getWsClient();
    wsClient.sendChatMessage(messageId, text, get().conversationId || undefined, agentMode);
  },
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateAssistantMessage: (token) => {
    set((state) => {
      if (!state.assistantMessage) {
        return {
          assistantMessage: {
            id: `assistant_${state.currentMessageId || Date.now()}`,
            role: "assistant",
            content: token,
          },
        };
      }
      return {
        assistantMessage: {
          ...state.assistantMessage,
          content: state.assistantMessage.content + token,
        },
        statusDetail: "RESPONDING...",
      };
    });
  },
  commitAssistantMessage: () => {
    set((state) => {
      if (state.requestTimeout) clearTimeout(state.requestTimeout);
      // Clear active request from wsClient
      if (state.currentMessageId) {
        const wsClient = getWsClient();
        wsClient.clearActiveRequest(state.currentMessageId);
      }
      const nextMessages = state.assistantMessage
        ? [...state.messages, state.assistantMessage]
        : state.messages;
      return {
        messages: nextMessages,
        assistantMessage: null,
        isProcessing: false,
        currentMessageId: null,
        requestTimeout: null,
        statusDetail: "",
      };
    });
    // Ensure AI store resets properly
    useAIStore.getState().setCoreStatus("idle");
    useAIStore.getState().setAIProviderStatus("ready");
    useAIStore.getState().setChatStatus("idle");
    useAIStore.getState().setDashState("idle");
  },
  setConversationId: (id) => set({ conversationId: id }),
  clearMessages: () =>
    set({ messages: [], assistantMessage: null, isProcessing: false, currentMessageId: null, statusDetail: "" }),
  resetOnError: (message) => {
    const state = get();
    if (state.requestTimeout) clearTimeout(state.requestTimeout);
    // Clear active request from wsClient
    if (state.currentMessageId) {
      const wsClient = getWsClient();
      wsClient.clearActiveRequest(state.currentMessageId);
    }
    set({
      isProcessing: false,
      currentMessageId: null,
      assistantMessage: null,
      requestTimeout: null,
      statusDetail: message || "",
    });
    useAIStore.getState().setCoreStatus("idle");
    useAIStore.getState().setAIProviderStatus("ready");
    useAIStore.getState().setChatStatus("error");
    useAIStore.getState().setDashState("idle");
  },
  clearTimeout: () => {
    const state = get();
    if (state.requestTimeout) {
      clearTimeout(state.requestTimeout);
      set({ requestTimeout: null });
    }
  },
  cancelRequest: () => {
    const id = get().currentMessageId;
    if (id) getWsClient().clearActiveRequest(id);
    get().resetOnError("");
    useAIStore.getState().setChatStatus("idle");
    useAIStore.getState().setAIProviderStatus("ready");
  },
}));