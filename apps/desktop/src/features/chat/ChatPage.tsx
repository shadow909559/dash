import { useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { MessageBubble } from './components/MessageBubble';
import { ChatComposer } from './components/ChatComposer';
import { TypingIndicator } from './components/TypingIndicator';
import { useChatStore, initChatWebSocketListener } from './chatStore';
import { useAgentStore } from '../agent/agentStore';
import { AgentStatus } from '../agent/agentTypes';
import { useVoiceStore } from './voiceStore';
import './chat.css';

export function ChatPage() {
  const navigate = useNavigate();

  const { conversations, activeConversationId, messagesByConversationId, isTyping, createConversation, setActiveConversationId, sendUserMessage } =
    useChatStore();

  const { status, connect } = useAgentStore();

  const { voiceState } = useVoiceStore();

  const activeMessages = useMemo(() => {
    if (!activeConversationId) return [];
    return messagesByConversationId[activeConversationId] ?? [];
  }, [activeConversationId, messagesByConversationId]);

  const scrollerRef = useRef<HTMLDivElement | null>(null);

  // Auto-create first conversation
  useEffect(() => {
    if (conversations.length === 0) {
      createConversation();
    }
  }, [conversations.length, createConversation]);

  // Auto-connect to backend on mount
  useEffect(() => {
    if (status === AgentStatus.disconnected) {
      connect();
    }
  }, [status, connect]);

  // Initialize WebSocket listener for chat tokens
  useEffect(() => {
    const unsub = initChatWebSocketListener();
    return () => {
      unsub();
    };
  }, []);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;

    // Auto-scroll to bottom when messages/typing changes.
    el.scrollTop = el.scrollHeight;
  }, [activeMessages.length, isTyping, activeConversationId]);

  const handleSend = (params: { content: string; attachments?: { name: string }[] }) => {
    if (!activeConversationId) {
      // should not happen (we create convo on mount)
      createConversation();
      const nextId = useChatStore.getState().activeConversationId;
      if (!nextId) return;
      return sendUserMessage({ conversationId: nextId, ...params });
    }

    sendUserMessage({ conversationId: activeConversationId, ...params });
  };

  return (
    <div className="chat">
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onNewConversation={createConversation}
        onSelectConversation={setActiveConversationId}
      />

      <section className="chat__main">
        <div className="chat__topBar">
          <div className="chat__topTitle">Chat</div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {voiceState !== 'idle' ? (
              <div
                className={`chat__voiceIndicator chat__voiceIndicator--${voiceState}`}
                role="status"
                aria-live="polite"
              >
                {voiceState === 'listening' ? '🎙️ Listening…' : '🗣️ Speaking…'}
              </div>
            ) : null}
            <button className="chat__settingsButton" type="button" onClick={() => navigate('/settings')}>
              Settings
            </button>
            <button className="chat__settingsButton" type="button" onClick={() => navigate('/chat')}>
              Refresh
            </button>
          </div>
        </div>


        <div className="chat__messages" ref={scrollerRef}>
          {activeMessages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          {isTyping ? <TypingIndicator /> : null}
        </div>

        <ChatComposer disabled={isTyping || !activeConversationId} onSend={handleSend} />
      </section>
    </div>
  );
}

