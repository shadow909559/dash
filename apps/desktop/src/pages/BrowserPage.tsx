import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard, TabBar, EmptyState } from "@/components/ultron";
import { Globe, ExternalLink, X, Plus, Bookmark, History, BarChart3, RefreshCw, Loader2 } from "lucide-react";

interface Tab {
  id: string;
  url: string;
  title: string;
  active: boolean;
  opened_at?: string;
}

export const BrowserPage: React.FC = () => {
  const { addNotification } = useNotifier();
  const [tab, setTab] = useState<"tabs" | "bookmarks" | "history">("tabs");
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [bookmarks, setBookmarks] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, b, h, s] = await Promise.all([
        authFetch("/features/browser/tabs"),
        authFetch("/features/browser/bookmarks"),
        authFetch("/features/browser/history?limit=30"),
        authFetch("/features/browser/stats"),
      ]);
      if (t?.ok) setTabs((await t.json()).tabs || []);
      if (b?.ok) setBookmarks((await b.json()).bookmarks || []);
      if (h?.ok) setHistory((await h.json()).history || []);
      if (s?.ok) setStats(await s.json());
      if (!t?.ok) setError("Browser service unavailable.");
    } catch {
      setError("Browser service unreachable — is the backend running?");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openTab = async () => {
    if (!url.trim()) return;
    setOpening(true);
    try {
      const target = url.trim().match(/^https?:\/\//) ? url.trim() : `https://${url.trim()}`;
      const r = await authFetch("/features/browser/tabs/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: target, title: "" }),
      });
      if (r?.ok) {
        setUrl("");
        addNotification({ type: "success", title: "Tab opened", message: target });
        load();
      } else {
        addNotification({ type: "error", title: "Failed", message: "Could not open tab" });
      }
    } catch {
      addNotification({ type: "error", title: "Failed", message: "Backend unreachable" });
    }
    setOpening(false);
  };

  const closeTab = async (tabId: string) => {
    try {
      await authFetch("/features/browser/tabs/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tab_id: tabId }),
      });
      setTabs((prev) => prev.filter((t) => t.id !== tabId));
    } catch {
      /* refetch on next refresh */
    }
  };

  return (
    <PageShell glowColor="rgba(77, 148, 255, 0.05)">
      <PageHeader
        icon={<Globe size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        iconBg="rgba(77,148,255,0.15)"
        title="Browser Management"
        subtitle={
          stats
            ? `${stats.open_tabs ?? tabs.length} open tabs • ${stats.bookmarks ?? bookmarks.length} bookmarks • ${stats.history_entries ?? history.length} history entries`
            : "Manage tabs, bookmarks, and browsing history"
        }
        actions={
          <button onClick={load} className="dash-btn-ghost" title="Refresh" aria-label="Refresh browser data">
            <RefreshCw size={14} className={loading ? "animate-rotate" : undefined} />
          </button>
        }
      />

      <div className="dash-page-content">
        {error && (
          <div role="alert" style={{ padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, marginBottom: 14, fontSize: 12, color: "#ef4444" }}>
            {error}
          </div>
        )}

        {/* URL bar */}
        <GlassCard glow padding={14} style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Globe size={15} style={{ color: "var(--dash-accent)", flexShrink: 0 }} />
            <input
              aria-label="Website URL"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && openTab()}
              placeholder="Enter URL to open…"
              className="dash-input-ultron"
              style={{ flex: 1, fontFamily: "'JetBrains Mono', monospace" }}
            />
            <button onClick={openTab} disabled={opening || !url.trim()} className="dash-btn-primary" aria-label="Open tab">
              {opening ? <Loader2 size={14} className="spin" /> : <><Plus size={14} /> Open</>}
            </button>
          </div>
        </GlassCard>

        <TabBar
          tabs={[
            { id: "tabs", label: "Tabs", count: tabs.length },
            { id: "bookmarks", label: "Bookmarks", count: bookmarks.length },
            { id: "history", label: "History", count: history.length },
          ]}
          activeTab={tab}
          onTabChange={(id) => setTab(id as "tabs" | "bookmarks" | "history")}
        />

        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {[1, 2, 3].map((i) => (
              <div key={i} style={{ height: 52, background: "var(--dash-bg)", borderRadius: "var(--dash-radius-md)", opacity: 0.5 }} />
            ))}
          </div>
        ) : tab === "tabs" ? (
          tabs.length === 0 ? (
            <EmptyState icon={<Globe size={28} style={{ color: "var(--dash-text-muted)" }} />} title="No open tabs" description="Open a URL above to start browsing." />
          ) : (
            <div className="dash-stagger">
              {tabs.map((t) => (
                <GlassCard key={t.id} padding={12} className="dash-card-glow">
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: t.active ? "#22c55e" : "var(--dash-text-muted)" }} title={t.active ? "Active" : "Background"} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--dash-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {t.title || t.url}
                      </div>
                      <div style={{ fontSize: 10, color: "var(--dash-text-muted)", fontFamily: "'JetBrains Mono', monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {t.url}
                      </div>
                    </div>
                    <button onClick={() => window.open(t.url, "_blank")} className="dash-btn-ghost" title="Open in system browser" aria-label="Open in system browser" style={{ minHeight: 24, minWidth: 24 }}>
                      <ExternalLink size={13} />
                    </button>
                    <button onClick={() => closeTab(t.id)} className="dash-btn-ghost" title="Close tab" aria-label="Close tab" style={{ minHeight: 24, minWidth: 24, color: "#ef4444" }}>
                      <X size={13} />
                    </button>
                  </div>
                </GlassCard>
              ))}
            </div>
          )
        ) : tab === "bookmarks" ? (
          bookmarks.length === 0 ? (
            <EmptyState icon={<Bookmark size={28} style={{ color: "var(--dash-text-muted)" }} />} title="No bookmarks" description="Bookmarked pages will appear here." />
          ) : (
            <div className="dash-stagger">
              {bookmarks.map((b, i) => (
                <GlassCard key={b.id || i} padding={12} className="dash-card-glow">
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Bookmark size={13} style={{ color: "#f59e0b", flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{b.title || b.url}</div>
                      <div style={{ fontSize: 10, color: "var(--dash-text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>{b.url}</div>
                    </div>
                    {b.folder && <span style={{ fontSize: 10, color: "var(--dash-text-muted)", border: "1px solid var(--dash-border)", borderRadius: 999, padding: "1px 8px" }}>{b.folder}</span>}
                  </div>
                </GlassCard>
              ))}
            </div>
          )
        ) : history.length === 0 ? (
          <EmptyState icon={<History size={28} style={{ color: "var(--dash-text-muted)" }} />} title="No history" description="Pages you visit will be recorded here." />
        ) : (
          <div className="dash-stagger">
            {history.map((h, i) => (
              <div key={h.id || i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 4px", borderBottom: "1px solid var(--dash-border-subtle)" }}>
                <History size={12} style={{ color: "var(--dash-text-muted)", flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 12, color: "var(--dash-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{h.title || h.url}</span>
                {h.visited_at && <span style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>{new Date(h.visited_at).toLocaleString()}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default BrowserPage;
