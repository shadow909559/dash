import React from "react";

/**
 * Ultron-styled page wrapper with ambient HUD background effects.
 * Wraps page content with scanline, grid overlay, and radial glow.
 */
export function PageShell({
  children,
  glowColor = "rgba(63, 169, 245, 0.06)",
  className = "",
  style = {},
}: {
  children: React.ReactNode;
  glowColor?: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={className}
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        overflow: "hidden",
        background: `
          radial-gradient(ellipse at 50% 0%, ${glowColor}, transparent 60%),
          var(--dash-bg)
        `,
        ...style,
      }}
    >
      {/* HUD grid background */}
      <div
        className="dash-hud-grid"
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.3,
          pointerEvents: "none",
        }}
      />
      {/* Scanline */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 1,
          background:
            "linear-gradient(90deg, transparent, rgba(63,169,245,0.12), transparent)",
          animation: "scanLine 8s linear infinite",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />
      {/* Content */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          width: "100%",
          height: "100%",
          overflowY: "auto",
        }}
      >
        {children}
      </div>
    </div>
  );
}

/**
 * Ultron-styled page header with icon, title, subtitle, and optional actions.
 */
export function PageHeader({
  icon,
  iconColor = "var(--dash-accent)",
  iconBg,
  title,
  subtitle,
  badge,
  actions,
}: {
  icon: React.ReactNode;
  iconColor?: string;
  iconBg?: string;
  title: string;
  subtitle: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div
      className="dash-luminous"
      style={{
        padding: "20px 28px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        background: "var(--dash-surface)",
        backgroundImage: "var(--dash-gradient-surface)",
        borderBottom: "1px solid var(--dash-border)",
        position: "relative",
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: "var(--dash-radius-md)",
          backgroundColor: iconBg || "var(--dash-accent-glow)",
          border: `1px solid ${iconColor}30`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: "var(--dash-text)",
            margin: 0,
            letterSpacing: "-0.01em",
          }}
        >
          {title}
        </h1>
        <p
          style={{
            fontSize: 12,
            color: "var(--dash-text-muted)",
            margin: "3px 0 0",
            letterSpacing: "0.01em",
          }}
        >
          {subtitle}
        </p>
      </div>
      {badge && <div style={{ flexShrink: 0 }}>{badge}</div>}
      {actions && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {actions}
        </div>
      )}
    </div>
  );
}

/**
 * Pulsing status indicator dot with label.
 */
export function StatusIndicator({
  status,
  label,
}: {
  status: "online" | "offline" | "warning" | "processing";
  label: string;
}) {
  const colors = {
    online: "var(--dash-success)",
    offline: "var(--dash-danger)",
    warning: "var(--dash-warning)",
    processing: "var(--ultron-core-bright)",
  };
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        fontSize: 10,
        fontFamily: "'JetBrains Mono', monospace",
        letterSpacing: "0.06em",
        color: colors[status],
      }}
    >
      <span
        className={
          status === "online" || status === "processing"
            ? "animate-status-pulse"
            : undefined
        }
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: colors[status],
          boxShadow: `0 0 6px ${colors[status]}`,
          display: "inline-block",
        }}
      />
      {label}
    </div>
  );
}

/**
 * Empty state with icon, title, and optional action.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 64,
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: "var(--dash-radius-lg)",
          background: "var(--dash-surface)",
          border: "1px solid var(--dash-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 16,
          boxShadow: "0 0 30px var(--dash-accent-glow)",
        }}
      >
        {icon}
      </div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 600,
          color: "var(--dash-text)",
          marginBottom: 6,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontSize: 13,
          color: "var(--dash-text-muted)",
          maxWidth: 400,
          lineHeight: 1.6,
        }}
      >
        {description}
      </div>
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}

/**
 * Reusable section title for grouping content.
 */
export function SectionTitle({
  children,
  count,
  action,
}: {
  children: React.ReactNode;
  count?: number;
  action?: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 12,
      }}
    >
      <div className="dash-section-title" style={{ margin: 0 }}>
        {children}
        {count !== undefined && (
          <span
            style={{
              marginLeft: 6,
              fontWeight: 400,
              opacity: 0.7,
            }}
          >
            ({count})
          </span>
        )}
      </div>
      {action}
    </div>
  );
}

/**
 * Premium glass card with optional glow border.
 */
export function GlassCard({
  children,
  glow = false,
  padding = 18,
  className = "",
  style = {},
}: {
  children: React.ReactNode;
  glow?: boolean;
  padding?: number;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`dash-card ${glow ? "dash-glow-border" : ""} ${className}`}
      style={{
        padding,
        backgroundImage: "var(--dash-gradient-surface)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/**
 * Tab bar component with Ultron styling.
 */
export function TabBar({
  tabs,
  activeTab,
  onTabChange,
}: {
  tabs: Array<{ id: string; label: string; icon?: React.ReactNode; count?: number }>;
  activeTab: string;
  onTabChange: (id: string) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        padding: 3,
        background: "var(--dash-surface)",
        borderRadius: "var(--dash-radius-md)",
        border: "1px solid var(--dash-border)",
        width: "fit-content",
      }}
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          style={{
            padding: "6px 14px",
            borderRadius: "var(--dash-radius-sm)",
            border: "none",
            background:
              activeTab === tab.id ? "var(--dash-surface-active)" : "transparent",
            color:
              activeTab === tab.id ? "var(--dash-text)" : "var(--dash-text-muted)",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: activeTab === tab.id ? 600 : 400,
            display: "flex",
            alignItems: "center",
            gap: 6,
            transition: "all var(--dash-transition-fast)",
          }}
        >
          {tab.icon}
          {tab.label}
          {tab.count !== undefined && (
            <span style={{ opacity: 0.6, fontSize: 10 }}>({tab.count})</span>
          )}
        </button>
      ))}
    </div>
  );
}
