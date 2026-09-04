/**
 * ChatPage — JARVIS-style multi-agent chat interface.
 *
 * Features:
 * - 5 agent modes with distinct tabs, colors, and AI models
 * - General: Gemini/Grok for general conversation
 * - Coder: Qwen 2.5 Coder for code generation
 * - Planner: Ollama for task decomposition
 * - Research: Gemini for web research
 * - Executor: Fast-path for direct tool execution
 * - Clean message bubbles with agent-specific theming
 */
import React, { useState, useRef, useEffect, useCallback } from "react";
import { useChatStore } from "@/stores/chatStore";
import { useAIStore } from "@/stores/aiStore";
import { useModelStore } from "@/stores/modelStore";
import { ModelSelector } from "@/components/ModelSelector";
import {
  Send,
  Mic,
  MicOff,
  Bot,
  User,
  Sparkles,
  Copy,
  Check,
  RefreshCw,
  Paperclip,
  StopCircle,
  MoreHorizontal,
  Trash2,
  Code2,
  CalendarDays,
  Compass,
  Zap,
  MessageSquare,
} from "lucide-react";

/* ── Agent Mode Definitions ────────────────────────────────── */
interface AgentMode {
  id: string;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>;
  color: string;
  glowColor: string;
  modelHint: string;
  systemPrompt: string;
  placeholder: string;
}

