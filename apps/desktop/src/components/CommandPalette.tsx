import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  Home,
  MessageSquare,
  Mic,
  Brain,
  BookOpen,
  FolderKanban,
  Code2,
  Compass,
  Globe,
  Monitor,
  Smartphone,
  Zap,
  CalendarDays,
  Bot,
  Bell,
  CheckSquare,
  Puzzle,
  BarChart3,
  Settings,
  Activity,
  X,
  ArrowRight,
  Command,
} from "lucide-react";

interface PaletteItem {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
  path?: string;
  action?: () => void;
  category: string;
  keywords: string[];
}

const NAV_ITEMS: PaletteItem[] = [
  { id: "home", label: "Home", description: "Dashboard overview with Orb", icon: Home, path: "/", category: "Navigation", keywords: ["dashboard", "orb", "main", "home"] },
  { id: "chat", label: "Chat", description: "Message DASH with AI", icon: MessageSquare, path: "/chat", category: "Navigation", keywords: ["message", "talk", "ask", "ai", "llm"] },
  { id: "voice", label: "Voice", description: "Voice input and TTS output", icon: Mic, path: "/voice", category: "Navigation", keywords: ["microphone", "speech", "stt", "tts", "speak", "listen"] },
  { id: "memory", label: "Memory", description: "Long-term memory management", icon: Brain, path: "/memory", category: "Navigation", keywords: ["recall", "remember", "episodic", "semantic"] },
  { id: "knowledge", label: "Knowledge", description: "Indexed knowledge base", icon: BookOpen, path: "/knowledge", category: "Navigation", keywords: ["docs", "vector", "embeddings", "search"] },
  { id: "obsidian", label: "Obsidian", description: "Vault note integration", icon: BookOpen, path: "/obsidian", category: "Navigation", keywords: ["notes", "vault", "markdown"] },
  { id: "projects", label: "Projects", description: "Workspace repositories", icon: FolderKanban, path: "/projects", category: "Navigation", keywords: ["repos", "workspace", "code", "project"] },
  { id: "coding", label: "Coding", description: "Code generation and debugging", icon: Code2, path: "/coding", category: "Navigation", keywords: ["code", "debug", "generate", "python", "typescript"] },
  { id: "research", label: "Research", description: "Deep-web research and reports", icon: Compass, path: "/research", category: "Navigation", keywords: ["search", "web", "report", "analysis"] },
  { id: "browser", label: "Browser", description: "Headless web automation", icon: Globe, path: "/browser", category: "Navigation", keywords: ["scrape", "web", "url", "navigate"] },
  { id: "desktop", label: "Desktop Control", description: "Mouse, keyboard, windows, power", icon: Monitor, path: "/desktop", category: "Navigation", keywords: ["mouse", "keyboard", "volume", "brightness", "screenshot", "power", "lock", "shutdown"] },
  { id: "phone", label: "Phone Link", description: "Mobile device sync", icon: Smartphone, path: "/phone", category: "Navigation", keywords: ["android", "companion", "device", "mobile"] },
  { id: "automation", label: "Automation", description: "Event-driven workflows", icon: Zap, path: "/automation", category: "Navigation", keywords: ["rules", "trigger", "workflow", "schedule"] },
  { id: "planner", label: "Planner", description: "Multi-step goal execution", icon: CalendarDays, path: "/planner", category: "Navigation", keywords: ["plan", "goal", "task", "decompose", "execute"] },
  { id: "agents", label: "Agents", description: "Multi-agent orchestration", icon: Bot, path: "/agents", category: "Navigation", keywords: ["sub-agent", "delegation", "pool", "orchestrator"] },
  { id: "system", label: "System Monitor", description: "Real-time system health", icon: Activity, path: "/system-monitor", category: "Navigation", keywords: ["cpu", "ram", "gpu", "disk", "health", "status", "uptime"] },
  { id: "notifications", label: "Notifications", description: "System alerts and events", icon: Bell, path: "/notifications", category: "Navigation", keywords: ["alerts", "messages", "unread"] },
  { id: "approvals", label: "Approvals", description: "Security approval queue", icon: CheckSquare, path: "/approvals", category: "Navigation", keywords: ["approve", "deny", "security", "review"] },
  { id: "plugins", label: "Plugins", description: "Built-in modules and extensions", icon: Puzzle, path: "/plugins", category: "Navigation", keywords: ["extensions", "modules", "integrations"] },
  { id: "analytics", label: "Analytics", description: "System metrics and telemetry", icon: BarChart3, path: "/analytics", category: "Navigation", keywords: ["metrics", "charts", "performance", "telemetry"] },
  { id: "settings", label: "Settings", description: "Connection, AI, appearance", icon: Settings, path: "/settings", category: "Navigation", keywords: ["config", "theme", "provider", "api", "connection"] },
];

/** Match score: lower = better. 0 = exact match. */
function matchScore(query: string, item: PaletteItem): number {
  if (!query) return 0;
  const q = query.toLowerCase();

  // Exact label match
  if (item.label.toLowerCase() === q) return 0;

  // Label starts with query
  if (item.label.toLowerCase().startsWith(q)) return 1;

  // Label contains query
  if (item.label.toLowerCase().includes(q)) return 2;

  // Description contains query
  if (item.description.toLowerCase().includes(q)) return 3;

  // Keyword match
  for (const kw of item.keywords) {
    if (kw === q) return 4;
    if (kw.startsWith(q)) return 5;
    if (kw.includes(q)) return 6;
  }

  return -1; // no match
}

