"""Write the new chatStore.ts with per-mode message isolation."""
import os

content = r'''import { create } from "zustand";
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
  modeMessages: Record<string, ChatMessage[]>;
  activeMode: string;
  assistantMessage: ChatMessage | null;
  input: string;
  conversationId: string | null;
  isProcessing: boolean;
  currentMessageId: string | null;
  requestTimeout: ReturnType<typeof setTimeout> | null;
  statusDetail: string;
  setInput: (input: string) => void;
  setActiveMode: (mode: string) => void;
  sendMessage: (override?: string, agentMode?: string) => void;
  addMessage: (message: ChatMessage) => void;
  updateAssistantMessage: (token: string) => void;
  commitAssistantMessage: () => void;
  setConversationId: (id: string | null) => void;
  clearMessages: (mode?: string) => void;
  setProcessing: (processing: boolean) => void;
  setCurrentMessageId: (id: string | null) => void;
  resetOnError: (message?: string) => void;
  clearTimeout: () => void;
  cancelRequest: () => void;
  setStatusDetail: (detail: string) => void;
  getActiveMessages: () => ChatMessage[];
}

function newMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `msg_${crypto.randomUUID()}`;
  }
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export const useChatStore = create<ChatState>((set, get) => ({
  modeMessages: { general: [], coder: [], planner: [], research: [], executor: [] },
  activeMode: "general",
  assistantMessage: null,
  input: "",
  conversationId: null,
  isProcessing: false,
  currentMessageId: null,
  requestTimeout: null,
  statusDetail: "",

  setInput: (input) => set({ input }),
  setActiveMode: (mode) => set({ activeMode: mode }),
  getActiveMessages: () => {
    const s = get();
    return s.modeMessages[s.activeMode] || [];
  },

  sendMessage: (override, agentMode?: string) => {
    const state = get();
    const mode = agentMode || state.activeMode;
    const text = (override ?? state.input).trim();
    if (!text || state.isProcessing) return;

    const messageId = newMessageId();
    const userMessage: ChatMessage = { id: messageId, role: "user", content: text };

    get().clearTimeout();
    get().addMessage(userMessage);

    const timeoutId = setTimeout(() => {
      const s2 = get();
      if (s2.isProcessing && s2.currentMessageId === messageId) {
        s2.resetOnError("Request timed out. Try again.");
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
      usePanelStore.getState().openPanel("research", "Research", {
        query: intent.query, status: "searching", action: "Starting web search", progress: 10,
      });
      void (async () => {
        try {
          const data = await runResearch(intent.query);
          usePanelStore.getState().openPanel("research", "Research", {
            query: intent.query,
            status: data.ok ? "complete" : "error",
            action: data.ok ? "Analysis complete" : data.error || "Search failed",
            progress: 100, abstract: data.abstract, summary: data.summary, results: data.results,
          });
        } catch (err) {
          usePanelStore.getState().openPanel("research", "Research", {
            query: intent.query, status: "error",
            action: err instanceof Error ? err.message : "Research failed", progress: 100,
          });
        }
      })();
    } else if (intent.type === "system") {
      usePanelStore.getState().openPanel("system", "System Monitor");
    } else if (intent.type === "files") {
      usePanelStore.getState().openPanel("files", "Files");
    } else if (intent.type === "coding") {
      useAIStore.getState().setDashState("coding");
      usePanelStore.getState().openPanel("coding", "Code");
    } else if (intent.type === "memory") {
      usePanelStore.getState().openPanel("memory", "Memory");
    }

    const wsClient = getWsClient();
    wsClient.sendChatMessage(messageId, text, get().conversationId || undefined, mode);
  },

  addMessage: (message) =>
    set((state) => {
      const mode = state.activeMode;
      const current = state.modeMessages[mode] || [];
      return { modeMessages: { ...state.modeMessages, [mode]: [...current, message] } };
    }),

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
        assistantMessage: { ...state.assistantMessage, content: state.assistantMessage.content + token },
        statusDetail: "RESPONDING...",
      };
    });
  },

  commitAssistantMessage: () => {
    set((state) => {
      if (state.requestTimeout) clearTimeout(state.requestTimeout);
      if (state.currentMessageId) getWsClient().clearActiveRequest(state.currentMessageId);
      const mode = state.activeMode;
      const current = state.modeMessages[mode] || [];
      const nextMessages = state.assistantMessage ? [...current, state.assistantMessage] : current;
      return {
        modeMessages: { ...state.modeMessages, [mode]: nextMessages },
        assistantMessage: null,
        isProcessing: false,
        currentMessageId: null,
        requestTimeout: null,
        statusDetail: "",
      };
    });
    useAIStore.getState().setCoreStatus("idle");
    useAIStore.getState().setAIProviderStatus("ready");
    useAIStore.getState().setChatStatus("idle");
    useAIStore.getState().setDashState("idle");
  },

  setConversationId: (id) => set({ conversationId: id }),

  clearMessages: (mode?: string) =>
    set((state) => {
      const targetMode = mode || state.activeMode;
      return {
        modeMessages: { ...state.modeMessages, [targetMode]: [] },
        assistantMessage: null,
        isProcessing: false,
        currentMessageId: null,
        statusDetail: "",
      };
    }),

  setProcessing: (processing) => set({ isProcessing: processing }),
  setCurrentMessageId: (id) => set({ currentMessageId: id }),
  setStatusDetail: (detail) => set({ statusDetail: detail }),

  resetOnError: (message) => {
    const state = get();
    if (state.requestTimeout) clearTimeout(state.requestTimeout);
    if (state.currentMessageId) getWsClient().clearActiveRequest(state.currentMessageId);
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
'''

target = "apps/desktop/src/stores/chatStore.ts"
with open(target, "w", newline="\n") as f:
    f.write(content)
print(f"Written {len(content.splitlines())} lines to {target}")
