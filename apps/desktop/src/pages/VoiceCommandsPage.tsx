import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { Mic, MicOff, Play, Pause, Square, Volume2, Keyboard, Clock, Search } from "lucide-react";

export default function VoiceCommandsPage() {
  const { addNotification } = useNotifier();
  const [config, setConfig] = useState({ wake_words: ["hey dash", "dash"], language: "en", command_count: 0, listening: false });
  const [commands, setCommands] = useState<Record<string, { patterns: string[]; action: string; target: string }>>({});
  const [memos, setMemos] = useState<any[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingText, setRecordingText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const fetch = useCallback(async () => {
    try {
      const [cfgRes, cmdRes, memoRes] = await Promise.all([
        authFetch("/features/voice/config"),
        authFetch("/features/voice/commands"),
        authFetch("/features/voice/memos"),
      ]);
      if (cfgRes?.ok) setConfig(await cfgRes.json());
      if (cmdRes?.ok) setCommands((await cmdRes.json()).commands || {});
      if (memoRes?.ok) setMemos((await memoRes.json()).memos || []);
    } catch {
      setCommands({
        open_settings: { patterns: ["open settings", "show settings"], action: "navigate", target: "/settings" },
        new_chat: { patterns: ["new chat", "start conversation"], action: "chat", target: "new" },
        search_memory: { patterns: ["search memory", "find memory"], action: "memory", target: "search" },
        take_note: { patterns: ["take note", "remember this"], action: "memory", target: "create" },
        read_email: { patterns: ["read email", "check email"], action: "email", target: "inbox" },
        show_calendar: { patterns: ["show calendar", "today's schedule"], action: "calendar", target: "today" },
        set_reminder: { patterns: ["remind me", "set reminder"], action: "reminder", target: "create" },
        summarize: { patterns: ["summarize this", "tldr"], action: "ai", target: "summarize" },
      });
      setMemos([
        { id: "memo1", title: "Meeting Notes", transcript: "Discussed roadmap for Q3. Key decisions: focus on mobile app, add voice commands, improve memory.", duration_seconds: 120, created_at: new Date().toISOString() },
      ]);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const toggleRecording = () => {
    if (isRecording) {
      setIsRecording(false);
      if (recordingText.trim()) {
        authFetch("/features/voice/memos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "Voice Memo", transcript: recordingText, duration_seconds: 30 }) }).catch(() => {});
        addNotification({ type: "success", title: "Memo Saved", message: "Voice memo recorded" });
        setRecordingText("");
        fetch();
      }
    } else {
      setIsRecording(true);
      setRecordingText("");
      addNotification({ type: "info", title: "Recording", message: "Speak now..." });
    }
  };

  const filteredCommands = Object.entries(commands).filter(([id, cmd]) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return id.includes(q) || cmd.patterns.some(p => p.includes(q)) || cmd.action.includes(q);
  });

  return (
    <PageShell>
      <PageHeader icon={<Mic size={18} />} iconColor={isRecording ? "#ef4444" : "var(--accent, #22c55e)"} iconBg={isRecording ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)"} title="Voice Commands" subtitle={`${Object.keys(commands).length} commands registered`} />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Recording & Wake Word */}
        <GlassCard>
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Voice Input</h4>
          <div style={{ textAlign: "center", padding: 20 }}>
            <button onClick={toggleRecording} style={{ width: 80, height: 80, borderRadius: "50%", background: isRecording ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)", border: `3px solid ${isRecording ? "#ef4444" : "var(--accent, #22c55e)"}`, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 12px", transition: "all 0.2s" }}>
              {isRecording ? <Square size={24} style={{ color: "#ef4444" }} /> : <Mic size={24} style={{ color: "var(--accent, #22c55e)" }} />}
            </button>
            <p style={{ fontSize: 12, color: "var(--text-muted, #666)", margin: 0 }}>{isRecording ? "Recording... Click to stop" : "Click to start recording"}</p>
            {recordingText && <p style={{ fontSize: 12, color: "var(--text)", marginTop: 8, fontStyle: "italic" }}>"{recordingText}"</p>}
          </div>

          <div style={{ borderTop: "1px solid var(--border, #333)", paddingTop: 12 }}>
            <h4 style={{ fontSize: 12, color: "var(--text-muted, #666)", marginBottom: 8 }}>Wake Words</h4>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {config.wake_words.map(ww => (
                <span key={ww} style={{ padding: "4px 10px", borderRadius: 12, background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", fontSize: 11, fontFamily: "monospace" }}>"{ww}"</span>
              ))}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted, #666)", marginTop: 6 }}>Language: {config.language} • {config.listening ? "Listening" : "Idle"}</div>
          </div>
        </GlassCard>

        {/* Command List */}
        <GlassCard style={{ overflow: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h4 style={{ fontSize: 13, color: "var(--text-muted, #666)", margin: 0, textTransform: "uppercase", letterSpacing: "0.08em" }}>Commands ({filteredCommands.length})</h4>
            <div style={{ position: "relative" }}>
              <Search size={12} style={{ position: "absolute", left: 8, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted, #666)" }} />
              <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Filter..." style={{ padding: "4px 8px 4px 24px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 11, width: 120 }} />
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {filteredCommands.map(([id, cmd]) => (
              <div key={id} style={{ padding: "6px 8px", borderRadius: 4, background: "var(--bg-secondary, #1a1a2e)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 500, fontFamily: "monospace" }}>{id.replace(/_/g, " ")}</div>
                  <div style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>"{cmd.patterns[0]}"</div>
                </div>
                <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: "rgba(34,197,94,0.15)", color: "var(--accent, #22c55e)", textTransform: "uppercase" }}>{cmd.action}</span>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Voice Memos */}
        <GlassCard style={{ gridColumn: "1 / -1" }}>
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Voice Memos ({memos.length})</h4>
          {memos.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--text-muted, #666)", textAlign: "center", padding: 20 }}>No voice memos yet. Record one above.</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 8 }}>
              {memos.map(m => (
                <div key={m.id} style={{ padding: "10px 12px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)" }}>
                  <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{m.title}</div>
                  <div style={{ fontSize: 11, color: "var(--text-secondary, #aaa)", marginBottom: 6, lineHeight: 1.5 }}>{m.transcript?.slice(0, 150)}{m.transcript?.length > 150 ? "..." : ""}</div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-muted, #666)" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 3 }}><Clock size={10} /> {Math.floor((m.duration_seconds || 0) / 60)}:{String((m.duration_seconds || 0) % 60).padStart(2, "0")}</span>
                    <span>{new Date(m.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>
    </PageShell>
  );
}
