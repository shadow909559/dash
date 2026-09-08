import { useState, useEffect } from 'react';

interface LogEntry { id: string; level: string; module: string; message: string; metadata: string; recorded_at: string; }

export default function DebugConsolePage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [search, setSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState('all');
  const [moduleFilter, setModuleFilter] = useState('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const [showDetails, setShowDetails] = useState<string | null>(null);

  useEffect(() => { loadLogs(); const interval = setInterval(loadLogs, 5000); return () => clearInterval(interval); }, []);

  async function loadLogs() {
    try { const r = await fetch('/api/v1/features/debug/logs'); if (r.ok) { const data = await r.json(); setLogs(data.logs || data || []); } } catch { /* */ }
  }

  async function exportLogs() {
    try { const r = await fetch('/api/v1/features/debug/logs/export?format=json'); if (r.ok) { const blob = await r.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `dash-logs-${Date.now()}.json`; a.click(); } } catch { /* */ }
  }

  async function clearLogs() {
    if (!confirm('Clear all logs?')) return;
    try { await fetch('/api/v1/features/debug/logs', { method: 'DELETE' }); loadLogs(); } catch { /* */ }
  }

  const levelColors: Record<string, string> = { debug: '#888', info: '#6366f1', warning: '#f59e0b', error: '#ef4444', critical: '#ef4444' };
  const levelIcons: Record<string, string> = { debug: '🔍', info: 'ℹ️', warning: '⚠️', error: '❌', critical: '🔥' };

  const filtered = logs.filter(l => {
    const matchSearch = !search || l.message.toLowerCase().includes(search.toLowerCase()) || l.module.toLowerCase().includes(search.toLowerCase());
    const matchLevel = levelFilter === 'all' || l.level === levelFilter;
    const matchModule = moduleFilter === 'all' || l.module === moduleFilter;
    return matchSearch && matchLevel && matchModule;
  });

  const modules = ['all', ...new Set(logs.map(l => l.module))];
  const levels = ['all', 'debug', 'info', 'warning', 'error', 'critical'];

  return (
    <div style={{ padding: 24, color: '#e0e0e0', height: 'calc(100vh - 60px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div><h1 style={{ fontSize: 24, fontWeight: 700 }}>🐛 Debug Console</h1><p style={{ color: '#888' }}>{logs.length} log entries</p></div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={loadLogs} style={{ padding: '6px 14px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>🔄 Refresh</button>
          <button onClick={exportLogs} style={{ padding: '6px 14px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>📤 Export</button>
          <button onClick={clearLogs} style={{ padding: '6px 14px', background: '#ef4444', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>🗑 Clear</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search logs..." style={{ flex: 1, padding: '6px 10px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0', fontSize: 13 }} />
        <select value={levelFilter} onChange={e => setLevelFilter(e.target.value)} style={{ padding: '6px 8px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0', fontSize: 13 }}>
          {levels.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <select value={moduleFilter} onChange={e => setModuleFilter(e.target.value)} style={{ padding: '6px 8px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0', fontSize: 13 }}>
          {modules.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#888', fontSize: 12, cursor: 'pointer' }}>
          <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} /> Auto-scroll
        </label>
      </div>

      {/* Log Entries */}
      <div style={{ flex: 1, overflow: 'auto', background: '#0a0a0f', borderRadius: 8, border: '1px solid #222', fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>
        {filtered.map(entry => (
          <div key={entry.id} onClick={() => setShowDetails(showDetails === entry.id ? null : entry.id)} style={{ padding: '6px 12px', borderBottom: '1px solid #1a1a2a', cursor: 'pointer', display: 'flex', gap: 12, alignItems: 'flex-start', background: showDetails === entry.id ? '#1a1a2e' : 'transparent' }}
            onMouseEnter={e => { if (showDetails !== entry.id) e.currentTarget.style.background = '#111122'; }}
            onMouseLeave={e => { if (showDetails !== entry.id) e.currentTarget.style.background = 'transparent'; }}>
            <span style={{ color: '#555', minWidth: 80, flexShrink: 0 }}>{entry.recorded_at ? new Date(entry.recorded_at).toLocaleTimeString() : '--:--:--'}</span>
            <span style={{ color: levelColors[entry.level] || '#888', minWidth: 16, flexShrink: 0 }}>{levelIcons[entry.level] || '?'}</span>
            <span style={{ color: '#6366f1', minWidth: 100, flexShrink: 0 }}>{entry.module}</span>
            <span style={{ flex: 1, color: entry.level === 'error' || entry.level === 'critical' ? '#ef4444' : '#ccc' }}>{entry.message}</span>
            {showDetails === entry.id && entry.metadata && (
              <div style={{ gridColumn: 'span 4', marginTop: 8, padding: 8, background: '#12121e', borderRadius: 4, fontSize: 11, color: '#888', whiteSpace: 'pre-wrap' }}>
                {typeof entry.metadata === 'string' ? entry.metadata : JSON.stringify(entry.metadata, null, 2)}
              </div>
            )}
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No log entries found</div>}
      </div>

      {/* Status Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: '#555' }}>
        <span>{filtered.length} entries (filtered from {logs.length})</span>
        <span>Auto-refresh: 5s • {autoScroll ? 'Auto-scroll ON' : ''}</span>
      </div>
    </div>
  );
}
