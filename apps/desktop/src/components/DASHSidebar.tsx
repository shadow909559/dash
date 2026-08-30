import React from "react";
import { NavLink } from "react-router-dom";
import {
  Home,
  MessageSquare,
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
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Mic,
} from "lucide-react";
import { useAIStore } from "@/stores/aiStore";

interface DASHSidebarProps {
  isExpanded: boolean;
  onToggle: () => void;
}

interface NavItem {
  id: string;
  path: string;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>;
  badge?: string | number;
}

const PRIMARY_NAV_ITEMS: NavItem[] = [
  { id: "home", path: "/", label: "Home", icon: Home },
  { id: "chat", path: "/chat", label: "Chat", icon: MessageSquare },
  { id: "voice", path: "/voice", label: "Voice", icon: Mic },
  { id: "memory", path: "/memory", label: "Memory", icon: Brain },
  { id: "knowledge", path: "/knowledge", label: "Knowledge", icon: BookOpen },
  { id: "obsidian", path: "/obsidian", label: "Obsidian", icon: BookOpen },
  { id: "projects", path: "/projects", label: "Projects", icon: FolderKanban },
  { id: "coding", path: "/coding", label: "Coding", icon: Code2 },
  { id: "research", path: "/research", label: "Research", icon: Compass },
  { id: "browser", path: "/browser", label: "Browser", icon: Globe },
  { id: "desktop", path: "/desktop", label: "Desktop", icon: Monitor },
  { id: "phone", path: "/phone", label: "Phone", icon: Smartphone },
  { id: "automation", path: "/automation", label: "Automation", icon: Zap },
  { id: "planner", path: "/planner", label: "Planner", icon: CalendarDays },
  { id: "agents", path: "/agents", label: "Agents", icon: Bot },
  { id: "system-monitor", path: "/system-monitor", label: "System", icon: Activity },
];

const SECONDARY_NAV_ITEMS: NavItem[] = [
  { id: "notifications", path: "/notifications", label: "Notifications", icon: Bell },
  { id: "approvals", path: "/approvals", label: "Approvals", icon: CheckSquare },
  { id: "plugins", path: "/plugins", label: "Plugins", icon: Puzzle },
  { id: "analytics", path: "/analytics", label: "Analytics", icon: BarChart3 },
  { id: "settings", path: "/settings", label: "Settings", icon: Settings },
];

