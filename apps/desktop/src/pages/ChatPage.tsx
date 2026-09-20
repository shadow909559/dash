/**
 * ChatPage — JARVIS-style multi-agent chat with fixed layout.
 * Agent tabs stay within bounds, info bar is compact, no overflow.
 */
import React, { useState, useRef, useEffect, useCallback } from "react";
import { useChatStore } from "@/stores/chatStore";
import { useAIStore } from "@/stores/aiStore";
import { useModelStore } from "@/stores/modelStore";
import { useOrchestratorStore } from "@/stores/orchestratorStore";
import { getWsClient } from "@/lib/wsClient";
import { LiveRegion } from "@/components/LiveRegion";
import { StreamingCaret, StaggerItem, TypingIndicator } from "@/components/fx";
import { ModelSelector } from "@/components/ModelSelector";
import {
  Send, Mic, MicOff, Bot, User, Copy, Check, Paperclip, StopCircle,
  Code2, CalendarDays, Compass, Zap, MessageSquare, Layers,
} from "lucide-react";

interface AgentMode {
  id: string;
  label: string;
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
  color: string;
  glow: string;
  hint: string;
  placeholder: string;
}

const MODES: AgentMode[] = [
  { id: "general", label: "General", icon: MessageSquare, color: "#3fa9f5", glow: "rgba(63,169,245,0.2)", hint: "Cloud AI", placeholder: "Ask DASH anything..." },
  { id: "coder", label: "Coder", icon: Code2, color: "#22c55e", glow: "rgba(34,197,94,0.2)", hint: "Code", placeholder: "Describe what to code..." },
  { id: "planner", label: "Planner", icon: CalendarDays, color: "#eab308", glow: "rgba(234,179,8,0.2)", hint: "Plan", placeholder: "What to accomplish?" },
  { id: "research", label: "Research", icon: Compass, color: "#a855f7", glow: "rgba(168,85,247,0.2)", hint: "Research", placeholder: "What to research?" },
  { id: "executor", label: "Execute", icon: Zap, color: "#ef4444", glow: "rgba(239,68,68,0.2)", hint: "Run", placeholder: "What task to execute?" },
];