const AGENT_MODES: AgentMode[] = [
  {
    id: "general",
    label: "General",
    icon: MessageSquare,
    color: "#3fa9f5",
    glowColor: "rgba(63, 169, 245, 0.25)",
    modelHint: "Gemini / Grok",
    systemPrompt: "You are DASH, a JARVIS-like AI assistant. Be concise, helpful, and slightly formal. Use technical language when appropriate.",
    placeholder: "Ask DASH anything...",
  },
  {
    id: "coder",
    label: "Coder",
    icon: Code2,
    color: "#22c55e",
    glowColor: "rgba(34, 197, 94, 0.25)",
    modelHint: "Qwen 2.5 Coder",
    systemPrompt: "You are DASH Coder. Write clean, efficient code. Explain briefly. Prefer Python, TypeScript, Bash. Include error handling.",
    placeholder: "Describe what to code...",
  },
  {
    id: "planner",
    label: "Planner",
    icon: CalendarDays,
    color: "#eab308",
    glowColor: "rgba(234, 179, 8, 0.25)",
    modelHint: "Ollama Local",
    systemPrompt: "You are DASH Planner. Break complex goals into clear, actionable steps. Prioritize by dependency and urgency.",
    placeholder: "What do you want to accomplish?",
  },
  {
    id: "research",
    label: "Research",
    icon: Compass,
    color: "#a855f7",
    glowColor: "rgba(168, 85, 247, 0.25)",
    modelHint: "Gemini",
    systemPrompt: "You are DASH Research. Find, analyze, and summarize information. Cite sources. Be thorough but concise.",
    placeholder: "What do you want to research?",
  },
  {
    id: "executor",
    label: "Executor",
    icon: Zap,
    color: "#ef4444",
    glowColor: "rgba(239, 68, 68, 0.25)",
    modelHint: "Fast-Path",
    systemPrompt: "You are DASH Executor. Execute tasks immediately. Use available tools. Report results clearly.",
    placeholder: "What task should DASH execute?",
  },
];

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
  const { selectedModelId, models } = useModelStore();

  const [activeMode, setActiveMode] = useState("general");
  const [inputText, setInputText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

  const currentMode = AGENT_MODES.find((m) => m.id === activeMode) || AGENT_MODES[0];
  const selectedModel = models.find((m) => m.id === selectedModelId);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, assistantMessage]);

  // Auto-focus input
  useEffect(() => {
    inputRef.current?.focus();
  }, [activeMode]);

  // Scroll detection
  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (el) {
      setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 200);
    }
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + "px";
    }
  }, [inputText]);

  // Speech recognition
  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";
      recognition.onresult = (event: any) => {
        const transcript = event.results[0]?.[0]?.transcript;
        if (transcript) setInputText(transcript);
        setIsListening(false);
      };
      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);
      recognitionRef.current = recognition;
    }
  }, []);

  const handleSend = () => {
    if (!inputText.trim() || isProcessing) return;
    useChatStore.setState({ input: inputText.trim() });
    sendMessage(undefined, activeMode);
    setInputText("");
    if (inputRef.current) inputRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
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
      recognitionRef.current.start();
      setIsListening(true);
    }
  };

  const copyMessage = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const allMessages = [
    ...messages,
    ...(assistantMessage
      ? [{ id: assistantMessage.id || "streaming", role: "assistant" as const, content: assistantMessage.content || "" }]
      : []),
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--dash-bg)" }}>
      {/* ── Agent Mode Tabs ──────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          padding: "8px 16px",
          borderBottom: "1px solid var(--dash-border-subtle)",
          background: "var(--dash-bg-subtle)",
          overflow: "visible",
          flexShrink: 0,
        }}
      >
        {AGENT_MODES.map((mode) => {
          const Icon = mode.icon;
          const isActive = activeMode === mode.id;
          return (
            <button
              key={mode.id}
              onClick={() => setActiveMode(mode.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 8,
                border: isActive ? `1px solid ${mode.color}40` : "1px solid transparent",
                background: isActive ? `${mode.glowColor}` : "transparent",
                color: isActive ? mode.color : "var(--dash-text-muted)",
                fontSize: 12,
                fontWeight: 500,
                fontFamily: "'Orbitron', monospace",
                letterSpacing: "0.05em",
                cursor: "pointer",
                transition: "all 150ms ease",
                boxShadow: isActive ? `0 0 12px ${mode.glowColor}` : "none",
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = `${mode.glowColor}40`;
                  e.currentTarget.style.color = mode.color;
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--dash-text-muted)";
                }
              }}
            >
              <Icon size={14} />
              <span>{mode.label}</span>
            </button>
          );
        })}

        {/* Model info badge */}
        <div
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexShrink: 0,
          }}
        >
          <ModelSelector />
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: websocketStatus === "connected" ? "var(--dash-success)" : "var(--dash-danger)",
              boxShadow: websocketStatus === "connected" ? "0 0 6px rgba(34, 197, 94, 0.5)" : "none",
            }}
          />
        </div>
      </div>

      {/* ── Mode Info Bar ────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 16px",
          borderBottom: "1px solid var(--dash-border-subtle)",
          fontSize: 11,
          color: "var(--dash-text-muted)",
          fontFamily: "'Orbitron', monospace",
          letterSpacing: "0.08em",
          flexShrink: 0,
        }}
      >
        <span style={{ color: currentMode.color }}>{currentMode.label.toUpperCase()}</span>
        <span>·</span>
        <span>{currentMode.modelHint}</span>
        <span>·</span>
        <span>{currentMode.placeholder}</span>
      </div>

      {/* ── Messages ─────────────────────────────────────────── */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        style={{ flex: 1, overflowY: "auto", padding: "16px" }}
      >
        {allMessages.length === 0 ? (
          <EmptyState mode={currentMode} />
        ) : (
          <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", flexDirection: "column", gap: 16 }}>
            {allMessages.map((msg, i) => (
              <MessageBubble
                key={msg.id || i}
                message={msg}
                mode={currentMode}
                onCopy={() => copyMessage(msg.id || String(i), msg.content)}
                isCopied={copiedId === (msg.id || String(i))}
              />
            ))}

            {/* Typing indicator */}
            {isProcessing && !assistantMessage && (
              <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: currentMode.glowColor,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    border: `1px solid ${currentMode.color}30`,
                  }}
                >
                  <Bot size={16} style={{ color: currentMode.color }} />
                </div>
                <div style={{ padding: "12px 16px", borderRadius: 16, background: "var(--dash-surface)" }}>
                  <TypingIndicator color={currentMode.color} />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Scroll to bottom */}
        {showScrollBtn && (
          <button
            onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })}
            style={{
              position: "fixed",
              bottom: 80,
              right: 32,
              width: 40,
              height: 40,
              borderRadius: "50%",
              background: "var(--dash-surface)",
              border: "1px solid var(--dash-border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--dash-text-secondary)",
              cursor: "pointer",
              boxShadow: "var(--dash-shadow-md)",
              zIndex: 10,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1v12M1 7l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </div>

      {/* ── Input Bar ────────────────────────────────────────── */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--dash-border-subtle)",
          background: "var(--dash-bg-subtle)",
        }}
      >
        <div style={{ maxWidth: 800, margin: "0 auto" }}>
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              gap: 8,
              padding: "8px 12px",
              borderRadius: 16,
              background: "var(--dash-surface)",
              border: `1px solid var(--dash-border)`,
              transition: "border-color 200ms ease",
            }}
            onFocus={(e) => {
              (e.currentTarget as HTMLElement).style.borderColor = currentMode.color + "60";
            }}
            onBlur={(e) => {
              (e.currentTarget as HTMLElement).style.borderColor = "var(--dash-border)";
            }}
          >
            {/* Attachment */}
            <button
              style={{
                padding: 4,
                color: "var(--dash-text-muted)",
                cursor: "pointer",
                background: "none",
                border: "none",
                marginBottom: 2,
              }}
            >
              <Paperclip size={18} />
            </button>

            {/* Input */}
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={currentMode.placeholder}
              rows={1}
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "var(--dash-text)",
                fontSize: 14,
                resize: "none",
                maxHeight: 150,
                padding: "4px 0",
                fontFamily: "'Inter', sans-serif",
              }}
            />

            {/* Mic */}
            <button
              onClick={toggleMic}
              style={{
                padding: 4,
                color: isListening ? "#ef4444" : "var(--dash-text-muted)",
                background: isListening ? "rgba(239, 68, 68, 0.15)" : "none",
                border: "none",
                borderRadius: 6,
                cursor: "pointer",
                marginBottom: 2,
              }}
            >
              {isListening ? <MicOff size={18} /> : <Mic size={18} />}
            </button>

            {/* Send / Stop */}
            {isProcessing ? (
              <button
                onClick={cancelRequest}
                style={{
                  padding: 4,
                  color: "#ef4444",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  marginBottom: 2,
                }}
              >
                <StopCircle size={18} />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!inputText.trim()}
                style={{
                  padding: 4,
                  color: inputText.trim() ? currentMode.color : "var(--dash-text-muted)",
                  background: "none",
                  border: "none",
                  cursor: inputText.trim() ? "pointer" : "default",
                  marginBottom: 2,
                  transition: "color 150ms ease",
                }}
              >
                <Send size={18} />
              </button>
            )}
          </div>

          {/* Model info */}
          <div style={{ textAlign: "center", marginTop: 8, fontSize: 11, color: "var(--dash-text-muted)" }}>
            {selectedModel ? selectedModel.name : "No model selected"} · DASH can make mistakes
          </div>
        </div>
      </div>
    </div>
  );
};

