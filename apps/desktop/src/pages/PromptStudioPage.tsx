import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { FileText, Plus, Copy, Trash2, Play, BarChart3, Tag } from "lucide-react";

export default function PromptStudioPage() {
  const { addNotification } = useNotifier();
  const [prompts, setPrompts] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newCategory, setNewCategory] = useState("custom");

  const fetch = useCallback(async () => {
    try {
      const [pRes, tRes] = await Promise.all([authFetch("/features/prompts"), authFetch("/features/prompts/templates")]);
      if (pRes?.ok) setPrompts((await pRes.json()).prompts || []);
      if (tRes?.ok) setTemplates((await tRes.json()).templates || []);
    } catch {
      setTemplates([
        { id: "tpl_summarize", name: "Summarize", template: "Summarize the following text concisely:\n\n{text}", category: "content" },
        { id: "tpl_code_review", name: "Code Review", template: "Review this code for bugs, performance, and style:\n\n```{language}\n{code}\n```", category: "code" },
        { id: "tpl_explain", name: "Explain", template: "Explain the following concept clearly:\n\n{concept}", category: "education" },
        { id: "tpl_brainstorm", name: "Brainstorm", template: "Generate 10 creative ideas for: {topic}", category: "creative" },
        { id: "tpl_email", name: "Email Draft", template: "Write a professional email to {recipient} about {topic}.", category: "communication" },
        { id: "tpl_bug_fix", name: "Bug Fix", template: "Fix this error:\n\n{error}\n\nIn:\n```{language}\n{code}\n```", category: "code" },
      ]);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const createPrompt = async () => {
    if (!newName.trim() || !newContent.trim()) return;
    try { await authFetch("/features/prompts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: newName, content: newContent, category: newCategory }) }); } catch {}
    addNotification({ type: "success", title: "Created", message: `Prompt "${newName}" created` });
    setShowCreate(false); setNewName(""); setNewContent(""); fetch();
  };

  return (
    <PageShell>
      <PageHeader icon={<FileText size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Prompt Studio" subtitle={`${prompts.length} prompts, ${templates.length} templates`} actions={<button onClick={() => setShowCreate(true)} style={{ background: "var(--accent, #22c55e)", border: "none", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "#000", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}><Plus size={12} /> New Prompt</button>} />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Templates */}
        <GlassCard>
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Templates ({templates.length})</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {templates.map(t => (
              <div key={t.id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", cursor: "pointer" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{t.name}</span>
                  <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: "rgba(34,197,94,0.15)", color: "var(--accent, #22c55e)" }}>{t.category}</span>
                </div>
                <p style={{ fontSize: 11, color: "var(--text-muted, #666)", margin: "3px 0 0", fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.template}</p>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* My Prompts / Detail */}
        <GlassCard>
          {selected ? (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <h3 style={{ margin: 0, fontSize: 15 }}>{selected.name}</h3>
                <div style={{ display: "flex", gap: 4 }}>
                  <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 4, padding: "4px 8px", cursor: "pointer", color: "var(--text-muted, #666)" }}><Copy size={12} /></button>
                  <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 4, padding: "4px 8px", cursor: "pointer", color: "#ef4444" }}><Trash2 size={12} /></button>
                </div>
              </div>
              <pre style={{ padding: 12, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 6, fontSize: 12, fontFamily: "monospace", lineHeight: 1.6, color: "var(--text-secondary, #aaa)", whiteSpace: "pre-wrap", marginBottom: 12 }}>{selected.content || selected.template}</pre>
              <div style={{ display: "flex", gap: 6 }}>
                <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "var(--text)", fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}><Play size={12} /> Test</button>
                <button style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "var(--text)", fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}><BarChart3 size={12} /> A/B Test</button>
              </div>
            </div>
          ) : (
            <div>
              <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>My Prompts ({prompts.length})</h4>
              {prompts.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--text-muted, #666)", textAlign: "center", padding: 20 }}>No custom prompts yet</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {prompts.map(p => (
                    <div key={p.id} onClick={() => setSelected(p)} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 13 }}>{p.name}</span>
                      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                        <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: "rgba(34,197,94,0.15)", color: "var(--accent, #22c55e)" }}>{p.category}</span>
                        <span style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>v{p.version || 1}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </GlassCard>
      </div>

      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
          <GlassCard style={{ maxWidth: 500, width: "100%" }}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15 }}>New Prompt</h3>
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Prompt name" style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 13, marginBottom: 10 }} />
            <select value={newCategory} onChange={e => setNewCategory(e.target.value)} style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 12, marginBottom: 10 }}>
              {["custom", "content", "code", "education", "creative", "communication", "analytics"].map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <textarea value={newContent} onChange={e => setNewContent(e.target.value)} rows={8} placeholder="Prompt content..." style={{ width: "100%", padding: 10, background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 12, fontFamily: "monospace", resize: "vertical", marginBottom: 14 }} />
            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
              <button onClick={() => setShowCreate(false)} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", color: "var(--text)", cursor: "pointer", fontSize: 12 }}>Cancel</button>
              <button onClick={createPrompt} style={{ background: "var(--accent, #22c55e)", border: "none", borderRadius: 6, padding: "6px 12px", color: "#000", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>Create</button>
            </div>
          </GlassCard>
        </div>
      )}
    </PageShell>
  );
}