export const ChatPage: React.FC = () => {
  const { assistantMessage, isProcessing, sendMessage, cancelRequest, getActiveMessages, setActiveMode: setStoreMode } = useChatStore();
  const messages = getActiveMessages();
  const { websocketStatus } = useAIStore();
  const { selectedModelId, models } = useModelStore();
  const orch = useOrchestratorStore();
  const [mode, setMode] = useState("general");
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recogRef = useRef<any>(null);
  const current = MODES.find((m) => m.id === mode) || MODES[0];
  const model = models.find((m) => m.id === selectedModelId);

  const switchMode = (m: string) => { setMode(m); setStoreMode(m); };

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, assistantMessage]);
  useEffect(() => { inputRef.current?.focus(); }, [mode]);
  useEffect(() => {
    if (inputRef.current) { inputRef.current.style.height = "auto"; inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + "px"; }
  }, [input]);

  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SR) {
      const r = new SR(); r.continuous = false; r.interimResults = false; r.lang = "en-US";
      r.onresult = (e: any) => { const t = e.results[0]?.[0]?.transcript; if (t) setInput(t); setListening(false); };
      r.onerror = () => setListening(false); r.onend = () => setListening(false);
      recogRef.current = r;
    }
  }, []);

  const send = () => {
    if (!input.trim() || isProcessing) return;
    useChatStore.setState({ input: input.trim() });
    sendMessage(undefined, mode);
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";
  };
  const onKey = (e: React.KeyboardEvent) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
  const toggleMic = () => { if (!recogRef.current) return; listening ? (recogRef.current.stop(), setListening(false)) : (recogRef.current.start(), setListening(true)); };
  const copyMsg = (id: string, text: string) => { navigator.clipboard.writeText(text); setCopied(id); setTimeout(() => setCopied(null), 2000); };
  const runOrch = () => { if (!input.trim() || isProcessing) return; getWsClient().sendOrchestratorRun(input.trim()); useOrchestratorStore.getState().startRun(input.trim()); setInput(""); };

  const allMsgs = [...messages, ...(assistantMessage ? [{ id: assistantMessage.id || "s", role: "assistant" as const, content: (assistantMessage.content || "") + "\u0000STREAMING", streaming: true }] : [])];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, overflow: "hidden" }}>
      {/* ── Agent Tabs + Model Selector (single row, no overflow) ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 2, padding: "6px 12px", borderBottom: "1px solid var(--dash-border-subtle)", background: "var(--dash-bg-subtle)", flexShrink: 0, overflowX: "auto", overflowY: "hidden" }}>
        {MODES.map((m) => {
          const Ic = m.icon; const act = mode === m.id;
          return (
            <button key={m.id} onClick={() => switchMode(m.id)} style={{
              display: "flex", alignItems: "center", gap: 4, padding: "5px 10px", borderRadius: 6,
              border: act ? `1px solid ${m.color}50` : "1px solid transparent",
              background: act ? m.glow : "transparent", color: act ? m.color : "var(--dash-text-muted)",
              fontSize: 11, fontWeight: 500, fontFamily: "'Orbitron',monospace", letterSpacing: "0.04em",
              cursor: "pointer", transition: "all 150ms", whiteSpace: "nowrap", flexShrink: 0,
            }}>
              <Ic size={12} />{m.label}
            </button>
          );
        })}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <ModelSelector />
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: websocketStatus === "connected" ? "#22c55e" : "#ef4444", boxShadow: websocketStatus === "connected" ? "0 0 6px rgba(34,197,94,0.5)" : "none" }} />
        </div>
      </div>

      {/* ── Status Bar ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 12px", borderBottom: "1px solid var(--dash-border-subtle)", fontSize: 10, color: "var(--dash-text-muted)", fontFamily: "'Orbitron',monospace", letterSpacing: "0.06em", flexShrink: 0 }}>
        <span style={{ color: current.color }}>{current.label.toUpperCase()}</span>
        <span>·</span><span>{current.hint}</span>
        {orch.status !== "idle" && <><span>·</span><span style={{ color: "#eab308" }}>ORCH: {orch.message}</span></>}
      </div>

      {/* Screen reader announcement for new messages */}
      <LiveRegion>
        {assistantMessage?.content
          ? `Assistant: ${assistantMessage.content.slice(-200)}`
          : isProcessing
          ? "Assistant is typing"
          : ""}
      </LiveRegion>

      {/* ── Messages ── */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "12px", minHeight: 0 }}>
        {allMsgs.length === 0 ? (
          <EmptyState mode={current} onSend={(t) => { setInput(t); setTimeout(send, 50); }} onOrch={(t) => { setInput(t); setTimeout(runOrch, 50); }} />
        ) : (
          <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Orchestrator progress */}
            {orch.status !== "idle" && orch.steps.length > 0 && <OrchestratorProgress />}
            {allMsgs.map((msg, i) => (
              <Bubble key={msg.id || i} msg={msg} mode={current} onCopy={() => copyMsg(msg.id || String(i), msg.content)} copied={copied === (msg.id || String(i))} />
            ))}
            {isProcessing && !assistantMessage && <Typing color={current.color} />}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* ── Input ── */}
      <div style={{ padding: "8px 12px", borderTop: "1px solid var(--dash-border-subtle)", background: "var(--dash-bg-subtle)", flexShrink: 0 }}>
        <div style={{ maxWidth: 800, margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 6, padding: "6px 10px", borderRadius: 12, background: "var(--dash-surface)", border: "1px solid var(--dash-border)" }}>
            <button style={{ padding: 3, color: "var(--dash-text-muted)", background: "none", border: "none", marginBottom: 1 }}><Paperclip size={16} /></button>
            <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey}
              placeholder={current.placeholder} rows={1}
              style={{ flex: 1, background: "transparent", border: "none", color: "var(--dash-text)", fontSize: 13, resize: "none", maxHeight: 120, padding: "3px 0", fontFamily: "'Inter',sans-serif" }} />
            <button onClick={toggleMic} style={{ padding: 3, color: listening ? "#ef4444" : "var(--dash-text-muted)", background: listening ? "rgba(239,68,68,0.15)" : "none", border: "none", borderRadius: 4, cursor: "pointer", marginBottom: 1 }}>
              {listening ? <MicOff size={16} /> : <Mic size={16} />}
            </button>
            <button onClick={runOrch} title="Run orchestrator" style={{ padding: 3, color: "#eab308", background: "none", border: "none", borderRadius: 4, cursor: "pointer", marginBottom: 1, opacity: input.trim() && !isProcessing ? 1 : 0.3 }}>
              <Layers size={16} />
            </button>
            {isProcessing ? (
              <button onClick={cancelRequest} style={{ padding: 3, color: "#ef4444", background: "none", border: "none", cursor: "pointer", marginBottom: 1 }}><StopCircle size={16} /></button>
            ) : (
              <button onClick={send} disabled={!input.trim()} style={{ padding: 3, color: input.trim() ? current.color : "var(--dash-text-muted)", background: "none", border: "none", cursor: input.trim() ? "pointer" : "default", marginBottom: 1 }}><Send size={16} /></button>
            )}
          </div>
          <div style={{ textAlign: "center", marginTop: 4, fontSize: 10, color: "var(--dash-text-muted)" }}>
            {model?.name || "No model"} · DASH can make mistakes
          </div>
        </div>
      </div>
    </div>
  );
};

