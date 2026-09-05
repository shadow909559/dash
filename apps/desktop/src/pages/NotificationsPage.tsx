import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { Bell, Check, RefreshCw, BellOff, Eye } from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle, TabBar } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Notification {
  id: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
}

export const NotificationsPage: React.FC = () => {
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"unread" | "all">("unread");

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/notifications`);
      const d = await r.json();
      setItems(d.notifications || d || []);
    } catch {}
    setLoading(false);
  }, []);

  const markRead = async (id: string) => {
    try {
      await authFetch(`${API}/notifications/${id}/read`, { method: "PATCH" });
      fetchNotifications();
    } catch {}
  };

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const unread = items.filter((n) => !n.read);
  const all = items;
  const displayItems = activeTab === "unread" ? unread : all;

  return (
    <PageShell glowColor="rgba(77, 148, 255, 0.05)">
      <PageHeader
        icon={<Bell size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        title="Notifications"
        subtitle="System alerts and agent status events"
        badge={
          unread.length > 0 ? (
            <span
              className="dash-badge-glow animate-status-pulse"
              style={{
                background: "rgba(77,148,255,0.12)",
                color: "var(--dash-accent)",
                border: "1px solid var(--dash-border-accent)",
              }}
            >
              <Bell size={10} />
              {unread.length} unread
            </span>
          ) : undefined
        }
        actions={
          <button onClick={fetchNotifications} className="dash-btn-ghost">
            <RefreshCw size={14} />
          </button>
        }
      />

      <div className="dash-page-content">
        {/* Tabs */}
        <TabBar
          tabs={[
            { id: "unread", label: "Unread", count: unread.length },
            { id: "all", label: "All", count: all.length },
          ]}
          activeTab={activeTab}
          onTabChange={(id) => setActiveTab(id as "unread" | "all")}
        />

        {/* Content */}
        {loading ? (
          <div
            style={{
              textAlign: "center",
              padding: 48,
              color: "var(--dash-text-muted)",
            }}
          >
            <RefreshCw
              size={18}
              className="animate-rotate"
              style={{ marginBottom: 10 }}
            />
            <div>Loading notifications...</div>
          </div>
        ) : displayItems.length === 0 ? (
          <EmptyState
            icon={
              activeTab === "unread" ? (
                <BellOff size={28} style={{ color: "var(--dash-success)" }} />
              ) : (
                <Bell size={28} style={{ color: "var(--dash-text-muted)" }} />
              )
            }
            title={
              activeTab === "unread"
                ? "All caught up!"
                : "No notifications yet"
            }
            description={
              activeTab === "unread"
                ? "No unread notifications. DASH will alert you when something needs attention."
                : "Notifications will appear here as DASH processes tasks and system events occur."
            }
          />
        ) : (
          <div className="dash-stagger">
            {displayItems.map((n) => (
              <GlassCard key={n.id} padding={0} className="dash-card-glow">
                <div
                  style={{
                    display: "flex",
                    gap: 14,
                    alignItems: "flex-start",
                    padding: "14px 18px",
                  }}
                >
                  {/* Indicator line */}
                  <div
                    style={{
                      width: 3,
                      minHeight: 32,
                      borderRadius: 2,
                      background: n.read
                        ? "var(--dash-text-muted)"
                        : "var(--dash-accent)",
                      opacity: n.read ? 0.3 : 0.7,
                      flexShrink: 0,
                      marginTop: 2,
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 4,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: "var(--dash-text)",
                          opacity: n.read ? 0.7 : 1,
                        }}
                      >
                        {n.title}
                      </span>
                      {!n.read && (
                        <button
                          onClick={() => markRead(n.id)}
                          className="dash-btn-ghost"
                          style={{ padding: "3px 8px", fontSize: 10 }}
                        >
                          <Eye size={10} /> Mark read
                        </button>
                      )}
                    </div>
                    <p
                      style={{
                        fontSize: 12,
                        color: "var(--dash-text-secondary)",
                        margin: "0 0 4px",
                        lineHeight: 1.5,
                        opacity: n.read ? 0.6 : 1,
                      }}
                    >
                      {n.message}
                    </p>
                    <span
                      style={{
                        fontSize: 10,
                        color: "var(--dash-text-muted)",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {n.created_at
                        ? new Date(n.created_at).toLocaleString()
                        : ""}
                    </span>
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default NotificationsPage;
