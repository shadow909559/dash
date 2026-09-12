import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { PageShell, PageHeader, GlassCard, SectionTitle } from "@/components/ultron";
import { BrainCircuit, RefreshCw, Layers, MessageSquare, Database, Cpu, Loader2 } from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface FineTuneStatus {
  level1_prompt?: { status?: string; modes?: string[]; custom_prompts?: number };
  level2_rag?: { status?: string; chunks?: number };
  level3_lora?: { status?: string; examples?: number; training_data?: boolean };
}

const MODES = ["general", "research", "coding", "automation", "planning"] as const;

export default function FineTuningPage() {
  const [status, setStatus] = useState<FineTuneStatus>({});
  const [loading, setLoading] = useState(true);
  const [selectedMode, setSelectedMode] = useState<string>("general");
  const [prompt, setPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API}/fine-tuning/status`);
      if (res?.ok) setStatus(await res.json());
    } catch {
      setStatus({});
    }
    setLoading(false);
  }, []);

  const loadPrompt = useCallback(async (mode: string) => {
    try {
      const res = await authFetch(`${API}/fine-tuning/prompt/${mode}`);
      if (res?.ok) {
        const data = await res.json();
        setPrompt(data.prompt || "");
      }
    } catch {
      setPrompt("");
    }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);
  useEffect(() => { loadPrompt(selectedMode); }, [selectedMode, loadPrompt]);

  const savePrompt = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await authFetch(`${API}/fine-tuning/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: selectedMode, prompt }),
      });
      setMessage(res?.ok ? "Prompt saved — new conversations use it immediately." : "Save failed.");
    } catch {
      setMessage("Save failed — is the backend running?");
    }
    setSaving(false);
  };

  const prepareTraining = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await authFetch(`${API}/fine-tuning/prepare-training`, { method: "POST" });
      const data = res?.ok ? await res.json() : null;
      setMessage(data?.message || (res?.ok ? "Training data prepared." : "Prepare failed."));
    } catch {
      setMessage("Prepare failed — is the backend running?");
    }
    setSaving(false);
  };

  const levels = [
    {
      icon: <MessageSquare size={15} />,
      name: "Level 1 — Prompt Engine",
      detail: `${status.level1_prompt?.modes?.length ?? 0} agent modes · ${status.level1_prompt?.custom_prompts ?? 0} custom prompts`,
      active: status.level1_prompt?.status === "active",
    },
    {
      icon: <Database size={15} />,
      name: "Level 2 — RAG Context",
      detail: `${status.level2_rag?.chunks ?? 0} indexed chunks`,
      active: status.level2_rag?.status === "initialized",
    },
    {
      icon: <Cpu size={15} />,
      name: "Level 3 — LoRA Training",
      detail: `${status.level3_lora?.examples ?? 0} examples · training data ${status.level3_lora?.training_data ? "exported" : "not exported"}`,
      active: status.level3_lora?.status === "ready",
    },
  ];

  return (
    <PageShell>
      <PageHeader
        icon={<BrainCircuit size={18} />}
        iconColor="var(--dash-accent-secondary)"
        title="Fine-Tuning"
        subtitle="Three-level personalization: prompt engine, RAG context, and LoRA training"
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={fetchStatus}
              aria-label="Refresh fine-tuning status"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text)", cursor: "pointer", fontSize: 12 }}
            >
              <RefreshCw size={13} /> Refresh
            </button>
            <button
              onClick={prepareTraining}
              disabled={saving}
              aria-label="Prepare LoRA training data"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-accent)", background: "var(--dash-accent-glow)", color: "var(--dash-accent)", cursor: "pointer", fontSize: 12, fontWeight: 600 }}
            >
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Layers size={13} />} Prepare training data
            </button>
          </div>
        }
      />
      <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 24 }}>
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 60 }}><Loader2 size={22} className="animate-spin" /></div>
        ) : (
          <>
            <section>
              <SectionTitle>Tuning levels</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
                {levels.map((l) => (
                  <GlassCard key={l.name} glow={l.active}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <span style={{ color: l.active ? "var(--dash-success)" : "var(--dash-text-muted)", display: "flex" }}>{l.icon}</span>
                      <strong style={{ fontSize: 13 }}>{l.name}</strong>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>{l.detail}</div>
                    <div style={{ marginTop: 10, fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: l.active ? "var(--dash-success)" : "var(--dash-warning)" }}>
                      {l.active ? "● ACTIVE" : "○ IDLE"}
                    </div>
                  </GlassCard>
                ))}
              </div>
            </section>

            <section>
              <SectionTitle>Agent mode prompts</SectionTitle>
              <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
                {MODES.map((m) => (
                  <button
                    key={m}
                    onClick={() => setSelectedMode(m)}
                    aria-pressed={selectedMode === m}
                    style={{
                      padding: "6px 14px", fontSize: 12, borderRadius: "var(--dash-radius-sm)", cursor: "pointer",
                      border: "1px solid", borderColor: selectedMode === m ? "var(--dash-accent)" : "var(--dash-border)",
                      background: selectedMode === m ? "var(--dash-accent-glow)" : "transparent",
                      color: selectedMode === m ? "var(--dash-accent)" : "var(--dash-text-muted)",
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <GlassCard>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={6}
                  aria-label={`System prompt for ${selectedMode} mode`}
                  placeholder={`System prompt used whenever DASH acts as ${selectedMode}…`}
                  style={{ width: "100%", padding: 12, borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-bg)", color: "var(--dash-text)", fontSize: 12, fontFamily: "'JetBrains Mono', monospace", resize: "vertical", outline: "none" }}
                />
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10 }}>
                  <button
                    onClick={savePrompt}
                    disabled={saving}
                    style={{ padding: "8px 18px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-accent)", background: "var(--dash-accent-glow)", color: "var(--dash-accent)", cursor: "pointer", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}
                  >
                    {saving ? <Loader2 size={12} className="animate-spin" /> : null} Save prompt
                  </button>
                  {message && <span style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>{message}</span>}
                </div>
              </GlassCard>
            </section>
          </>
        )}
      </div>
    </PageShell>
  );
}