/* ── Orchestrator Progress ── */
const OrchestratorProgress: React.FC = () => {
  const { steps, currentStep, status, summary } = useOrchestratorStore();
  return (
    <div style={{ background: "var(--dash-surface)", border: "1px solid var(--dash-border)", borderRadius: 10, padding: 12, marginBottom: 8 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "#eab308", fontFamily: "'Orbitron',monospace", marginBottom: 8 }}>
        ORCHESTRATOR — {status.toUpperCase()}
      </div>
      {steps.map((s, i) => (
        <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0", fontSize: 11, color: s.status === "completed" ? "#22c55e" : s.status === "failed" ? "#ef4444" : s.status === "running" ? "#eab308" : "var(--dash-text-muted)" }}>
          <span style={{ width: 16, textAlign: "center" }}>{s.status === "completed" ? "✓" : s.status === "failed" ? "✗" : s.status === "running" ? "⟳" : "○"}</span>
          <span style={{ flex: 1 }}>{s.description.slice(0, 60)}</span>
          <span style={{ fontSize: 9, opacity: 0.6 }}>{s.agent}</span>
        </div>
      ))}
      {status === "complete" && summary && <div style={{ marginTop: 8, fontSize: 11, color: "var(--dash-text-secondary)", borderTop: "1px solid var(--dash-border-subtle)", paddingTop: 8 }}>{summary.slice(0, 300)}</div>}
    </div>
  );
};

/* ── Bubble — layered-surface redesign: edge-light, per-mode accent
      frame, hover actions. Content and copy behavior unchanged. ── */
