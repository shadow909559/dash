import { useState, useEffect, useRef } from 'react';

interface TimeEntry { id: string; task: string; project: string; start_time: string; end_time: string; duration_seconds: number; tags: string[]; billable: boolean; notes: string; }

export default function TimeTrackingPage() {
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [activeTask, setActiveTask] = useState('');
  const [activeProject, setActiveProject] = useState('');
  const [isTracking, setIsTracking] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [showManual, setShowManual] = useState(false);
  const [manualEntry, setManualEntry] = useState({ task: '', project: '', duration: '', date: new Date().toISOString().split('T')[0] });
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { loadEntries(); return () => { if (timerRef.current) clearInterval(timerRef.current); }; }, []);

  async function loadEntries() {
    try { const r = await fetch('/api/v1/phase4/time-entries'); if (r.ok) setEntries(await r.json()); } catch { /* */ }
  }

  function startTracking() {
    if (!activeTask) return;
    setIsTracking(true);
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
  }

  async function stopTracking() {
    if (timerRef.current) clearInterval(timerRef.current);
    setIsTracking(false);
    try {
      await fetch('/api/v1/phase4/time-entries', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task: activeTask, project: activeProject, duration_seconds: elapsed }) });
      setActiveTask(''); setActiveProject(''); setElapsed(0); loadEntries();
    } catch { /* */ }
  }

  async function addManualEntry() {
    if (!manualEntry.task) return;
    const parts = manualEntry.duration.split(':').map(Number);
    const duration = (parts[0] || 0) * 3600 + (parts[1] || 0) * 60 + (parts[2] || 0);
    try { await fetch('/api/v1/phase4/time-entries', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task: manualEntry.task, project: manualEntry.project, duration_seconds: duration, start_time: manualEntry.date }) }); setShowManual(false); loadEntries(); } catch { /* */ }
  }

  function formatDuration(seconds: number) { const h = Math.floor(seconds / 3600); const m = Math.floor((seconds % 3600) / 60); const s = seconds % 60; return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`; }

  const todayTotal = entries.filter(e => e.start_time?.startsWith(new Date().toISOString().split('T')[0])).reduce((sum, e) => sum + e.duration_seconds, 0);
  const weekTotal = entries.reduce((sum, e) => sum + e.duration_seconds, 0);

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 800, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>⏱ Time Tracking</h1>

      {/* Timer */}
      <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 24, marginBottom: 20, textAlign: 'center' }}>
        <div style={{ fontSize: 48, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: isTracking ? '#10b981' : '#e0e0e0', marginBottom: 16 }}>{formatDuration(elapsed)}</div>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginBottom: 16 }}>
          <input value={activeTask} onChange={e => setActiveTask(e.target.value)} placeholder="What are you working on?" disabled={isTracking} style={{ flex: 1, maxWidth: 300, padding: '8px 12px', background: '#12121e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
          <input value={activeProject} onChange={e => setActiveProject(e.target.value)} placeholder="Project" disabled={isTracking} style={{ width: 150, padding: '8px 12px', background: '#12121e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
        </div>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          {!isTracking ? <button onClick={startTracking} disabled={!activeTask} style={{ padding: '10px 24px', background: activeTask ? '#10b981' : '#333', border: 'none', borderRadius: 8, color: '#fff', cursor: activeTask ? 'pointer' : 'default', fontSize: 14 }}>▶ Start</button> : <button onClick={stopTracking} style={{ padding: '10px 24px', background: '#ef4444', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer', fontSize: 14 }}>⏹ Stop</button>}
          <button onClick={() => setShowManual(!showManual)} style={{ padding: '10px 24px', background: '#333', border: 'none', borderRadius: 8, color: '#e0e0e0', cursor: 'pointer' }}>+ Manual</button>
        </div>
      </div>

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
        {[{ label: 'Today', value: formatDuration(todayTotal), color: '#6366f1' }, { label: 'This Week', value: formatDuration(weekTotal), color: '#10b981' }, { label: 'Entries', value: String(entries.length), color: '#f59e0b' }].map(card => (
          <div key={card.label} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16, textAlign: 'center' }}>
            <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{card.label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>

      {showManual && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <input placeholder="Task" value={manualEntry.task} onChange={e => setManualEntry(p => ({ ...p, task: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Project" value={manualEntry.project} onChange={e => setManualEntry(p => ({ ...p, project: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Duration (HH:MM:SS)" value={manualEntry.duration} onChange={e => setManualEntry(p => ({ ...p, duration: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={addManualEntry} style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Save</button>
            <button onClick={() => setShowManual(false)} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
          </div>
        </div>
      )}

      {/* Entries List */}
      <h3 style={{ fontSize: 16, marginBottom: 12 }}>Recent Entries</h3>
      <div style={{ display: 'grid', gap: 8 }}>
        {entries.slice(0, 20).map(entry => (
          <div key={entry.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, padding: 14, display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{entry.task}</div>
              <div style={{ fontSize: 12, color: '#888' }}>{entry.project || 'No project'} • {new Date(entry.start_time).toLocaleDateString()}</div>
            </div>
            <div style={{ fontSize: 16, fontFamily: "'JetBrains Mono', monospace", color: '#6366f1' }}>{formatDuration(entry.duration_seconds)}</div>
            {entry.billable && <span style={{ background: '#10b981', padding: '2px 6px', borderRadius: 4, fontSize: 10, color: '#fff' }}>BILLABLE</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
