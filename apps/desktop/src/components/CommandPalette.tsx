import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";

interface Command {
  id: string;
  label: string;
  description: string;
  category: string;
  action: () => void;
  shortcut?: string;
  icon?: string;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

const DEFAULT_COMMANDS: Command[] = [
  { id: "goto-dashboard", label: "Go to Dashboard", description: "Navigate to the dashboard", category: "navigation", action: () => {}, icon: "d", shortcut: "Ctrl+1" },
  { id: "goto-chat", label: "Go to Chat", description: "Open AI chat interface", category: "navigation", action: () => {}, icon: "c", shortcut: "Ctrl+2" },
  { id: "goto-memory", label: "Go to Memory", description: "View memory storage", category: "navigation", action: () => {}, icon: "m", shortcut: "Ctrl+3" },
  { id: "goto-projects", label: "Go to Projects", description: "Manage your projects", category: "navigation", action: () => {}, icon: "p", shortcut: "Ctrl+4" },
  { id: "goto-automation", label: "Go to Automation", description: "Configure automations", category: "navigation", action: () => {}, icon: "a", shortcut: "Ctrl+5" },
  { id: "goto-settings", label: "Go to Settings", description: "Application settings", category: "navigation", action: () => {}, icon: "s", shortcut: "Ctrl+6" },
  { id: "toggle-theme", label: "Toggle Theme", description: "Switch between light and dark mode", category: "actions", action: () => {}, icon: "t" },
  { id: "search-files", label: "Search Files", description: "Search files on the system", category: "actions", action: () => {}, icon: "f" },
  { id: "open-terminal", label: "Open Terminal", description: "Open system terminal", category: "actions", action: () => {}, icon: ">" },
  { id: "run-command", label: "Run Command", description: "Execute a system command", category: "actions", action: () => {}, icon: "!" },
  { id: "clear-memory", label: "Clear Memory", description: "Clear AI conversation memory", category: "actions", action: () => {}, icon: "x" },
];

export default function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const commands: Command[] = DEFAULT_COMMANDS.map((cmd) => {
    if (cmd.id.startsWith("goto-")) {
      const path = "/" + cmd.id.replace("goto-", "");
      return { ...cmd, action: () => { navigate(path); onClose(); } };
    }
    return cmd;
  });

  const filtered = query
    ? commands.filter(
        (c) =>
          c.label.toLowerCase().includes(query.toLowerCase()) ||
          c.description.toLowerCase().includes(query.toLowerCase()) ||
          c.category.toLowerCase().includes(query.toLowerCase())
      )
    : commands;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        filtered[selectedIndex].action();
        setQuery("");
        onClose();
        return;
      }
    },
    [isOpen, filtered, selectedIndex, onClose]
  );

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "15vh",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "rgba(0,0,0,0.5)",
          backdropFilter: "blur(4px)",
        }}
      />
      <div
        className="glass"
        onClick={(e) => e.stopPropagation()}
        style={{
          position: "relative",
          width: 560,
          maxHeight: 420,
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-glass)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 25px 50px rgba(0,0,0,0.3)",
        }}
      >
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-glass)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 16, opacity: 0.5 }}>{">"}</span>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              placeholder="Search commands, files, actions..."
              style={{
                flex: 1,
                background: "none",
                border: "none",
                outline: "none",
                color: "var(--text-primary)",
                fontSize: 15,
                fontFamily: "inherit",
              }}
            />
            <kbd
              style={{
                padding: "2px 6px",
                borderRadius: 4,
                fontSize: 11,
                background: "var(--bg-glass-hover)",
                color: "var(--text-muted)",
                border: "1px solid var(--border-glass)",
              }}
            >
              ESC
            </kbd>
          </div>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
          {filtered.length === 0 && (
            <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
              No results found for that query
            </div>
          )}
          {filtered.map((cmd, idx) => (
            <button
              key={cmd.id}
              onClick={() => {
                cmd.action();
                setQuery("");
                onClose();
              }}
              onMouseEnter={() => setSelectedIndex(idx)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                width: "100%",
                padding: "10px 16px",
                background: idx === selectedIndex ? "var(--bg-glass-hover)" : "transparent",
                border: "none",
                textAlign: "left",
                cursor: "pointer",
                transition: "background 0.1s",
              }}
            >
              <span style={{ fontSize: 16, width: 24, textAlign: "center", opacity: 0.7 }}>
                {cmd.icon || "\u2192"}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>
                  {cmd.label}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {cmd.description}
                </div>
              </div>
              {cmd.shortcut && (
                <kbd
                  style={{
                    padding: "2px 6px",
                    borderRadius: 4,
                    fontSize: 11,
                    background: "var(--bg-glass-hover)",
                    color: "var(--text-muted)",
                    border: "1px solid var(--border-glass)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {cmd.shortcut}
                </kbd>
              )}
              <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "capitalize" }}>
                {cmd.category}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