const Bubble: React.FC<{ msg: { id?: string; role: string; content: string; streaming?: boolean }; mode: AgentMode; onCopy: () => void; copied: boolean }> = ({ msg, mode, onCopy, copied }) => {
  const u = msg.role === "user";
  return (
    <div style={{ display: "flex", gap: 10, flexDirection: u ? "row-reverse" : "row", alignItems: "flex-start" }}>
      {/* Avatar — instrument chip with mode-tinted ring */}
      <div style={{
        width: 28, height: 28, borderRadius: 9, flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: u ? "rgba(168,85,247,0.12)" : `linear-gradient(135deg, ${mode.color}22, ${mode.color}0a)`,
        border: `1px solid ${u ? "rgba(168,85,247,0.35)" : mode.color + "40"}`,
        boxShadow: u ? "none" : `0 0 10px ${mode.glow}`,
      }}>
        {u ? <User size={14} style={{ color: "#c084fc" }} /> : <Bot size={14} style={{ color: mode.color }} />}
      </div>
      <div style={{ maxWidth: "85%", position: "relative", minWidth: 0 }}>
        <div style={{
          padding: "10px 14px",
          borderRadius: u ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
          background: u
            ? `linear-gradient(135deg, ${mode.color}16, ${mode.color}0a)`
            : "linear-gradient(180deg, rgba(96,160,235,0.05), rgba(96,160,235,0.015))",
          color: "var(--dash-text)", fontSize: 13, lineHeight: 1.55,
          border: `1px solid ${u ? mode.color + "2a" : "var(--dash-border)"}`,
          boxShadow: u
            ? "none"
            : "inset 0 1px 0 rgba(200, 228, 255, 0.05), 0 2px 10px rgba(0, 0, 0, 0.3)",
          wordBreak: "break-word",
        }}>
          <MsgContent content={msg.content} streaming={msg.streaming} modeColor={mode.color} />
        </div>
        <div style={{ display: "flex", gap: 4, marginTop: 3, justifyContent: u ? "flex-end" : "flex-start", opacity: 0, transition: "opacity 150ms" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = "1"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = "0"; }}>
          <button onClick={onCopy} aria-label="Copy message" style={{ padding: 2, borderRadius: 4, color: copied ? "#22c55e" : "var(--dash-text-muted)", background: "none", border: "none", cursor: "pointer" }}>
            {copied ? <Check size={11} /> : <Copy size={11} />}
          </button>
        </div>
        {/* Per-mode accent thread under assistant bubbles */}
        {!u && (
          <div aria-hidden style={{
            position: "absolute", left: 14, bottom: -1, width: 28, height: 2, borderRadius: 1,
            background: `linear-gradient(90deg, ${mode.color}70, transparent)`,
          }} />
        )}
      </div>
    </div>
  );
};

/* ── MsgContent ── */
const MsgContent: React.FC<{ content: string; streaming?: boolean; modeColor?: string }> = ({ content, streaming, modeColor }) => {
  const live = streaming && content.endsWith("\u0000STREAMING");
  const text = live ? content.slice(0, -"\u0000STREAMING".length) : content;
  const parts = text.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*)/g);
  return (
    <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {parts.map((p, i) => {
        if (p.startsWith("```")) { const c = p.replace(/```\w*\n?/g, "").replace(/```$/g, ""); return <pre key={i} style={{ background: "rgba(4, 8, 15, 0.55)", border: "1px solid var(--dash-border-subtle)", borderRadius: 8, padding: 10, margin: "8px 0", overflowX: "auto", fontSize: 12, lineHeight: 1.55, fontFamily: "'JetBrains Mono',monospace", boxShadow: "inset 0 1px 0 rgba(200,228,255,0.04)" }}><code>{c}</code></pre>; }
        if (p.startsWith("`") && p.endsWith("`")) return <code key={i} style={{ background: "rgba(63,169,245,0.10)", border: "1px solid rgba(63,169,245,0.16)", padding: "1px 5px", borderRadius: 4, fontSize: 12, fontFamily: "'JetBrains Mono',monospace", color: "#7dc4f8" }}>{p.slice(1, -1)}</code>;
        if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
        return <span key={i}>{p}{live && i === parts.length - 1 && <StreamingCaret color={modeColor} />}</span>;
      })}
    </div>
  );
};