export const DASHSidebar: React.FC<DASHSidebarProps> = ({ isExpanded, onToggle }) => {
  const { systemStatus } = useAIStore();

  const renderNavGroup = (items: NavItem[], groupTitle?: string) => (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {groupTitle && isExpanded && (
        <div
          style={{
            padding: "8px 12px 4px 12px",
            fontSize: 10,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--dash-text-muted)",
          }}
        >
          {groupTitle}
        </div>
      )}
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.id}
            to={item.path}
            title={!isExpanded ? item.label : undefined}
            style={({ isActive }) => ({
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: isExpanded ? "8px 12px" : "8px",
              justifyContent: isExpanded ? "flex-start" : "center",
              borderRadius: "var(--dash-radius-sm)",
              color: isActive ? "var(--dash-text)" : "var(--dash-text-secondary)",
              backgroundColor: isActive ? "var(--dash-surface-active)" : "transparent",
              border: `1px solid ${isActive ? "var(--dash-border-accent)" : "transparent"}`,
              textDecoration: "none",
              fontSize: 13,
              fontWeight: isActive ? 500 : 400,
              transition: "all var(--dash-transition-fast)",
              position: "relative",
            })}
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={18}
                  style={{
                    color: isActive ? "var(--dash-accent)" : "var(--dash-text-secondary)",
                    flexShrink: 0,
                  }}
                />
                {isExpanded && (
                  <span
                    style={{
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      flex: 1,
                    }}
                  >
                    {item.label}
                  </span>
                )}
                {isExpanded && item.badge && (
                  <span
                    style={{
                      fontSize: 10,
                      padding: "1px 6px",
                      borderRadius: "var(--dash-radius-full)",
                      backgroundColor: "var(--dash-accent-glow)",
                      color: "var(--dash-accent)",
                      border: "1px solid var(--dash-border-accent)",
                    }}
                  >
                    {item.badge}
                  </span>
                )}
              </>
            )}
          </NavLink>
        );
      })}
    </div>
  );

  return (
    <aside
      role="navigation"
      aria-label="DASH navigation"
      style={{
        width: isExpanded ? 240 : 64,
        height: "100%",
        backgroundColor: "var(--dash-surface)",
        borderRight: "1px solid var(--dash-border)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        transition: "width var(--dash-transition-base)",
        zIndex: 30,
        overflow: "hidden",
        userSelect: "none",
      }}
    >
      {/* Top Branding Section */}
      <div
        style={{
          height: 48,
          display: "flex",
          alignItems: "center",
          justifyContent: isExpanded ? "space-between" : "center",
          padding: isExpanded ? "0 12px 0 16px" : "0 8px",
          borderBottom: "1px solid var(--dash-border)",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            overflow: "hidden",
          }}
        >
          {/* DASH Hexagon/Circle Logo */}
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: "var(--dash-radius-sm)",
              background: "linear-gradient(135deg, var(--dash-accent), var(--dash-accent-secondary))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 12px var(--dash-accent-glow)",
              flexShrink: 0,
            }}
          >
            <ShieldCheck size={16} color="#ffffff" />
          </div>
          {isExpanded && (
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: "var(--dash-text)",
                  letterSpacing: "0.04em",
                }}
              >
                DASH OS
              </span>
              <span
                style={{
                  fontSize: 10,
                  color: "var(--dash-text-muted)",
                  letterSpacing: "0.02em",
                }}
              >
                AI Operating System
              </span>
            </div>
          )}
        </div>

        {isExpanded && (
          <button
            onClick={onToggle}
            title="Collapse Sidebar"
            aria-label="Collapse Sidebar"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--dash-text-muted)",
              cursor: "pointer",
              padding: 4,
              borderRadius: "var(--dash-radius-xs)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all var(--dash-transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--dash-text)";
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--dash-text-muted)";
              e.currentTarget.style.backgroundColor = "transparent";
            }}
          >
            <ChevronLeft size={16} />
          </button>
        )}
      </div>

      {/* Main Navigation Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          padding: "12px 8px",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        {renderNavGroup(PRIMARY_NAV_ITEMS, "Core")}
        <div style={{ height: 1, backgroundColor: "var(--dash-border-subtle)", margin: "4px 4px" }} />
        {renderNavGroup(SECONDARY_NAV_ITEMS, "System")}
      </div>

      {/* Footer / Toggle Section */}
      <div
        style={{
          padding: isExpanded ? "10px 12px" : "10px 8px",
          borderTop: "1px solid var(--dash-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: isExpanded ? "space-between" : "center",
          backgroundColor: "var(--dash-bg-subtle)",
          flexShrink: 0,
        }}
      >
        {!isExpanded ? (
          <button
            onClick={onToggle}
            title="Expand Sidebar"
            aria-label="Expand Sidebar"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--dash-text-muted)",
              cursor: "pointer",
              padding: 6,
              borderRadius: "var(--dash-radius-xs)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all var(--dash-transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--dash-text)";
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--dash-text-muted)";
              e.currentTarget.style.backgroundColor = "transparent";
            }}
          >
            <ChevronRight size={16} />
          </button>
        ) : (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 11,
              color: "var(--dash-text-secondary)",
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                backgroundColor: systemStatus === "online" ? "var(--dash-success)" : "var(--dash-danger)",
              }}
            />
            <span>{systemStatus === "online" ? "System Ready" : "Disconnected"}</span>
          </div>
        )}
      </div>
    </aside>
  );
};

export default DASHSidebar;