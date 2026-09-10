import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { PageShell, PageHeader, GlassCard, EmptyState, SectionTitle } from "@/components/ultron";
import {
  KeyRound,
  Plus,
  Search,
  RefreshCw,
  Copy,
  Eye,
  EyeOff,
  Star,
  Trash2,
  Loader2,
  Dices,
  Lock,
} from "lucide-react";

interface VaultEntry {
  id: string;
  category: string;
  title: string;
  fields: Record<string, string>;
  notes: string;
  tags: string[];
  favorite: boolean;
  created_at: string;
  updated_at: string;
  access_count?: number;
}

const CATEGORY_OPTIONS = ["login", "secure_note", "credit_card", "identity", "api_key", "ssh_key"];

const emptyForm = { title: "", username: "", password: "", url: "", notes: "", category: "login" };

export default function PasswordManagerPage() {
  const [entries, setEntries] = useState<VaultEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [showAdd, setShowAdd] = useState(false);
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [newEntry, setNewEntry] = useState({ ...emptyForm });
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");

  const flash = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2200);
  }, []);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await authFetch("/features/vault/entries");
      if (r?.ok) {
        const d = await r.json();
        setEntries(d.entries || []);
      } else {
        setError("Vault unreachable — is the backend running?");
      }
    } catch {
      setError("Vault unreachable — is the backend running?");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  const addEntry = async () => {
    if (!newEntry.title.trim() || !newEntry.password.trim()) {
      flash("Title and password are required");
      return;
    }
    setBusy(true);
    try {
      const fields: Record<string, string> = {};
      if (newEntry.username) fields.username = newEntry.username;
      if (newEntry.password) fields.password = newEntry.password;
      if (newEntry.url) fields.url = newEntry.url;
      const r = await authFetch("/features/vault/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: CATEGORY_OPTIONS.includes(newEntry.category) ? newEntry.category : "login",
          title: newEntry.title.trim(),
          fields,
          notes: newEntry.notes,
        }),
      });
      if (r?.ok) {
        setNewEntry({ ...emptyForm });
        setShowAdd(false);
        flash("Entry saved (encrypted)");
        loadEntries();
      } else {
        flash("Save failed");
      }
    } catch {
      flash("Save failed");
    }
    setBusy(false);
  };

  const deleteEntry = async (id: string) => {
    try {
      await authFetch(`/features/vault/entries/${id}`, { method: "DELETE" });
      flash("Entry deleted");
      loadEntries();
    } catch {
      flash("Delete failed");
    }
  };

  const toggleFavorite = async (entry: VaultEntry) => {
    try {
      await authFetch(`/features/vault/entries/${entry.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ favorite: !entry.favorite }),
      });
      loadEntries();
    } catch {
      /* ignore */
    }
  };

  const revealPassword = async (id: string) => {
    const next = !showPasswords[id];
    setShowPasswords((prev) => ({ ...prev, [id]: next }));
    if (next && !entries.find((e) => e.id === id)?.fields?.password) {
      // list responses include full fields; nothing extra to fetch
    }
  };

  const copyPassword = (entry: VaultEntry) => {
    const pw = entry.fields?.password;
    if (!pw) return;
    navigator.clipboard.writeText(pw);
    flash("Password copied to clipboard");
  };

  const generatePassword = async () => {
    try {
      const r = await authFetch("/features/vault/generate-password?length=20");
      if (r?.ok) {
        const d = await r.json();
        setNewEntry((p) => ({ ...p, password: d.password || "" }));
      }
    } catch {
      /* ignore */
    }
  };

  const filtered = entries.filter((e) => {
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      e.title.toLowerCase().includes(q) ||
      (e.fields?.username || "").toLowerCase().includes(q) ||
      (e.notes || "").toLowerCase().includes(q);
    const matchCat = category === "all" || e.category === category;
    return matchSearch && matchCat;
  });

  const categories = ["all", ...new Set(entries.map((e) => e.category))];

  const inputStyle: React.CSSProperties = {
    padding: 8,
    background: "var(--dash-bg)",
    border: "1px solid var(--dash-border)",
    borderRadius: "var(--dash-radius-sm)",
    color: "var(--dash-text)",
    fontSize: 13,
    width: "100%",
  };

  return (
    <PageShell>
      <PageHeader
        icon={<KeyRound size={22} />}
        iconColor="var(--dash-accent)"
        iconBg="rgba(99,102,241,0.15)"
        title="Password Manager"
        subtitle="AES-256-GCM encrypted vault for credentials, keys, and identities"
        badge={
          <span className="dash-badge-glow" style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 999, background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.3)", color: "#10b981", fontSize: 11 }}>
            <Lock size={10} /> Encrypted at rest
          </span>
        }
        actions={
          <button onClick={loadEntries} className="dash-btn-ghost" title="Refresh" aria-label="Refresh vault">
            <RefreshCw size={14} className={loading ? "animate-rotate" : undefined} />
          </button>
        }
      />

      <div className="dash-page-content">
        {error && (
          <div role="alert" style={{ padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, marginBottom: 16, fontSize: 12, color: "#ef4444" }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200, position: "relative" }}>
            <Search size={14} style={{ position: "absolute", left: 10, top: 10, color: "var(--dash-text-muted)", pointerEvents: "none" }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search vault…"
              aria-label="Search vault entries"
              style={{ ...inputStyle, paddingLeft: 30 }}
            />
          </div>
          <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Filter by category" style={{ ...inputStyle, width: "auto", cursor: "pointer" }}>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowAdd(!showAdd)}
            aria-expanded={showAdd}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: "var(--dash-radius-sm)", border: "1px solid rgba(99,102,241,0.35)", background: "rgba(99,102,241,0.15)", color: "#a5b4fc", fontSize: 12, fontWeight: 600, cursor: "pointer", minHeight: 24 }}
          >
            <Plus size={14} /> Add Entry
          </button>
        </div>

        {showAdd && (
          <GlassCard padding={18} style={{ marginBottom: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <input placeholder="Title *" value={newEntry.title} onChange={(e) => setNewEntry((p) => ({ ...p, title: e.target.value }))} aria-label="Entry title" style={inputStyle} />
              <select value={newEntry.category} onChange={(e) => setNewEntry((p) => ({ ...p, category: e.target.value }))} aria-label="Entry category" style={{ ...inputStyle, cursor: "pointer" }}>
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <input placeholder="Username" value={newEntry.username} onChange={(e) => setNewEntry((p) => ({ ...p, username: e.target.value }))} aria-label="Username" style={inputStyle} />
              <div style={{ display: "flex", gap: 8 }}>
                <input placeholder="Password *" type="password" value={newEntry.password} onChange={(e) => setNewEntry((p) => ({ ...p, password: e.target.value }))} aria-label="Password" style={{ ...inputStyle, flex: 1 }} />
                <button onClick={generatePassword} className="dash-btn-ghost" title="Generate strong password" aria-label="Generate strong password" style={{ minHeight: 24, minWidth: 24 }}>
                  <Dices size={15} />
                </button>
              </div>
              <input placeholder="URL" value={newEntry.url} onChange={(e) => setNewEntry((p) => ({ ...p, url: e.target.value }))} aria-label="URL" style={inputStyle} />
              <textarea placeholder="Notes" value={newEntry.notes} onChange={(e) => setNewEntry((p) => ({ ...p, notes: e.target.value }))} aria-label="Notes" style={{ ...inputStyle, minHeight: 60, resize: "vertical" }} />
            </div>
            <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
              <button onClick={addEntry} disabled={busy} style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: "var(--dash-radius-sm)", border: "none", background: "#10b981", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                {busy ? <Loader2 size={13} className="spin" /> : <Plus size={13} />} Save encrypted
              </button>
              <button onClick={() => setShowAdd(false)} className="dash-btn-ghost" style={{ padding: "8px 16px", fontSize: 12 }}>
                Cancel
              </button>
            </div>
          </GlassCard>
        )}

        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[1, 2, 3].map((i) => (
              <div key={i} style={{ height: 72, background: "var(--dash-bg)", borderRadius: "var(--dash-radius-md)", opacity: 0.5 }} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<KeyRound size={28} style={{ color: "var(--dash-text-muted)" }} />}
            title={entries.length === 0 ? "Vault is empty" : "No matches"}
            description={entries.length === 0 ? "Add your first credential — entries are encrypted with AES-256-GCM before touching disk." : "Try a different search or category."}
          />
        ) : (
          <div className="dash-stagger">
            <SectionTitle count={filtered.length}>Entries</SectionTitle>
            {filtered.map((entry) => (
              <GlassCard key={entry.id} padding={14} className="dash-card-glow">
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 38, height: 38, borderRadius: "var(--dash-radius-sm)", background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.25)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <KeyRound size={16} style={{ color: "#a5b4fc" }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>{entry.title}</span>
                      <span style={{ fontSize: 10, color: "var(--dash-text-muted)", border: "1px solid var(--dash-border)", borderRadius: 999, padding: "1px 7px" }}>
                        {entry.category}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--dash-text-muted)", marginTop: 3, display: "flex", alignItems: "center", gap: 8 }}>
                      {entry.fields?.username && <span>{entry.fields.username}</span>}
                      {entry.fields?.password && (
                        <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
                          {showPasswords[entry.id] ? entry.fields.password : "•".repeat(Math.min(12, entry.fields.password.length))}
                        </code>
                      )}
                    </div>
                  </div>
                  <button onClick={() => revealPassword(entry.id)} className="dash-btn-ghost" title={showPasswords[entry.id] ? "Hide password" : "Show password"} aria-label={showPasswords[entry.id] ? "Hide password" : "Show password"} style={{ minHeight: 24, minWidth: 24 }}>
                    {showPasswords[entry.id] ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                  <button onClick={() => copyPassword(entry)} className="dash-btn-ghost" title="Copy password" aria-label="Copy password" style={{ minHeight: 24, minWidth: 24 }}>
                    <Copy size={14} />
                  </button>
                  <button
                    onClick={() => toggleFavorite(entry)}
                    className="dash-btn-ghost"
                    title={entry.favorite ? "Unfavorite" : "Favorite"}
                    aria-label={entry.favorite ? "Remove from favorites" : "Add to favorites"}
                    style={{ minHeight: 24, minWidth: 24, color: entry.favorite ? "#f59e0b" : undefined }}
                  >
                    <Star size={14} fill={entry.favorite ? "#f59e0b" : "none"} />
                  </button>
                  <button onClick={() => deleteEntry(entry.id)} className="dash-btn-ghost" title="Delete entry" aria-label="Delete entry" style={{ minHeight: 24, minWidth: 24, color: "#ef4444" }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>

      {toast && (
        <div role="status" aria-live="polite" style={{ position: "fixed", top: 20, right: 20, background: "var(--dash-surface)", border: "1px solid var(--dash-border)", color: "var(--dash-text)", padding: "10px 16px", borderRadius: 10, zIndex: 9999, fontSize: 12, boxShadow: "0 4px 20px rgba(0,0,0,0.4)" }}>
          {toast}
        </div>
      )}
    </PageShell>
  );
}
