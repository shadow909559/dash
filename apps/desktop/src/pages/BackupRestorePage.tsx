import { useState, useEffect } from 'react';

interface Backup { id: string; name: string; file_path: string; size_bytes: number; tables_included: string[]; created_at: string; notes: string; }

export default function BackupRestorePage() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [creating, setCreating] = useState(false);
  const [backupName, setBackupName] = useState('');
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState('');

  useEffect(() => { loadBackups(); }, []);

  async function loadBackups() {
    try { const r = await fetch('/api/v1/phase3/archives'); if (r.ok) setBackups(await r.json()); } catch { /* */ }
  }

  async function createBackup() {
    setCreating(true);
    try {
      const r = await fetch('/api/v1/phase3/archives', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: backupName || `backup-${Date.now()}`, tables: Array.from(selectedTables) }) });
      if (r.ok) { setBackupName(''); loadBackups(); setToast('Backup created!'); setTimeout(() => setToast(''), 3000); }
    } catch { /* */ }
    setCreating(false);
  }

  async function restoreBackup(id: string) {
    if (!confirm('Restore this backup? This will overwrite current data.')) return;
    try {
      const r = await fetch(`/api/v1/phase3/archives/${id}/restore`, { method: 'POST' });
      if (r.ok) { setToast('Backup restored!'); setTimeout(() => setToast(''), 3000); }
    } catch { /* */ }
  }

  async function deleteBackup(id: string) {
    try { await fetch(`/api/v1/phase3/archives/${id}`, { method: 'DELETE' }); loadBackups(); } catch { /* */ }
  }

  function formatSize(bytes: number) { if (bytes < 1024) return `${bytes} B`; if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`; return `${(bytes / (1024 * 1024)).toFixed(1)} MB`; }

  const tables = ['workflows', 'vault_entries', 'contacts', 'bookmarks', 'reminders', 'time_entries', 'meeting_notes', 'action_items', 'sprints', 'calendar_events'];

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 800, margin: '0 auto' }}>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, background: '#10b981', color: '#fff', padding: '8px 16px', borderRadius: 8, zIndex: 9999 }}>{toast}</div>}
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>💾 Backup & Restore</h1>
      <p style={{ color: '#888', marginBottom: 20 }}>Create backups and restore previous states</p>

      <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <h3 style={{ marginBottom: 12 }}>Create New Backup</h3>
        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          <input value={backupName} onChange={e => setBackupName(e.target.value)} placeholder="Backup name (optional)" style={{ flex: 1, padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
          <button onClick={createBackup} disabled={creating} style={{ padding: '8px 20px', background: creating ? '#333' : '#6366f1', border: 'none', borderRadius: 6, color: '#fff', cursor: creating ? 'default' : 'pointer' }}>{creating ? '⏳ Creating...' : '💾 Backup Now'}</button>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {tables.map(t => (
            <label key={t} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 8px', background: selectedTables.has(t) ? '#6366f1' : '#333', borderRadius: 4, fontSize: 12, cursor: 'pointer' }}>
              <input type="checkbox" checked={selectedTables.has(t)} onChange={e => { const next = new Set(selectedTables); e.target.checked ? next.add(t) : next.delete(t); setSelectedTables(next); }} style={{ display: 'none' }} />
              {t}
            </label>
          ))}
        </div>
      </div>

      <h3 style={{ marginBottom: 12 }}>Backup History ({backups.length})</h3>
      <div style={{ display: 'grid', gap: 10 }}>
        {backups.map(b => (
          <div key={b.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16, display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 48, height: 48, borderRadius: 10, background: '#333', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }}>💾</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{b.name}</div>
              <div style={{ fontSize: 12, color: '#888' }}>
                {formatSize(b.size_bytes)} • {b.tables_included?.length || 0} tables • {new Date(b.created_at).toLocaleString()}
              </div>
            </div>
            <button onClick={() => restoreBackup(b.id)} style={{ padding: '6px 14px', background: '#f59e0b', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 13 }}>🔄 Restore</button>
            <button onClick={() => deleteBackup(b.id)} style={{ padding: '6px 10px', background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>🗑</button>
          </div>
        ))}
        {backups.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No backups yet. Create your first backup above.</div>}
      </div>
    </div>
  );
}
