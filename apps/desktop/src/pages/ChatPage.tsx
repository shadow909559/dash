/**
 * ChatPage — ChatGPT/Gemini-style chat interface.
 *
 * Features:
 * - Clean message bubbles (user right, assistant left)
 * - Typing indicator with animated dots
 * - Model selector at top
 * - Input bar with send/mic/attachments
 * - Copy messages, regenerate responses
 * - Streaming text display
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
  Loader2,
  Copy,
  Check,
  RefreshCw,
  Paperclip,
  StopCircle,
  MoreHorizontal,
  Trash2,
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
  const { selectedModelId, models } = useModelStore();

  const [inputText, setInputText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

  const selectedModel = models.find((m) => m.id === selectedModelId);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, assistantMessage]);

  // Auto-focus input
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Scroll detection for "scroll to bottom" button
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
    // Store the input text in the store's input field, then call sendMessage
    useChatStore.setState({ input: inputText.trim() });
    sendMessage();
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
    <div className="flex flex-col h-full bg-[#0d0d1a]">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/5">
        <ModelSelector />
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              onClick={clearMessages}
              className="p-1.5 rounded-lg text-white/30 hover:text-white/60 hover:bg-white/5"
              title="New chat"
            >
              <Trash2 size={16} />
            </button>
          )}
          <div
            className={`w-2 h-2 rounded-full ${
              websocketStatus === "connected" ? "bg-green-400" : "bg-red-400"
            }`}
            title={websocketStatus}
          />
        </div>
      </div>

      {/* ── Messages ───────────────────────────────────────────── */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        {allMessages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {allMessages.map((msg, i) => (
              <MessageBubble
                key={msg.id || i}
                message={msg}
                onCopy={() => copyMessage(msg.id || String(i), msg.content)}
                isCopied={copiedId === (msg.id || String(i))}
              />
            ))}

            {/* Typing indicator */}
            {isProcessing && !assistantMessage && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
                  <Bot size={16} className="text-cyan-400" />
                </div>
                <div className="px-4 py-3 rounded-2xl bg-white/5">
                  <TypingIndicator />
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
            className="fixed bottom-24 right-8 w-10 h-10 rounded-full
              bg-[#1a1a2e] border border-white/10 shadow-lg
              flex items-center justify-center text-white/60 hover:text-white
              transition-all z-10"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1v12M1 7l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </div>

      {/* ── Input Bar ──────────────────────────────────────────── */}
      <div className="border-t border-white/5 px-4 py-3">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 bg-white/5 border border-white/10 rounded-2xl px-3 py-2
            focus-within:border-cyan-500/30 transition-colors">
            {/* Attachment button */}
            <button className="p-1.5 text-white/30 hover:text-white/60 mb-0.5">
              <Paperclip size={18} />
            </button>

            {/* Input */}
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message DASH..."
              rows={1}
              className="flex-1 bg-transparent text-sm text-white placeholder-white/30
                resize-none outline-none max-h-[150px] py-1.5"
            />

            {/* Mic button */}
            <button
              onClick={toggleMic}
              className={`p-1.5 mb-0.5 rounded-lg transition-colors ${
                isListening
                  ? "text-red-400 bg-red-500/20"
                  : "text-white/30 hover:text-white/60"
              }`}
            >
              {isListening ? <MicOff size={18} /> : <Mic size={18} />}
            </button>

            {/* Send / Stop */}
            {isProcessing ? (
              <button
                onClick={cancelRequest}
                className="p-1.5 text-red-400 hover:text-red-300 mb-0.5"
              >
                <StopCircle size={18} />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!inputText.trim()}
                className={`p-1.5 rounded-lg mb-0.5 transition-all ${
                  inputText.trim()
                    ? "text-cyan-400 hover:bg-cyan-500/20"
                    : "text-white/20"
                }`}
              >
                <Send size={18} />
              </button>
            )}
          </div>

          {/* Model info */}
          <div className="text-center mt-2">
            <span className="text-[11px] text-white/20">
              {selectedModel ? `${selectedModel.name}` : "No model selected"}
              {" · "}DASH can make mistakes
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Message Bubble ───────────────────────────────────────────────

const MessageBubble: React.FC<{
  message: { id?: string; role: string; content: string };
  onCopy: () => void;
  isCopied: boolean;
}> = ({ message, onCopy, isCopied }) => {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          isUser
            ? "bg-purple-500/20"
            : "bg-cyan-500/20"
        }`}
      >
        {isUser ? (
          <User size={16} className="text-purple-400" />
        ) : (
          <Bot size={16} className="text-cyan-400" />
        )}
      </div>

      {/* Content */}
      <div className={`group relative max-w-[85%] ${isUser ? "text-right" : ""}`}>
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-cyan-500/15 text-white/90 rounded-br-md"
              : "bg-white/5 text-white/80 rounded-bl-md"
          }`}
        >
          <MessageContent content={message.content} />
        </div>

        {/* Actions */}
        <div
          className={`flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity ${
            isUser ? "justify-end" : ""
          }`}
        >
          <button
            onClick={onCopy}
            className="p-1 text-white/20 hover:text-white/50 rounded"
          >
            {isCopied ? <Check size={12} /> : <Copy size={12} />}
          </button>
          {!isUser && (
            <button className="p-1 text-white/20 hover:text-white/50 rounded">
              <RefreshCw size={12} />
            </button>
          )}
          <button className="p-1 text-white/20 hover:text-white/50 rounded">
            <MoreHorizontal size={12} />
          </button>
        </div>
      </div>
    </div>
  );
};