/* ── Message Bubble ──────────────────────────────────────────── */

const MessageBubble: React.FC<{
  message: { id?: string; role: string; content: string };
  mode: AgentMode;
  onCopy: () => void;
  isCopied: boolean;
}> = ({ message, mode, onCopy, isCopied }) => {
  const isUser = message.role === "user";

  return (
    <div style={{ display: "flex", gap: 10, flexDirection: isUser ? "row-reverse" : "row", alignItems: "flex-start" }}>
      {/* Avatar */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: isUser ? "rgba(168, 85, 247, 0.15)" : mode.glowColor,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          border: `1px solid ${isUser ? "rgba(168, 85, 247, 0.3)" : mode.color + "30"}`,
        }}
      >
        {isUser ? (
          <User size={16} style={{ color: "#a855f7" }} />
        ) : (
          <Bot size={16} style={{ color: mode.color }} />
        )}
      </div>

      {/* Content */}
      <div style={{ maxWidth: "85%", position: "relative" }}>
        <div
          style={{
            padding: "10px 14px",
            borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
            background: isUser ? `${mode.color}15` : "var(--dash-surface)",
            color: "var(--dash-text)",
            fontSize: 13,
            lineHeight: 1.6,
            border: `1px solid ${isUser ? mode.color + "20" : "var(--dash-border-subtle)"}`,
          }}
        >
          <MessageContent content={message.content} />
        </div>

        {/* Actions */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            marginTop: 4,
            opacity: 0,
            transition: "opacity 150ms ease",
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = "1"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = "0"; }}
        >
          <button
            onClick={onCopy}
            style={{ padding: 2, color: "var(--dash-text-muted)", background: "none", border: "none", cursor: "pointer" }}
          >
            {isCopied ? <Check size={12} /> : <Copy size={12} />}
          </button>
          {!isUser && (
            <button style={{ padding: 2, color: "var(--dash-text-muted)", background: "none", border: "none", cursor: "pointer" }}>
              <RefreshCw size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

/* ── Message Content (markdown-like) ─────────────────────────── */

const MessageContent: React.FC<{ content: string }> = ({ content }) => {
  const parts = content.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*)/g);

  return (
    <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {parts.map((part, i) => {
        if (part.startsWith("```")) {
          const code = part.replace(/```\w*\n?/g, "").replace(/```$/g, "");
          return (
            <pre
              key={i}
              style={{
                background: "rgba(0,0,0,0.3)",
                borderRadius: 8,
                padding: 12,
                margin: "8px 0",
                overflowX: "auto",
                fontSize: 12,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              <code>{code}</code>
            </pre>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={i}
              style={{
                background: "rgba(255,255,255,0.08)",
                padding: "1px 5px",
                borderRadius: 4,
                fontSize: 12,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
};

/* ── Typing Indicator ────────────────────────────────────────── */

const TypingIndicator: React.FC<{ color: string }> = ({ color }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 0" }}>
    {[0, 1, 2].map((i) => (
      <div
        key={i}
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: color,
          opacity: 0.5,
          animation: `typing 1.4s infinite`,
          animationDelay: `${i * 0.2}s`,
        }}
      />
    ))}
    <style>{`
      @keyframes typing {
        0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
        30% { opacity: 1; transform: scale(1); }
      }
    `}</style>
  </div>
);

/* ── Empty State ─────────────────────────────────────────────── */

const EmptyState: React.FC<{ mode: AgentMode }> = ({ mode }) => {
  const { sendMessage } = useChatStore();

  const suggestions: Record<string, { icon: string; text: string }[]> = {
    general: [
      { icon: "🤖", text: "What can you do for me?" },
      { icon: "📊", text: "Show me system health" },
      { icon: "🔐", text: "Check security status" },
      { icon: "💡", text: "Suggest automations" },
    ],
    coder: [
      { icon: "🐍", text: "Write a Python script to organize files" },
      { icon: "⚡", text: "Create a TypeScript utility function" },
      { icon: "🔧", text: "Debug this error in my code" },
      { icon: "📦", text: "Generate a REST API endpoint" },
    ],
    planner: [
      { icon: "📋", text: "Plan a weekly backup schedule" },
      { icon: "🎯", text: "Break down a complex project" },
      { icon: "⏰", text: "Create a maintenance checklist" },
      { icon: "🚀", text: "Plan a deployment strategy" },
    ],
    research: [
      { icon: "🔍", text: "Compare Python web frameworks" },
      { icon: "📈", text: "Research best practices for Docker" },
      { icon: "🌐", text: "Find information about cloud services" },
      { icon: "📚", text: "Explain how neural networks work" },
    ],
    executor: [
      { icon: "⚡", text: "Clean up my Downloads folder" },
      { icon: "🗑️", text: "Find and delete duplicate files" },
      { icon: "📁", text: "Organize files by type" },
      { icon: "🔄", text: "Run system diagnostics" },
    ],
  };

  const items = suggestions[mode.id] || suggestions.general;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", padding: "0 16px" }}>
      {/* Logo */}
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 16,
          background: `linear-gradient(135deg, ${mode.color}25, ${mode.color}10)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 20,
          border: `1px solid ${mode.color}30`,
          boxShadow: `0 0 20px ${mode.glowColor}`,
        }}
      >
        <mode.icon size={28} style={{ color: mode.color }} />
      </div>

      <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--dash-text)", marginBottom: 6, fontFamily: "'Orbitron', monospace", letterSpacing: "0.05em" }}>
        {mode.label} Mode
      </h1>
      <p style={{ fontSize: 13, color: "var(--dash-text-muted)", marginBottom: 24 }}>
        {mode.modelHint} · {mode.placeholder}
      </p>

      {/* Suggestions */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, maxWidth: 500, width: "100%" }}>
        {items.map((s, i) => (
          <button
            key={i}
            onClick={() => {
              useChatStore.setState({ input: s.text });
              sendMessage();
            }}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: 12,
              borderRadius: 12,
              background: "var(--dash-surface)",
              border: "1px solid var(--dash-border-subtle)",
              cursor: "pointer",
              textAlign: "left",
              transition: "all 150ms ease",
              color: "var(--dash-text-secondary)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--dash-surface-hover)";
              e.currentTarget.style.borderColor = mode.color + "30";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--dash-surface)";
              e.currentTarget.style.borderColor = "var(--dash-border-subtle)";
            }}
          >
            <span style={{ fontSize: 18 }}>{s.icon}</span>
            <span style={{ fontSize: 12, lineHeight: 1.5 }}>{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default ChatPage;
