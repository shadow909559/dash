import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { useNotifier } from "@/components/NotificationProvider";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { Calendar, Plus, ChevronLeft, ChevronRight, Clock, MapPin, RefreshCw, Upload, AlarmClock } from "lucide-react";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function CalendarPage() {
  const { addNotification } = useNotifier();
  const [events, setEvents] = useState<any[]>([]);
  const [calendars, setCalendars] = useState<any[]>([]);
  const [stats, setStats] = useState({ total_events: 0, today_events: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDate, setNewDate] = useState(new Date().toISOString().slice(0, 10));
  const [newTime, setNewTime] = useState("09:00");
  const [showIcs, setShowIcs] = useState(false);
  const [icsText, setIcsText] = useState("");
  const [deadlines, setDeadlines] = useState<any[]>([]);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [evRes, calRes, stRes, dlRes] = await Promise.all([
        authFetch("/features/calendar/events"),
        authFetch("/features/calendar/list"),
        authFetch("/features/calendar/stats"),
        authFetch("/features/deadlines?window_days=30"),
      ]);
      if (evRes?.ok) setEvents((await evRes.json()).events || []);
      if (calRes?.ok) setCalendars((await calRes.json()).calendars || []);
      if (stRes?.ok) setStats(await stRes.json());
      if (dlRes?.ok) setDeadlines((await dlRes.json()).deadlines || []);
      if (!evRes?.ok) setError("Calendar service unavailable.");
    } catch {
      setError("Calendar service unreachable — is the backend running?");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const createEvent = async () => {
    if (!newTitle.trim()) return;
    // Default duration: 1 hour (start + 60min)
    const start = `${newDate}T${newTime}:00`;
    const endHour = (parseInt(newTime.split(":")[0], 10) + 1) % 24;
    const end = `${newDate}T${String(endHour).padStart(2, "0")}:${newTime.split(":")[1]}:00`;
    try {
      const r = await authFetch("/features/calendar/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: newTitle.trim(), start, end }) });
      if (r?.ok) addNotification({ type: "success", title: "Event Created", message: newTitle.trim() });
      else addNotification({ type: "error", title: "Failed", message: "Could not create event" });
    } catch { addNotification({ type: "error", title: "Failed", message: "Backend unreachable" }); }
    setShowCreate(false); setNewTitle(""); fetch();
  };

  const importIcs = async () => {
    if (!icsText.trim()) return;
    try {
      const r = await authFetch("/features/calendar/import-ics", { method: "POST", headers: { "Content-Type": "text/calendar" }, body: icsText });
      const d = await r?.json().catch(() => ({}));
      if (d?.ok) addNotification({ type: "success", title: "ICS imported", message: `${d.created} events added, ${d.skipped} already known` });
      else addNotification({ type: "error", title: "Import failed", message: "Could not parse the ICS text" });
      if (d?.ok) { setShowIcs(false); setIcsText(""); fetch(); }
    } catch { addNotification({ type: "error", title: "Failed", message: "Backend unreachable" }); }
  };

  const urgencyColor: Record<string, string> = {
    overdue: "#ef4444", today: "#f59e0b", urgent: "#f97316",
    soon: "#eab308", upcoming: "var(--accent, #22c55e)", unknown: "#666",
  };

  const getDaysInMonth = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const first = new Date(year, month, 1);
    const last = new Date(year, month + 1, 0);
    const days: { date: Date; inMonth: boolean }[] = [];
    for (let i = 0; i < first.getDay(); i++) days.push({ date: new Date(year, month, -first.getDay() + i + 1), inMonth: false });
    for (let d = 1; d <= last.getDate(); d++) days.push({ date: new Date(year, month, d), inMonth: true });
    while (days.length < 42) days.push({ date: new Date(year, month + 1, days.length - first.getDay() - last.getDate() + 1), inMonth: false });
    return days;
  };

  const getEventsForDate = (date: Date) => {
    const ds = date.toISOString().slice(0, 10);
    return events.filter(e => e.start?.startsWith(ds));
  };

  const today = new Date();
  const isToday = (d: Date) => d.toDateString() === today.toDateString();

  return (
    <PageShell>
      <PageHeader icon={<Calendar size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Calendar" subtitle={`${stats.today_events} events today`} actions={<div style={{ display: "flex", gap: 6 }}><button onClick={() => setShowIcs(!showIcs)} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "var(--text)", fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}><Upload size={12} /> Import ICS</button><button onClick={() => setShowCreate(true)} style={{ background: "var(--accent, #22c55e)", border: "none", borderRadius: 6, padding: "6px 12px", cursor: "pointer", color: "#000", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}><Plus size={12} /> New Event</button><button onClick={fetch} className="dash-btn-ghost" title="Refresh" aria-label="Refresh calendar"><RefreshCw size={14} className={loading ? "animate-rotate" : undefined} /></button></div>} />

      {showIcs && (
        <GlassCard padding={12} style={{ marginBottom: 14 }}>
          <textarea
            value={icsText}
            onChange={(e) => setIcsText(e.target.value)}
            placeholder="Paste ICS calendar text here (BEGIN:VCALENDAR …) — events dedupe on their UID"
            aria-label="ICS calendar text"
            rows={5}
            style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 11, fontFamily: "monospace", resize: "vertical" }}
          />
          <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", marginTop: 8 }}>
            <button onClick={() => { setShowIcs(false); setIcsText(""); }} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 14px", cursor: "pointer", color: "var(--text)", fontSize: 12 }}>Cancel</button>
            <button onClick={importIcs} disabled={!icsText.trim()} style={{ background: "var(--accent, #22c55e)", border: "none", borderRadius: 6, padding: "6px 14px", cursor: icsText.trim() ? "pointer" : "not-allowed", color: "#000", fontSize: 12, fontWeight: 600, opacity: icsText.trim() ? 1 : 0.5 }}>Import</button>
          </div>
        </GlassCard>
      )}

      {error && (
        <div role="alert" style={{ padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, marginBottom: 14, fontSize: 12, color: "#ef4444" }}>
          {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>
        {/* Month View */}
        <GlassCard>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <button onClick={() => setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1))} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text)" }}><ChevronLeft size={18} /></button>
            <span style={{ fontSize: 15, fontWeight: 600 }}>{currentDate.toLocaleString("default", { month: "long", year: "numeric" })}</span>
            <button onClick={() => setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1))} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text)" }}><ChevronRight size={18} /></button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 1 }}>
            {DAYS.map(d => <div key={d} style={{ textAlign: "center", fontSize: 11, color: "var(--text-muted, #666)", padding: "6px 0", fontWeight: 500 }}>{d}</div>)}
            {getDaysInMonth().map((d, i) => {
              const dayEvents = getEventsForDate(d.date);
              return (
                <div key={i} style={{ minHeight: 60, padding: 4, borderRadius: 4, background: isToday(d.date) ? "rgba(34,197,94,0.1)" : d.inMonth ? "transparent" : "rgba(255,255,255,0.02)", opacity: d.inMonth ? 1 : 0.3 }}>
                  <div style={{ fontSize: 11, fontWeight: isToday(d.date) ? 700 : 400, color: isToday(d.date) ? "var(--accent, #22c55e)" : "var(--text)", marginBottom: 2 }}>{d.date.getDate()}</div>
                  {dayEvents.slice(0, 2).map(e => (
                    <div key={e.id} style={{ fontSize: 9, padding: "1px 4px", borderRadius: 3, background: "var(--accent, #22c55e)", color: "#000", marginBottom: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{e.title}</div>
                  ))}
                </div>
              );
            })}
          </div>
        </GlassCard>

        {/* Today's Events */}
        <GlassCard>
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Today</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {events.filter(e => e.start?.startsWith(today.toISOString().slice(0, 10))).map(e => (
              <div key={e.id} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", borderLeft: "3px solid var(--accent, #22c55e)" }}>
                <div style={{ fontSize: 12, fontWeight: 500 }}>{e.title}</div>
                <div style={{ fontSize: 10, color: "var(--text-muted, #666)", display: "flex", gap: 8, marginTop: 3 }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 3 }}><Clock size={10} /> {e.start?.slice(11, 16)}</span>
                  {e.location && <span style={{ display: "flex", alignItems: "center", gap: 3 }}><MapPin size={10} /> {e.location}</span>}
                </div>
              </div>
            ))}
          </div>
          <h4 style={{ margin: "16px 0 8px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: 4 }}><AlarmClock size={12} /> Deadlines ({deadlines.length})</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 12 }}>
            {deadlines.slice(0, 6).map(d => (
              <div key={d.id} style={{ fontSize: 11, padding: "5px 8px", borderRadius: 6, background: "var(--bg-secondary, #1a1a2e)", borderLeft: `3px solid ${urgencyColor[d.urgency] || "#666"}`, display: "flex", justifyContent: "space-between", gap: 6 }}>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }} title={d.title}>{d.title}</span>
                <span style={{ color: urgencyColor[d.urgency] || "#666", whiteSpace: "nowrap" }}>
                  {d.urgency === "overdue" ? "overdue" : d.due?.slice(5, 10)}
                </span>
              </div>
            ))}
            {deadlines.length === 0 && <p style={{ fontSize: 11, color: "var(--text-muted, #666)", margin: "2px 0 0" }}>No upcoming deadlines. Scan your inbox from the Email page to find “due …” dates.</p>}
          </div>

          <h4 style={{ margin: "16px 0 8px", fontSize: 13, color: "var(--text-muted, #666)", textTransform: "uppercase", letterSpacing: "0.08em" }}>All Events ({events.length})</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {events.slice(0, 5).map(e => (
              <div key={e.id} style={{ fontSize: 11, padding: "4px 0", borderBottom: "1px solid var(--border, #333)", display: "flex", justifyContent: "space-between" }}>
                <span>{e.title}</span>
                <span style={{ color: "var(--text-muted, #666)" }}>{e.start?.slice(5, 10)}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
          <GlassCard style={{ maxWidth: 400, width: "100%" }}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15 }}>New Event</h3>
            <div style={{ marginBottom: 10 }}>
              <input value={newTitle} onChange={e => setNewTitle(e.target.value)} placeholder="Event title" style={{ width: "100%", padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 13 }} />
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
              <input type="date" value={newDate} onChange={e => setNewDate(e.target.value)} style={{ flex: 1, padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 12 }} />
              <input type="time" value={newTime} onChange={e => setNewTime(e.target.value)} style={{ width: 100, padding: "8px 10px", background: "var(--bg-secondary, #1a1a2e)", border: "1px solid var(--border, #333)", borderRadius: 6, color: "var(--text)", fontSize: 12 }} />
            </div>
            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
              <button onClick={() => setShowCreate(false)} style={{ background: "none", border: "1px solid var(--border, #333)", borderRadius: 6, padding: "6px 12px", color: "var(--text)", cursor: "pointer", fontSize: 12 }}>Cancel</button>
              <button onClick={createEvent} style={{ background: "var(--accent, #22c55e)", border: "none", borderRadius: 6, padding: "6px 12px", color: "#000", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>Create</button>
            </div>
          </GlassCard>
        </div>
      )}
    </PageShell>
  );
}