// ── Message Content (handles markdown-like formatting) ───────────

const MessageContent: React.FC<{ content: string }> = ({ content }) => {
  // Simple markdown: code blocks, bold, italic
  const parts = content.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*)/g);

  return (
    <div className="whitespace-pre-wrap break-words">
      {parts.map((part, i) => {
        if (part.startsWith("```")) {
          const code = part.replace(/```\w*\n?/g, "").replace(/```$/g, "");
          return (
            <pre key={i} className="bg-black/30 rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono">
              <code>{code}</code>
            </pre>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={i} className="bg-white/10 px-1.5 py-0.5 rounded text-xs font-mono">
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

// ── Typing Indicator ─────────────────────────────────────────────

const TypingIndicator: React.FC = () => (
  <div className="flex items-center gap-1 py-1">
    {[0, 1, 2].map((i) => (
      <div
        key={i}
        className="w-1.5 h-1.5 rounded-full bg-cyan-400/60"
        style={{
          animation: "typing 1.4s infinite",
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

// ── Empty State (ChatGPT-style welcome) ──────────────────────────

const EmptyState: React.FC = () => {
  const { sendMessage } = useChatStore();
  const { selectedModelId, models } = useModelStore();
  const model = models.find((m) => m.id === selectedModelId);

  const suggestions = [
    { icon: "💻", text: "Write a Python script to organize my Downloads" },
    { icon: "🔍", text: "Find all large files on my system" },
    { icon: "📊", text: "Show me system health and performance" },
    { icon: "🔒", text: "Check for security issues on my PC" },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full px-4">
      {/* Logo */}
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20
        flex items-center justify-center mb-6 border border-cyan-500/20">
        <Sparkles size={28} className="text-cyan-400" />
      </div>

      <h1 className="text-2xl font-semibold text-white/90 mb-2">
        How can I help you today?
      </h1>
      <p className="text-sm text-white/40 mb-8">
        {model ? `Powered by ${model.name}` : "Select a model to get started"}
      </p>

      {/* Suggestion cards */}
      <div className="grid grid-cols-2 gap-3 max-w-lg w-full">
        {suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => {
              useChatStore.setState({ input: s.text });
              sendMessage();
            }}
            className="flex items-start gap-3 p-3 rounded-xl bg-white/3 border border-white/5
              hover:bg-white/5 hover:border-white/10 transition-all text-left group"
          >
            <span className="text-lg">{s.icon}</span>
            <span className="text-xs text-white/50 group-hover:text-white/70 leading-relaxed">
              {s.text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default ChatPage;