interface CommandPaletteProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function CommandPalette({ isOpen: controlledIsOpen, onClose }: CommandPaletteProps = {}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const isOpen = controlledIsOpen !== undefined ? controlledIsOpen : internalOpen;
  const setIsOpen = (v: boolean | ((prev: boolean) => boolean)) => {
    if (onClose && !v) onClose();
    if (controlledIsOpen === undefined) setInternalOpen(v);
  };
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [isOpen]);

  // Filtered + scored results
  const results = useMemo(() => {
    if (!query.trim()) return NAV_ITEMS.slice(0, 12); // show popular items

    return NAV_ITEMS
      .map((item) => ({ item, score: matchScore(query, item) }))
      .filter((r) => r.score >= 0)
      .sort((a, b) => a.score - b.score)
      .slice(0, 12)
      .map((r) => r.item);
  }, [query]);

  // Keep selected index in bounds
  useEffect(() => {
    if (selectedIndex >= results.length) {
      setSelectedIndex(Math.max(0, results.length - 1));
    }
  }, [results.length, selectedIndex]);

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.children[selectedIndex] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  const executeItem = useCallback(
    (item: PaletteItem) => {
      if (item.action) {
        item.action();
      } else if (item.path) {
        navigate(item.path);
      }
      setIsOpen(false);
    },
    [navigate]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (results[selectedIndex]) executeItem(results[selectedIndex]);
    }
  };

  if (!isOpen) return null;

  // Group results by category
  const grouped: Record<string, PaletteItem[]> = {};
  for (const item of results) {
    if (!grouped[item.category]) grouped[item.category] = [];
    grouped[item.category].push(item);
  }

  let flatIndex = -1;

  return (
    <div
      role="dialog"
      aria-label="Command palette"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9000,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "15vh",
        background: "rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(8px)",
        animation: "fadeIn 0.12s ease",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) setIsOpen(false);
      }}
    >
      <div
        style={{
          width: "min(560px, 90vw)",
          maxHeight: "min(480px, 70vh)",
          background: "var(--dash-surface)",
          border: "1px solid var(--dash-border-accent)",
          borderRadius: "var(--dash-radius-lg)",
          boxShadow: "0 24px 80px rgba(0,0,0,0.5), 0 0 40px rgba(220,38,38,0.08)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Search input */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "14px 18px",
            borderBottom: "1px solid var(--dash-border)",
          }}
        >
          <Search size={16} style={{ color: "var(--dash-text-muted)", flexShrink: 0 }} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search pages, commands..."
            aria-label="Search pages"
            style={{
              flex: 1,
              background: "none",
              border: "none",
              /* a11y: removed outline:none — global :focus-visible handles focus */
              color: "var(--dash-text)",
              fontSize: 14,
              fontFamily: "Inter, sans-serif",
            }}
          />
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <kbd
              style={{
                fontSize: 10,
                padding: "2px 6px",
                borderRadius: "var(--dash-radius-xs)",
                background: "var(--dash-bg)",
                border: "1px solid var(--dash-border)",
                color: "var(--dash-text-muted)",
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              ESC
            </kbd>
          </div>
        </div>

        {/* Results list */}
        <div
          ref={listRef}
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "6px",
          }}
        >
          {results.length === 0 ? (
            <div
              style={{
                padding: "32px 18px",
                textAlign: "center",
                color: "var(--dash-text-muted)",
                fontSize: 13,
              }}
            >
              No results for "{query}"
            </div>
          ) : (
            Object.entries(grouped).map(([category, items]) => (
              <div key={category} style={{ marginBottom: 4 }}>
                {/* Category header */}
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: "var(--dash-text-muted)",
                    padding: "8px 12px 4px",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {category}
                </div>
                {items.map((item) => {
                  flatIndex++;
                  const isSelected = flatIndex === selectedIndex;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => executeItem(item)}
                      onMouseEnter={() => setSelectedIndex(flatIndex)}
                      role="option"
                      aria-selected={isSelected}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 12,
                        width: "100%",
                        padding: "10px 12px",
                        border: "none",
                        borderRadius: "var(--dash-radius-sm)",
                        background: isSelected ? "var(--ultron-surface)" : "transparent",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "background 0.1s",
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: "var(--dash-radius-sm)",
                          background: isSelected ? "var(--ultron-surface-hover)" : "var(--dash-bg)",
                          border: `1px solid ${isSelected ? "var(--ultron-border)" : "var(--dash-border-subtle)"}`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <Icon
                          size={15}
                          style={{
                            color: isSelected ? "var(--ultron-core-bright)" : "var(--dash-text-muted)",
                          }}
                        />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: isSelected ? 600 : 500,
                            color: isSelected ? "var(--dash-text)" : "var(--dash-text-secondary)",
                            marginBottom: 1,
                          }}
                        >
                          {item.label}
                        </div>
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--dash-text-muted)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {item.description}
                        </div>
                      </div>
                      {isSelected && (
                        <ArrowRight
                          size={14}
                          style={{ color: "var(--ultron-core-bright)", flexShrink: 0 }}
                        />
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer hints */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 16px",
            borderTop: "1px solid var(--dash-border)",
            background: "var(--dash-bg-subtle)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {[
              { keys: "↑↓", label: "Navigate" },
              { keys: "↵", label: "Open" },
              { keys: "ESC", label: "Close" },
            ].map(({ keys, label }) => (
              <div
                key={keys}
                style={{ display: "flex", alignItems: "center", gap: 4 }}
              >
                <kbd
                  style={{
                    fontSize: 10,
                    padding: "1px 5px",
                    borderRadius: 3,
                    background: "var(--dash-surface)",
                    border: "1px solid var(--dash-border)",
                    color: "var(--dash-text-muted)",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {keys}
                </kbd>
                <span
                  style={{
                    fontSize: 10,
                    color: "var(--dash-text-muted)",
                  }}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 10,
              color: "var(--dash-text-muted)",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            <Command size={10} />
            DASH
          </div>
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
