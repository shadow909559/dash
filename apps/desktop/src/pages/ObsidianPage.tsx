import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import {
  BookOpen,
  Search,
  Trash2,
  RefreshCw,
  FileText,
  ChevronRight,
  Plus,
  Database,
  BookMarked,
} from "lucide-react";
import {
  PageShell,
  PageHeader,
  EmptyState,
  GlassCard,
  TabBar,
  SectionTitle,
  StatusIndicator,
} from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface VaultNote {
  path: string;
  name: string;
  folder: string;
  size: number;
  modified: number;
}

interface NoteContent {
  path: string;
  content: string;
  frontmatter: Record<string, string>;
  size: number;
}

interface VaultHealth {
  healthy: boolean;
  mode: string;
  vault_path: string;
  note_count: number;
}

export const ObsidianPage: React.FC = () => {
  const [notes, setNotes] = useState<VaultNote[]>([]);
  const [selectedNote, setSelectedNote] = useState<NoteContent | null>(null);
  const [health, setHealth] = useState<VaultHealth | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<VaultNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"browse" | "search" | "create">(
    "browse"
  );
  const [createPath, setCreatePath] = useState("");
  const [createContent, setCreateContent] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const res = await authFetch(`${API}/obsidian/health`);
      setHealth(await res.json());
    } catch (e: any) {
      setError(`Cannot reach Obsidian backend: ${e.message}`);
    }
  }, []);

  const loadNotes = useCallback(async () => {
    try {
      setLoading(true);
      const res = await authFetch(`${API}/obsidian/list`);
      const data = await res.json();
      setNotes(data.notes || []);
    } catch (e: any) {
      setError(`Failed to load notes: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const searchNotes = useCallback(async () => {
    if (!searchQuery.trim()) return;
    try {
      setLoading(true);
      const res = await authFetch(`${API}/obsidian/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery }),
      });
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (e: any) {
      setError(`Search failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  const readNote = useCallback(async (path: string) => {
    try {
      const res = await authFetch(
        `${API}/obsidian/read?path=${encodeURIComponent(path)}`
      );
      setSelectedNote(await res.json());
    } catch (e: any) {
      setError(`Failed to read note: ${e.message}`);
    }
  }, []);

  const createNote = useCallback(async () => {
    if (!createPath.trim()) return;
    try {
      const res = await authFetch(`${API}/obsidian/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: createPath, content: createContent }),
      });
      if (res.ok) {
        setStatusMessage(`Created: ${createPath}`);
        setCreatePath("");
        setCreateContent("");
        loadNotes();
        setTimeout(() => setStatusMessage(null), 3000);
      }
    } catch (e: any) {
      setError(`Failed to create note: ${e.message}`);
    }
  }, [createPath, createContent, loadNotes]);

  const deleteNote = useCallback(
    async (path: string) => {
      try {
        const res = await authFetch(
          `${API}/obsidian/delete?path=${encodeURIComponent(path)}`,
          { method: "DELETE" }
        );
        if (res.ok) {
          setStatusMessage(`Deleted: ${path}`);
          setSelectedNote(null);
          loadNotes();
          setTimeout(() => setStatusMessage(null), 3000);
        }
      } catch (e: any) {
        setError(`Failed to delete note: ${e.message}`);
      }
    },
    [loadNotes]
  );

  useEffect(() => {
    checkHealth();
    loadNotes();
  }, [checkHealth, loadNotes]);

  const displayItems = activeTab === "search" ? searchResults : notes;

  return (
    <PageShell glowColor="rgba(159, 122, 250, 0.05)">
      <PageHeader
        icon={<BookOpen size={22} color="var(--dash-accent-secondary)" />}
        iconColor="var(--dash-accent-secondary)"
        iconBg="rgba(159, 122, 250, 0.12)"
        title="Obsidian Vault"
        subtitle={
          health
            ? health.healthy
              ? `${health.note_count} notes \u2014 ${health.vault_path}`
              : "Vault unavailable"
            : "Checking vault status..."
        }
        badge={
          <StatusIndicator
            status={health?.healthy ? "online" : "offline"}
            label={health?.healthy ? "Connected" : "Offline"}
          />
        }
        actions={
          <button
            onClick={() => {
              checkHealth();
              loadNotes();
            }}
            className="dash-btn-ghost"
          >
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content" style={{ padding: 0 }}>
        {/* Status/Error messages */}
        <div style={{ padding: "0 28px" }}>
          {statusMessage && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: "var(--dash-radius-md)",
                backgroundColor: "rgba(34,197,94,0.1)",
                border: "1px solid rgba(34,197,94,0.3)",
                color: "var(--dash-success)",
                fontSize: 12,
                marginBottom: 12,
              }}
            >
              {statusMessage}
            </div>
          )}
          {error && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: "var(--dash-radius-md)",
                backgroundColor: "rgba(239,68,68,0.1)",
                border: "1px solid rgba(239,68,68,0.3)",
                color: "var(--dash-danger)",
                fontSize: 12,
                marginBottom: 12,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              {error}
              <button
                onClick={() => setError(null)}
                className="dash-btn-ghost"
                style={{ padding: "2px 6px" }}
              >
                <span style={{ fontSize: 14 }}>\u2715</span>
              </button>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div style={{ padding: "0 28px", marginBottom: 16 }}>
          <TabBar
            tabs={[
              { id: "browse", label: "Browse", icon: <BookMarked size={12} /> },
              { id: "search", label: "Search", icon: <Search size={12} /> },
              { id: "create", label: "Create", icon: <Plus size={12} /> },
            ]}
            activeTab={activeTab}
            onTabChange={(id) =>
              setActiveTab(id as "browse" | "search" | "create")
            }
          />
        </div>

        {/* Search bar */}
        {activeTab === "search" && (
          <div style={{ padding: "0 28px", marginBottom: 16 }}>
            <GlassCard padding={14}>
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                }}
              >
                <Search
                  size={16}
                  style={{
                    color: "var(--dash-text-muted)",
                    flexShrink: 0,
                  }}
                />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && searchNotes()}
                  placeholder="Search vault notes..."
                  className="dash-input-ultron"
                  style={{ flex: 1 }}
                />
                <button onClick={searchNotes} className="dash-btn-primary">
                  Search
                </button>
              </div>
            </GlassCard>
          </div>
        )}

        {/* Content */}
        <div
          style={{
            display: "flex",
            gap: 16,
            minHeight: 400,
            padding: "0 28px 28px",
          }}
        >
          {/* Notes list */}
          <div
            className="dash-card"
            style={{
              width: 320,
              overflow: "auto",
              padding: 0,
              flexShrink: 0,
              backgroundImage: "var(--dash-gradient-surface)",
            }}
          >
            {loading ? (
              <div
                style={{
                  padding: 24,
                  textAlign: "center",
                  color: "var(--dash-text-muted)",
                  fontSize: 12,
                }}
              >
                <RefreshCw
                  size={16}
                  className="animate-rotate"
                  style={{ display: "inline", marginRight: 8 }}
                />
                Loading notes...
              </div>
            ) : displayItems.length === 0 ? (
              <div
                style={{
                  padding: 24,
                  textAlign: "center",
                  color: "var(--dash-text-muted)",
                  fontSize: 12,
                }}
              >
                No notes found
              </div>
            ) : (
              displayItems.map((note) => (
                <div
                  key={note.path}
                  onClick={() => readNote(note.path)}
                  style={{
                    padding: "10px 14px",
                    borderBottom: "1px solid var(--dash-border)",
                    cursor: "pointer",
                    background:
                      selectedNote?.path === note.path
                        ? "var(--dash-accent-glow)"
                        : "transparent",
                    transition: "background 0.15s",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <FileText
                    size={14}
                    style={{
                      color: "var(--dash-text-muted)",
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        color: "var(--dash-text)",
                        fontWeight: 500,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {note.name}
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: "var(--dash-text-muted)",
                        fontFamily: "'JetBrains Mono', monospace",
                        marginTop: 2,
                      }}
                    >
                      {note.folder}
                    </div>
                  </div>
                  <ChevronRight
                    size={12}
                    style={{
                      color: "var(--dash-text-muted)",
                      flexShrink: 0,
                    }}
                  />
                </div>
              ))
            )}
          </div>

          {/* Note viewer / Create form */}
          <div
            className="dash-card"
            style={{
              flex: 1,
              overflow: "auto",
              backgroundImage: "var(--dash-gradient-surface)",
            }}
          >
            {activeTab === "create" ? (
              <div
                style={{
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  height: "100%",
                }}
              >
                <h3
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "var(--dash-text)",
                    margin: 0,
                  }}
                >
                  Create New Note
                </h3>
                <input
                  value={createPath}
                  onChange={(e) => setCreatePath(e.target.value)}
                  placeholder="path/to/note.md"
                  className="dash-input-ultron"
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                />
                <textarea
                  value={createContent}
                  onChange={(e) => setCreateContent(e.target.value)}
                  placeholder="# Note Title\n\nWrite your content here..."
                  style={{
                    flex: 1,
                    minHeight: 250,
                    padding: 14,
                    borderRadius: "var(--dash-radius-md)",
                    border: "1px solid var(--dash-border)",
                    background: "var(--dash-bg)",
                    color: "var(--dash-text)",
                    fontSize: 13,
                    fontFamily: "'JetBrains Mono', monospace",
                    resize: "vertical",
                    outline: "none",
                  }}
                />
                <button
                  onClick={createNote}
                  className="dash-btn-primary"
                  style={{ alignSelf: "flex-end" }}
                >
                  <Plus size={12} /> Create Note
                </button>
              </div>
            ) : selectedNote ? (
              <div style={{ padding: 20 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 14,
                  }}
                >
                  <div>
                    <h3
                      style={{
                        margin: 0,
                        color: "var(--dash-text)",
                        fontSize: 15,
                        fontWeight: 600,
                      }}
                    >
                      {selectedNote.path}
                    </h3>
                    {Object.keys(selectedNote.frontmatter).length > 0 && (
                      <div
                        style={{
                          fontSize: 10,
                          color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace",
                          marginTop: 4,
                        }}
                      >
                        {Object.entries(selectedNote.frontmatter)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(" \u00b7 ")}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => deleteNote(selectedNote.path)}
                    className="dash-btn-ghost"
                    style={{
                      border: "1px solid rgba(239,68,68,0.3)",
                      background: "rgba(239,68,68,0.1)",
                      color: "var(--dash-danger)",
                    }}
                  >
                    <Trash2 size={12} /> Delete
                  </button>
                </div>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: "var(--dash-text-secondary)",
                    margin: 0,
                    padding: 16,
                    background: "var(--dash-bg)",
                    borderRadius: "var(--dash-radius-md)",
                    border: "1px solid var(--dash-border)",
                  }}
                >
                  {selectedNote.content}
                </pre>
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  color: "var(--dash-text-muted)",
                  fontSize: 13,
                }}
              >
                Select a note to read
              </div>
            )}
          </div>
        </div>
      </div>
    </PageShell>
  );
};

export default ObsidianPage;
