import React, { useState, useRef, useEffect } from "react";
import { AgentPanel } from "@/components/AgentPanel";
import { useChatStore } from "@/stores/chatStore";
import { useAIStore } from "@/stores/aiStore";
import {
  Send,
  Mic,
  MicOff,
  Trash2,
  Bot,
  User,
  Sparkles,
  Loader2,
  MessageSquare,
  Copy,
  Check,
} from "lucide-react";

export const ChatPage: React.FC = () => {
  const {
    messages,
    assistantMessage,
    isProcessing,
    statusDetail,
    sendMessage,
    clearMessages,
    cancelRequest,
  } = useChatStore();
  const { dashState, websocketStatus } = useAIStore();
  const [inputText, setInputText] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<string | undefined>();
  const [showAgentPanel, setShowAgentPanel] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, assistantMessage]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onresult = (event: any) => {
        const transcript = event.results[0]?.[0]?.transcript;
        if (transcript) {
          setInputText(transcript);
          sendMessage(transcript);
        }
        setIsListening(false);
      };

      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);
      recognitionRef.current = recognition;
    }
  }, [sendMessage]);

  const handleSend = () => {
    if (!inputText.trim() || isProcessing) return;
    sendMessage(inputText.trim());
    setInputText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleMic = () => {
    if (!recognitionRef.current) return;
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.warn("Could not start recognition", err);
      }
    }
  };

  const copyMessage = (content: string, id: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const wsDisconnected = websocketStatus !== "connected";

  const getStateStatus = (): "online" | "offline" | "warning" | "processing" => {
    if (wsDisconnected) return "offline";
    if (isProcessing) return "processing";
    return "online";
  };

  const getStateLabel = () => {
    if (wsDisconnected) return "Disconnected";
    if (isProcessing) return statusDetail || "Processing";
    return "Ready";
  };

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Agent Panel Sidebar */}
      {showAgentPanel && (
        <AgentPanel
          selectedAgentId={selectedAgentId}
          onSelectAgent={setSelectedAgentId}
        />
      )}

      {/* Main Chat Area */}
      <div
        style={{
          display: "grid",
          gridTemplateRows: "auto minmax(0, 1fr) auto",
          flex: 1,
          height: "100%",
          minHeight: 0,
          backgroundColor: "var(--dash-bg)",
          overflow: "hidden",
          position: "relative",
        }}
      >
      {/* HUD grid overlay */}
      <div
        className="dash-hud-grid"
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.2,
          pointerEvents: "none",
          zIndex: 0,
        }}
      />

      {/* Top Chat Header */}
      <div
        className="dash-luminous"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 24px",
          borderBottom: "1px solid var(--dash-border)",
          backgroundColor: "var(--dash-surface)",
          zIndex: 10,
          position: "relative",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: "var(--dash-radius-sm)",
              background: isProcessing
                ? "var(--dash-accent)"
                : "var(--ultron-surface)",
              border: "1px solid var(--ultron-border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: isProcessing
                ? "0 0 20px var(--dash-accent-glow)"
                : undefined,
              transition: "all 0.3s",
            }}
          >
            <Bot
              size={17}
              color={isProcessing ? "#fff" : "var(--ultron-text)"}
            />
          </div>
          <div>
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: "var(--dash-text)",
                letterSpacing: "-0.01em",
              }}
            >
              DASH Assistant
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 10,
                fontFamily: "'JetBrains Mono', monospace",
                color:
                  getStateStatus() === "online"
                    ? "var(--dash-success)"
                    : getStateStatus() === "processing"
                      ? "var(--ultron-core-bright)"
                      : "var(--dash-danger)",
              }}
            >
              <span
                className={
                  getStateStatus() === "online" ||
                  getStateStatus() === "processing"
                    ? "animate-status-pulse"
                    : undefined
                }
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background:
                    getStateStatus() === "online"
                      ? "var(--dash-success)"
                      : getStateStatus() === "processing"
                        ? "var(--ultron-core-bright)"
                        : "var(--dash-danger)",
                }}
              />
              {getStateLabel()}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {isProcessing && (
            <button
              onClick={cancelRequest}
              title="Cancel request"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                padding: "6px 12px",
                background: "rgba(220, 38, 38, 0.1)",
                border: "1px solid rgba(220, 38, 38, 0.25)",
                borderRadius: "var(--dash-radius-sm)",
                color: "var(--dash-danger)",
                fontSize: 11,
                cursor: "pointer",
                fontWeight: 500,
                transition: "all var(--dash-transition-fast)",
              }}
            >
              <Trash2 size={12} /> Cancel
            </button>
          )}
          <button
            onClick={clearMessages}
            title="Clear Conversation"
            className="dash-btn-ghost"
          >
            <Trash2 size={12} /> Clear
          </button>
        </div>
      </div>

      {/* Center: Scrollable Message List */}
      <div
        style={{
          overflowY: "auto",
          minHeight: 0,
          padding: "20px 24px",
          display: "flex",
          flexDirection: "column",
          gap: 14,
          position: "relative",
          zIndex: 1,
        }}
      >
        {/* Empty state */}
        {messages.length === 0 && !assistantMessage && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              flex: 1,
              gap: 14,
              textAlign: "center",
              margin: "auto 0",
            }}
          >
            <div
              style={{
                width: 60,
                height: 60,
                borderRadius: "var(--dash-radius-lg)",
                background:
                  "linear-gradient(135deg, var(--ultron-surface), var(--dash-surface))",
                border: "1px solid var(--ultron-border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 30px var(--ultron-glow), 0 0 60px var(--ultron-glow-intense)",
              }}
            >
              <Sparkles size={28} color="var(--ultron-core-bright)" />
            </div>
            <div
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--dash-text)",
                letterSpacing: "-0.01em",
              }}
            >
              How can DASH help you today?
            </div>
            <div
              style={{
                fontSize: 13,
                maxWidth: 440,
                lineHeight: 1.6,
                color: "var(--dash-text-secondary)",
              }}
            >
              Ask a question, request code generation, run system checks, manage
              files, or control your desktop remotely.
            </div>
            <div
              style={{
                display: "flex",
                gap: 8,
                marginTop: 8,
                flexWrap: "wrap",
                justifyContent: "center",
              }}
            >
              {[
                "What's my system status?",
                "List open windows",
                "Search memory for projects",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => {
                    setInputText(suggestion);
                    sendMessage(suggestion);
                  }}
                  className="dash-btn-ghost"
                  style={{
                    padding: "7px 14px",
                    borderRadius: "var(--dash-radius-full)",
                    fontSize: 11,
                    background: "var(--dash-surface)",
                  }}
                >
                  <MessageSquare size={10} style={{ opacity: 0.6 }} />
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((message) => {
          const isUser = message.role === "user";
          return (
            <div
              key={message.id}
              className="animate-slide-up"
              style={{
                display: "flex",
                gap: 10,
                maxWidth: "85%",
                alignSelf: isUser ? "flex-end" : "flex-start",
                flexDirection: isUser ? "row-reverse" : "row",
              }}
            >
              {/* Avatar */}
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "var(--dash-radius-sm)",
                  backgroundColor: isUser
                    ? "var(--dash-accent)"
                    : "var(--ultron-surface)",
                  border: `1px solid ${isUser ? "transparent" : "var(--ultron-border)"}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  marginTop: 2,
                }}
              >
                {isUser ? (
                  <User size={14} color="#ffffff" />
                ) : (
                  <Bot size={14} color="var(--ultron-core-bright)" />
                )}
              </div>

              {/* Message Bubble */}
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: isUser
                    ? "var(--dash-radius-md) var(--dash-radius-md) 4px var(--dash-radius-md)"
                    : "var(--dash-radius-md) var(--dash-radius-md) var(--dash-radius-md) 4px",
                  backgroundColor: isUser
                    ? "var(--dash-accent)"
                    : "var(--dash-surface)",
                  color: isUser ? "#ffffff" : "var(--dash-text)",
                  border: isUser ? "none" : "1px solid var(--ultron-border)",
                  fontSize: 13.5,
                  lineHeight: 1.55,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  boxShadow: isUser
                    ? "0 2px 16px var(--dash-accent-glow)"
                    : "var(--dash-shadow-sm)",
                  position: "relative",
                }}
              >
                {message.content}
                {!isUser && (
                  <button
                    onClick={() => copyMessage(message.content, message.id)}
                    style={{
                      position: "absolute",
                      top: 6,
                      right: 6,
                      background: "transparent",
                      border: "none",
                      color: "var(--dash-text-muted)",
                      cursor: "pointer",
                      padding: 2,
                      borderRadius: 3,
                      opacity: 0.4,
                      transition: "all var(--dash-transition-fast)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.opacity = "1";
                      e.currentTarget.style.color = "var(--dash-accent)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.opacity = "0.4";
                      e.currentTarget.style.color = "var(--dash-text-muted)";
                    }}
                  >
                    {copiedId === message.id ? (
                      <Check size={12} />
                    ) : (
                      <Copy size={12} />
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}

        {/* Streaming Assistant Message */}
        {assistantMessage && (
          <div
            className="animate-slide-up"
            style={{
              display: "flex",
              gap: 10,
              maxWidth: "85%",
              alignSelf: "flex-start",
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "var(--dash-radius-sm)",
                background: "var(--ultron-surface)",
                border: "1px solid var(--ultron-border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                marginTop: 2,
                boxShadow: "0 0 16px var(--ultron-glow)",
              }}
            >
              <Bot size={14} color="var(--ultron-core-bright)" />
            </div>

            <div
              style={{
                padding: "12px 16px",
                borderRadius:
                  "var(--dash-radius-md) var(--dash-radius-md) var(--dash-radius-md) 4px",
                backgroundColor: "var(--dash-surface)",
                color: "var(--dash-text)",
                border: "1px solid var(--ultron-border)",
                fontSize: 13.5,
                lineHeight: 1.55,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                boxShadow: "0 0 24px var(--ultron-glow)",
                position: "relative",
              }}
            >
              {assistantMessage.content || (
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <Loader2
                    size={14}
                    className="animate-rotate"
                    style={{ color: "var(--dash-accent)" }}
                  />
                  <span
                    style={{
                      display: "flex",
                      gap: 4,
                      alignItems: "center",
                    }}
                  >
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </span>
                </span>
              )}
              {assistantMessage.content && (
                <button
                  onClick={() =>
                    copyMessage(
                      assistantMessage!.content,
                      assistantMessage!.id
                    )
                  }
                  style={{
                    position: "absolute",
                    top: 6,
                    right: 6,
                    background: "transparent",
                    border: "none",
                    color: "var(--dash-text-muted)",
                    cursor: "pointer",
                    padding: 2,
                    borderRadius: 3,
                    opacity: 0.4,
                    transition: "all var(--dash-transition-fast)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.opacity = "1";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.opacity = "0.4";
                  }}
                >
                  <Copy size={12} />
                </button>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Fixed Composer */}
      <div
        style={{
          flexShrink: 0,
          padding: "14px 24px 18px 24px",
          backgroundColor: "var(--dash-surface)",
          borderTop: "1px solid var(--dash-border)",
          display: "flex",
          flexDirection: "column",
          gap: 6,
          position: "relative",
          zIndex: 10,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            backgroundColor: "var(--dash-bg)",
            border: `1px solid ${isListening ? "var(--ultron-core)" : "var(--dash-border)"}`,
            borderRadius: "var(--dash-radius-md)",
            padding: "6px 8px 6px 16px",
            transition:
              "border-color var(--dash-transition-fast), box-shadow var(--dash-transition-fast)",
            boxShadow: isListening
              ? "0 0 16px var(--ultron-glow)"
              : undefined,
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isListening
                ? "Listening..."
                : wsDisconnected
                  ? "Disconnected from backend..."
                  : "Message DASH... (Enter to send)"
            }
            aria-label="Message DASH"
            disabled={isProcessing}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              /* a11y: removed outline:none — global :focus-visible handles focus */
              color: "var(--dash-text)",
              fontSize: 13.5,
            }}
          />

          <button
            onClick={toggleMic}
            title={isListening ? "Stop listening" : "Voice input"}
            style={{
              width: 34,
              height: 34,
              borderRadius: "var(--dash-radius-sm)",
              background: isListening
                ? "var(--ultron-surface)"
                : "transparent",
              border: isListening
                ? "1px solid var(--ultron-border)"
                : "none",
              color: isListening
                ? "var(--ultron-core-bright)"
                : "var(--dash-text-secondary)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all var(--dash-transition-fast)",
            }}
            onMouseEnter={(e) => {
              if (!isListening)
                e.currentTarget.style.backgroundColor =
                  "rgba(255, 255, 255, 0.06)";
            }}
            onMouseLeave={(e) => {
              if (!isListening)
                e.currentTarget.style.backgroundColor = "transparent";
            }}
          >
            {isListening ? <MicOff size={16} /> : <Mic size={16} />}
          </button>

          <button
            onClick={handleSend}
            disabled={!inputText.trim() || isProcessing}
            title="Send message"
            style={{
              width: 34,
              height: 34,
              borderRadius: "var(--dash-radius-sm)",
              backgroundColor:
                inputText.trim() && !isProcessing
                  ? "var(--dash-accent)"
                  : "rgba(255, 255, 255, 0.05)",
              border: "none",
              color:
                inputText.trim() && !isProcessing
                  ? "#ffffff"
                  : "var(--dash-text-muted)",
              cursor:
                inputText.trim() && !isProcessing ? "pointer" : "default",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all var(--dash-transition-fast)",
              boxShadow:
                inputText.trim() && !isProcessing
                  ? "0 0 12px var(--dash-accent-glow)"
                  : "none",
            }}
          >
            {isProcessing ? (
              <Loader2 size={15} className="animate-rotate" />
            ) : (
              <Send size={15} />
            )}
          </button>
        </div>
      </div>


      {/* Agent Panel Toggle (floating button) */}
      {!showAgentPanel && (
        <button
          onClick={() => setShowAgentPanel(true)}
          style={{
            position: "absolute",
            left: 8,
            top: 60,
            background: "rgba(139, 92, 246, 0.15)",
            border: "1px solid rgba(139, 92, 246, 0.3)",
            borderRadius: 8,
            padding: "8px 10px",
            color: "var(--dash-accent)",
            cursor: "pointer",
            zIndex: 10,
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            fontWeight: 500,
          }}
        >
          <Bot size={14} />
          Agents
        </button>
      )}

      </div>
    </div>
  );
};

export default ChatPage;