/* ── Typing — fx TypingIndicator inside a matching bubble shell ── */
const Typing: React.FC<{ color: string }> = ({ color }) => (
  <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
    <div style={{
      width: 28, height: 28, borderRadius: 9, flexShrink: 0,
      display: "flex", alignItems: "center", justifyContent: "center",
      background: `linear-gradient(135deg, ${color}22, ${color}0a)`,
      border: `1px solid ${color}40`, boxShadow: `0 0 10px ${color}20`,
    }}><Bot size={14} style={{ color }} /></div>
    <div style={{
      padding: "12px 16px", borderRadius: "14px 14px 14px 4px",
      background: "linear-gradient(180deg, rgba(96,160,235,0.05), rgba(96,160,235,0.015))",
      border: "1px solid var(--dash-border)",
      boxShadow: "inset 0 1px 0 rgba(200, 228, 255, 0.05)",
    }}>
      <TypingIndicator color={color} label={"DASH IS THINKING"} />
    </div>
  </div>
);

/* ── EmptyState ── */
const EmptyState: React.FC<{ mode: AgentMode; onSend: (t: string) => void; onOrch: (t: string) => void }> = ({ mode, onSend, onOrch }) => {
  const suggestions: Record<string, { icon: string; text: string; orch?: boolean }[]> = {
    general: [
      { icon: "🤖", text: "What can you do for me?" },
      { icon: "📊", text: "Show me system health" },
      { icon: "🔐", text: "Check security status" },
      { icon: "💡", text: "Suggest automations" },
    ],
    coder: [
      { icon: "🐍", text: "Write a Python file organizer script" },
      { icon: "⚡", text: "Create a TypeScript utility function" },
      { icon: "🔧", text: "Debug this error in my code" },
      { icon: "📦", text: "Generate a REST API endpoint", orch: true },
    ],
    planner: [
      { icon: "📋", text: "Plan a weekly backup schedule" },
      { icon: "🎯", text: "Break down a complex project", orch: true },
      { icon: "⏰", text: "Create a maintenance checklist" },
      { icon: "🚀", text: "Plan a deployment strategy", orch: true },
    ],
    research: [
      { icon: "🔍", text: "Compare Python web frameworks" },
      { icon: "📈", text: "Research Docker best practices" },
      { icon: "🌐", text: "Find cloud service pricing" },
      { icon: "📚", text: "Explain neural networks" },
    ],
    executor: [
      { icon: "⚡", text: "Clean up Downloads folder" },
      { icon: "🗑️", text: "Find duplicate files" },
      { icon: "📁", text: "Organize files by type" },
      { icon: "🔄", text: "Run system diagnostics", orch: true },
    ],
  };
  const items = suggestions[mode.id] || suggestions.general;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", padding: "0 12px" }}>
      <div style={{ width: 56, height: 56, borderRadius: 14, background: `linear-gradient(135deg, ${mode.color}20, ${mode.color}08)`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16, border: `1px solid ${mode.color}25`, boxShadow: `0 0 16px ${mode.glow}` }}>
        <mode.icon size={24} style={{ color: mode.color }} />
      </div>
      <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--dash-text)", marginBottom: 4, fontFamily: "'Orbitron',monospace" }}>{mode.label} Mode</h1>
      <p style={{ fontSize: 12, color: "var(--dash-text-muted)", marginBottom: 20 }}>{mode.hint} · {mode.placeholder}</p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, maxWidth: 460, width: "100%" }}>
        {items.map((s, i) => (
          <button key={i} onClick={() => s.orch ? onOrch(s.text) : onSend(s.text)}
            style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: 10, borderRadius: 10, background: "var(--dash-surface)", border: `1px solid ${s.orch ? "#eab30830" : "var(--dash-border-subtle)"}`, cursor: "pointer", textAlign: "left", color: "var(--dash-text-secondary)", fontSize: 11, lineHeight: 1.4, transition: "all 150ms" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--dash-surface-hover)"; e.currentTarget.style.borderColor = mode.color + "30"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "var(--dash-surface)"; e.currentTarget.style.borderColor = s.orch ? "#eab30830" : "var(--dash-border-subtle)"; }}
          >
            <span style={{ fontSize: 16 }}>{s.icon}</span>
            <span>{s.text}{s.orch && <span style={{ fontSize: 9, color: "#eab308", marginLeft: 4 }}>⚡ ORCH</span>}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default ChatPage;
