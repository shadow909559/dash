import { useEffect, useState, useRef, FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { chat as chatApi } from "@/lib/api";
import { getWsClient, WsClient } from "@/lib/wsClient";

interface Message {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  last_message_at: string | null;
}

export default function Chat() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversation, setActiveConversation] = useState<{
    id: string;
    title: string;
    messages: Message[];
  } | null>(null);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WsClient | null>(null);
  const messageBufferRef = useRef<Map<string, string>>(new Map());
  const skipNextLoadRef = useRef(false);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation?.messages, streamingMessageId]);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (id) {
      if (skipNextLoadRef.current) {
        skipNextLoadRef.current = false;
        return;
      }
      loadConversation(id);
    }
  }, [id]);

  useEffect(() => {
    const client = getWsClient();
    wsRef.current = client;
    connectWs(client);
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, []);

  async function connectWs(client: WsClient) {
    setWsStatus("connecting");
    try {
      await client.connect();
      setWsStatus("connected");

      client.setChatCallbacks({
        onToken: (messageId, token) => {
          setStreamingMessageId((prev) => prev || messageId);
          const existing = messageBufferRef.current.get(messageId) || "";
          messageBufferRef.current.set(messageId, existing + token);

          const currentContent = messageBufferRef.current.get(messageId) || "";
          setActiveConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const streamIdx = messages.findIndex((m) => m.id === messageId);
            if (streamIdx >= 0) {
              messages[streamIdx] = { ...messages[streamIdx], content: currentContent };
            }
            return { ...prev, messages };
          });
        },
        onDone: (messageId, conversationId) => {
          const finalContent = messageBufferRef.current.get(messageId) || "";
          messageBufferRef.current.delete(messageId);
          setStreamingMessageId(null);
          setIsLoading(false);

          setActiveConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const streamIdx = messages.findIndex((m) => m.id === messageId);
            if (streamIdx >= 0) {
              messages[streamIdx] = { ...messages[streamIdx], content: finalContent };
            }
            const newId = conversationId || prev.id;
            return { ...prev, id: newId, messages };
          });

          loadConversations();

          if (conversationId) {
            const pathParts = window.location.pathname.split("/chat/");
            const currentId = pathParts[1];
            if (!currentId || currentId !== conversationId) {
              skipNextLoadRef.current = true;
              window.history.replaceState(null, "", `/chat/${conversationId}`);
            }
          }
        },
        onError: (messageId, error) => {
          console.error("Chat error:", error);
          messageBufferRef.current.delete(messageId || "");
          setStreamingMessageId(null);
          setIsLoading(false);

          if (messageId) {
            setActiveConversation((prev) => {
              if (!prev) return prev;
              const messages = prev.messages.map((m) =>
                m.id === messageId
                  ? { ...m, content: `${m.content}\n\n*Error: ${error}*` }
                  : m
              );
              return { ...prev, messages };
            });
          }
        },
      });
    } catch (err) {
      console.error("WebSocket connection failed:", err);
      setWsStatus("disconnected");
      reconnectTimerRef.current = setTimeout(() => connectWs(client), 5000);
    }
  }

  async function loadConversations() {
    try {
      const result = await chatApi.getConversations();
      setConversations(result.items);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    }
  }

  async function loadConversation(conversationId: string) {
    try {
      const conv = await chatApi.getConversation(conversationId);
      const messagesResult = await chatApi.getMessages(conversationId);
      setActiveConversation({
        id: conversationId,
        title: conv.title || "New Chat",
        messages: messagesResult.items,
      });
    } catch (err) {
      console.error("Failed to load conversation:", err);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const messageContent = input.trim();
    setInput("");

    const client = wsRef.current;
    if (!client || !client.isConnected()) {
      try {
        await client?.connect();
      } catch {
        console.error("WebSocket not connected");
        return;
      }
    }

    setIsLoading(true);

    const tempMessageId = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const userMsg: Message = {
      id: `user-${tempMessageId}`,
      role: "user",
      content: messageContent,
      created_at: new Date().toISOString(),
    };

    const currentConvId = activeConversation?.id || null;

    const assistantMsg: Message = {
      id: tempMessageId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };

    setActiveConversation((prev) => {
      const newMessages = prev
        ? [...prev.messages, userMsg, assistantMsg]
        : [userMsg, assistantMsg];
      const title = prev?.title || messageContent.slice(0, 50);
      return {
        id: prev?.id || tempMessageId,
        title,
        messages: newMessages,
      };
    });

    setStreamingMessageId(tempMessageId);
    messageBufferRef.current.set(tempMessageId, "");

    const sent = client!.sendChat(currentConvId, tempMessageId, messageContent);
    if (!sent) {
      console.error("Failed to send message via WebSocket");
      setIsLoading(false);
      setStreamingMessageId(null);
    }
  }

  return (
    <div style={{ display: "flex", height: "100%", gap: 16 }}>
      {/* Sidebar */}
      <div
        className="glass"
        style={{
          width: 260,
          flexShrink: 0,
          borderRadius: "var(--radius-md)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "12px 16px",
            borderBottom: "1px solid var(--border-glass)",
            fontSize: 13,
            fontWeight: 600,
            color: "var(--text-secondary)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>Conversations</span>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background:
                wsStatus === "connected"
                  ? "var(--success)"
                  : wsStatus === "connecting"
                    ? "var(--warning)"
                    : "var(--danger)",
              display: "inline-block",
            }}
            title={`WebSocket: ${wsStatus}`}
          />
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
          {conversations.length === 0 && (
            <div
              style={{
                padding: 16,
                textAlign: "center",
                color: "var(--text-muted)",
                fontSize: 13,
              }}
            >
              No conversations yet
            </div>
          )}
          {conversations.map((conv) => (
            <button
              key={conv.id}
              className="btn-ghost"
              onClick={() => navigate(`/chat/${conv.id}`)}
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: 13,
                textAlign: "left",
                borderRadius: "var(--radius-sm)",
                background:
                  activeConversation?.id === conv.id
                    ? "var(--bg-glass-hover)"
                    : "transparent",
                color: "var(--text-primary)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                marginBottom: 2,
              }}
            >
              {conv.title || "New conversation"}
            </button>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div
        className="glass"
        style={{
          flex: 1,
          borderRadius: "var(--radius-md)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
          {!activeConversation && (
            <div
              style={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-muted)",
                gap: 8,
              }}
            >
              <span style={{ fontSize: 40 }}>💬</span>
              <p style={{ fontSize: 14 }}>
                Type a message to start a new conversation
              </p>
            </div>
          )}

          {activeConversation?.messages.map((msg) => (
            <div
              key={msg.id}
              className="animate-fade-in"
              style={{
                display: "flex",
                justifyContent:
                  msg.role === "user" ? "flex-end" : "flex-start",
                marginBottom: 12,
              }}
            >
              <div
                className="glass"
                style={{
                  maxWidth: "70%",
                  padding: "10px 14px",
                  borderRadius:
                    msg.role === "user"
                      ? "16px 16px 4px 16px"
                      : "16px 16px 16px 4px",
                  background:
                    msg.role === "user"
                      ? "rgba(108, 92, 231, 0.15)"
                      : "var(--bg-glass)",
                  border:
                    msg.role === "user"
                      ? "1px solid rgba(108, 92, 231, 0.2)"
                      : "1px solid var(--border-glass)",
                }}
              >
                <p
                  style={{
                    fontSize: 14,
                    lineHeight: 1.5,
                    color: "var(--text-primary)",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {msg.content}
                  {msg.id === streamingMessageId && (
                    <span
                      className="streaming-cursor"
                      style={{ animation: "pulse 1s infinite" }}
                    >
                      ▌
                    </span>
                  )}
                </p>
                {msg.created_at &&
                  msg.content &&
                  msg.id !== streamingMessageId && (
                    <p
                      style={{
                        fontSize: 11,
                        color: "var(--text-muted)",
                        marginTop: 4,
                        textAlign: "right",
                      }}
                    >
                      {new Date(msg.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  )}
              </div>
            </div>
          ))}
          {isLoading && !streamingMessageId && (
            <div
              style={{
                display: "flex",
                justifyContent: "flex-start",
                marginBottom: 12,
              }}
            >
              <div
                className="glass"
                style={{
                  padding: "10px 14px",
                  borderRadius: "16px 16px 16px 4px",
                }}
              >
                <div style={{ display: "flex", gap: 4 }}>
                  <div
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: "var(--text-muted)",
                      animation: "pulse 1.2s ease infinite",
                    }}
                  />
                  <div
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: "var(--text-muted)",
                      animation: "pulse 1.2s ease infinite 0.2s",
                    }}
                  />
                  <div
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: "var(--text-muted)",
                      animation: "pulse 1.2s ease infinite 0.4s",
                    }}
                  />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form
          onSubmit={handleSubmit}
          style={{
            padding: "12px 16px",
            borderTop: "1px solid var(--border-glass)",
            display: "flex",
            gap: 8,
          }}
        >
          <input
            className="input"
            type="text"
            placeholder={
              wsStatus === "connected"
                ? "Type a message..."
                : "Connecting to server..."
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading || wsStatus !== "connected"}
            style={{ flex: 1 }}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={
              isLoading || !input.trim() || wsStatus !== "connected"
            }
          >
            {isLoading ? "Sending..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
