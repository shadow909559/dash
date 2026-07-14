import { create } from 'zustand';
import { Conversation, ChatMessage, MessageStatus } from './types';
import { useAgentStore } from '../agent/agentStore';
import { apiGet, apiPost, apiDelete, apiPut } from '../../services/apiService';

function uid(prefix = 'id'): string {
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now()}`;
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

type ChatState = {
  conversations: Conversation[];
  activeConversationId: string | null;
  messagesByConversationId: Record<string, ChatMessage[]>;
  isTyping: boolean;
  connectionStatus: ConnectionStatus;
  lastError: string | null;
  isLoadingConversations: boolean;
  isLoadingMessages: boolean;

  createConversation: () => Promise<void>;
  setActiveConversationId: (id: string) => void;
  deleteConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;

  sendUserMessage: (params: {
    conversationId: string;
    content: string;
    attachments?: { name: string }[];
  }) => void;

  /**
   * Directly append a received assistant token to the streaming message,
   * or finalize the message on 'done'.
   */
  appendAssistantToken: (conversationId: string, token: string) => void;
  finalizeAssistantMessage: (conversationId: string) => void;
  setAssistantError: (conversationId: string, error: string) => void;

  /** Fetch conversations from backend */
  fetchConversations: () => Promise<void>;
  /** Fetch messages for a conversation */
  fetchMessages: (conversationId: string) => Promise<void>;

  /** Clear last error */
  clearError: () => void;
};

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  messagesByConversationId: {},
  isTyping: false,
  connectionStatus: 'disconnected',
  lastError: null,
  isLoadingConversations: false,
  isLoadingMessages: false,

  createConversation: async () => {
    const id = uid('conv');
    const conv: Conversation = {
      id,
      title: 'New conversation',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messageCount: 0,
    };

    set((state) => ({
      conversations: [conv, ...state.conversations],
      activeConversationId: id,
      messagesByConversationId: {
        ...state.messagesByConversationId,
        [id]: [],
      },
      connectionStatus: useAgentStore.getState().status === 'connected' ? 'connected' : 'disconnected',
    }));

    // Persist to backend
    const result = await apiPost<{ id: string }>('/conversations', {
      title: conv.title,
      id: conv.id,
    });

    if (result.ok && result.data.id !== id) {
      // Backend assigned a different ID — update local
      const backendId = result.data.id;
      set((state) => {
        const newConv = { ...conv, id: backendId };
        const newMsgs = { ...state.messagesByConversationId };
        newMsgs[backendId] = newMsgs[id] ?? [];
        delete newMsgs[id];
        return {
          conversations: state.conversations.map((c) => (c.id === id ? newConv : c)),
          activeConversationId: backendId,
          messagesByConversationId: newMsgs,
        };
      });
    }
  },

  setActiveConversationId: (id) => {
    set({ activeConversationId: id });
    // Load messages for this conversation
    const existing = get().messagesByConversationId[id];
    if (!existing || existing.length === 0) {
      get().fetchMessages(id);
    }
  },

  deleteConversation: async (id) => {
    // Optimistic removal
    const state = get();
    const newConversations = state.conversations.filter((c) => c.id !== id);
    const newActiveId = state.activeConversationId === id
      ? (newConversations[0]?.id ?? null)
      : state.activeConversationId;
    const newMsgs = { ...state.messagesByConversationId };
    delete newMsgs[id];

    set({
      conversations: newConversations,
      activeConversationId: newActiveId,
      messagesByConversationId: newMsgs,
    });

    // Delete from backend
    await apiDelete(`/conversations/${id}`);
  },

  renameConversation: async (id, title) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title } : c,
      ),
    }));

    await apiPut(`/conversations/${id}`, { title });
  },

  sendUserMessage: ({ conversationId, content, attachments }) => {
    const message: ChatMessage = {
      id: uid('msg'),
      role: 'user',
      content,
      createdAt: Date.now(),
      attachments,
      status: 'sending' as MessageStatus,
    };

    set((state) => {
      const prev = state.messagesByConversationId[conversationId] ?? [];
      const nextMessages = [...prev, message];

      // Set better title on first user message
      const conv = state.conversations.find((c) => c.id === conversationId);
      const shouldRename = conv && conv.title === 'New conversation' && nextMessages.filter((m) => m.role === 'user').length === 1;

      return {
        messagesByConversationId: {
          ...state.messagesByConversationId,
          [conversationId]: nextMessages,
        },
        conversations: shouldRename
          ? state.conversations.map((c) =>
              c.id === conversationId
                ? { ...c, title: content.trim().slice(0, 40) || 'Conversation' }
                : c,
            )
          : state.conversations,
        isTyping: true,
        lastError: null,
      };
    });

    // Send via WebSocket or REST
    const agentState = useAgentStore.getState();
    if (agentState.status === 'connected' && agentState._ws?.readyState === WebSocket.OPEN) {
      agentState.sendMessage({
        type: 'message',
        conversation_id: conversationId,
        content,
      });
    } else {
      // Fallback: REST API call queue — use /chat endpoint
      apiPost<{ reply: string }>('/chat', {
        conversation_id: conversationId,
        content,
        message_id: message.id,
      }).then((result) => {
        if (result.ok) {
          get().appendAssistantToken(conversationId, result.data.reply);
          get().finalizeAssistantMessage(conversationId);
        } else {
          get().setAssistantError(conversationId, result.error);
        }
      });
    }
  },

  appendAssistantToken: (conversationId, token) => {
    set((state) => {
      const prev = state.messagesByConversationId[conversationId] ?? [];
      const lastMsg = prev[prev.length - 1];

      if (lastMsg && lastMsg.role === 'assistant' && lastMsg.status === 'streaming') {
        // Append to existing streaming message
        const updated = {
          ...lastMsg,
          content: lastMsg.content + token,
          status: 'streaming' as MessageStatus,
        };
        const nextMessages = [...prev.slice(0, -1), updated];
        return {
          messagesByConversationId: {
            ...state.messagesByConversationId,
            [conversationId]: nextMessages,
          },
        };
      }

      // Mark user message as sent
      const markSent = prev.map((m) =>
        m.role === 'user' && m.status === 'sending'
          ? { ...m, status: 'sent' as MessageStatus }
          : m,
      );

      // Start new streaming assistant message
      const assistantMsg: ChatMessage = {
        id: uid('msg'),
        role: 'assistant',
        content: token,
        createdAt: Date.now(),
        status: 'streaming' as MessageStatus,
      };

      return {
        messagesByConversationId: {
          ...state.messagesByConversationId,
          [conversationId]: [...markSent, assistantMsg],
        },
        isTyping: true,
        lastError: null,
      };
    });
  },

  finalizeAssistantMessage: (conversationId) => {
    set((state) => {
      const prev = state.messagesByConversationId[conversationId] ?? [];
      const lastMsg = prev[prev.length - 1];

      if (!lastMsg || lastMsg.role !== 'assistant') {
        return { isTyping: false };
      }

      const updated = {
        ...lastMsg,
        status: 'complete' as MessageStatus,
      };
      const nextMessages = [...prev.slice(0, -1), updated];

      return {
        messagesByConversationId: {
          ...state.messagesByConversationId,
          [conversationId]: nextMessages,
        },
        isTyping: false,
      };
    });
  },

  setAssistantError: (conversationId, error) => {
    set((state) => {
      const prev = state.messagesByConversationId[conversationId] ?? [];
      const lastMsg = prev[prev.length - 1];

      if (lastMsg && lastMsg.role === 'assistant' && lastMsg.status === 'streaming') {
        const updated = {
          ...lastMsg,
          content: lastMsg.content + `\n\n*Error: ${error}*`,
          status: 'error' as MessageStatus,
        };
        const nextMessages = [...prev.slice(0, -1), updated];
        return {
          messagesByConversationId: {
            ...state.messagesByConversationId,
            [conversationId]: nextMessages,
          },
          isTyping: false,
          lastError: error,
        };
      }

      // Add error message
      const errorMsg: ChatMessage = {
        id: uid('msg'),
        role: 'assistant',
        content: `⚠️ **Error**: ${error}`,
        createdAt: Date.now(),
        status: 'error' as MessageStatus,
      };

      return {
        messagesByConversationId: {
          ...state.messagesByConversationId,
          [conversationId]: [...prev, errorMsg],
        },
        isTyping: false,
        lastError: error,
      };
    });
  },

  fetchConversations: async () => {
    set({ isLoadingConversations: true });
    const result = await apiGet<Conversation[]>('/conversations');
    if (result.ok) {
      set({
        conversations: result.data,
        isLoadingConversations: false,
        connectionStatus: 'connected',
      });
      // Auto-select first conversation if none active
      if (!get().activeConversationId && result.data.length > 0) {
        get().setActiveConversationId(result.data[0].id);
      }
    } else {
      set({
        isLoadingConversations: false,
        lastError: result.error,
        connectionStatus: 'error',
      });
    }
  },

  fetchMessages: async (conversationId) => {
    set({ isLoadingMessages: true });
    const result = await apiGet<ChatMessage[]>(`/conversations/${conversationId}/messages`);
    if (result.ok) {
      set((state) => ({
        messagesByConversationId: {
          ...state.messagesByConversationId,
          [conversationId]: result.data,
        },
        isLoadingMessages: false,
      }));
    } else {
      set({ isLoadingMessages: false, lastError: result.error });
    }
  },

  clearError: () => {
    set({ lastError: null });
  },
}));

// ── Subscribe to WebSocket agent messages to wire up chat tokens ──
let _wsListenerRegistered = false;

export function initChatWebSocketListener(): () => void {
  if (_wsListenerRegistered) {
    return () => {};
  }
  _wsListenerRegistered = true;

  const unsub = useAgentStore.getState().onMessage((data) => {
    const type = data.type as string | undefined;
    const conversationId = (data.conversation_id as string) ?? getActiveConversationId();

    if (!conversationId) return;

    switch (type) {
      case 'token':
      case 'text_chunk':
        const token = (data.content as string) ?? (data.text as string) ?? '';
        if (token) {
          useChatStore.getState().appendAssistantToken(conversationId, token);
        }
        break;
      case 'done':
      case 'stream_end':
        useChatStore.getState().finalizeAssistantMessage(conversationId);
        break;
      case 'error':
        const errMsg = (data.message as string) ?? (data.error as string) ?? 'Unknown error';
        useChatStore.getState().setAssistantError(conversationId, errMsg);
        break;
      case 'echo':
        // Backend echo response — treat as final assistant reply
        const echoContent = data.received
          ? (data.received as Record<string, unknown>)?.content ?? JSON.stringify(data.received)
          : null;
        if (echoContent && typeof echoContent === 'string') {
          useChatStore.getState().appendAssistantToken(conversationId, echoContent);
          useChatStore.getState().finalizeAssistantMessage(conversationId);
        }
        break;
    }
  });

  return () => {
    _wsListenerRegistered = false;
    unsub();
  };
}

function getActiveConversationId(): string | null {
  return useChatStore.getState().activeConversationId;
}