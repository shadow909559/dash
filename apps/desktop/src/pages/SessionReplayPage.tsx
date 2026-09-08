import { useState, useEffect } from 'react';

interface ReplaySession { id: string; title: string; duration_seconds: number; events_count: number; created_at: string; url: string; }

export default function SessionReplayPage() {
  const [sessions, setSessions] = useState<ReplaySession[]>([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<ReplaySession | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => { loadSessions(); }, []);

  async function loadSessions() {
    try { const r = await fetch('/api/v1/features/session-replay'); if (r.ok) setSessions(await r.json()); } catch { /* */ }
  }

  function formatDuration(seconds: number) { const m = Math.floor(seconds / 60); const s = seconds % 60; return `${m}m ${s}s`; }

  const filtered = sessions.filter(s => !search || s.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>🎬 Session Replay</h1>
      <p style={{ color: '#888', marginBottom: 20 }}>Record and replay user sessions</p>

      <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search sessions..." style={{ width: '100%', padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0', marginBottom: 20 }} />

      {selected && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3>{selected.title}</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setPlaying(!playing)} style={{ padding: '6px 14px', background: playing ? '#ef4444' : '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>{playing ? '⏹ Stop' : '▶ Play'}</button>
              <button onClick={() => setSelected(null)} style={{ padding: '6px 14px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>✕</button>
            </div>
          </div>
          <div style={{ background: '#0a0a0f', borderRadius: 8, height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {playing ? (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 48, marginBottom: 16, animation: 'pulse 2s infinite' }}>▶️</div>
                <div style={{ color: '#888' }}>Replaying session... {formatDuration(selected.duration_seconds)}</div>
                <div style={{ color: '#666', marginTop: 8 }}>Events: {selected.events_count}</div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: '#666' }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🎬</div>
                <div>Click Play to start replay</div>
              </div>
            )}
          </div>
          <div style={{ fontSize: 12, color: '#888', marginTop: 8 }}>Duration: {formatDuration(selected.duration_seconds)} • Events: {selected.events_count} • {new Date(selected.created_at).toLocaleString()}</div>
        </div>
      )}

      <div style={{ display: 'grid', gap: 10 }}>
        {filtered.map(s => (
          <div key={s.id} onClick={() => setSelected(s)} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16, display: 'flex', alignItems: 'center', gap: 14, cursor: 'pointer', transition: 'border-color 0.2s' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = '#6366f1')} onMouseLeave={e => (e.currentTarget.style.borderColor = '#333')}>
            <div style={{ width: 48, height: 48, borderRadius: 10, background: '#333', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }}>🎬</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{s.title}</div>
              <div style={{ fontSize: 12, color: '#888' }}>{formatDuration(s.duration_seconds)} • {s.events_count} events • {new Date(s.created_at).toLocaleDateString()}</div>
            </div>
            <button style={{ padding: '6px 14px', background: '#333', border: 'none', borderRadius: 6, color: '#10b981', cursor: 'pointer' }}>▶</button>
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No recorded sessions</div>}
      </div>
    </div>
  );
}
