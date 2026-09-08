import { useState, useEffect } from 'react';

interface ClipEntry { id: string; content: string; content_type: string; source_app: string; pinned: boolean; created_at: string; }

export default function ClipboardHistoryPage() {
  const [clips, setClips] = useState<ClipEntry[]>([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [toast, setToast] = useState('');

  useEffect(() => { loadClips(); }, []);

  async function loadClips() {
    try {
      const r = await fetch('/api/v1/features/clipboard/history');
      if (r.ok) setClips(await r.json());
    } catch { /* ignore */ }
  }

  async function togglePin(id: string, pinned: boolean) {
    try {
      await fetch(`/api/v1/features/clipboard/${id}/pin`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pinned: !pinned }) });
      loadClips();
    } catch { /* ignore */ }
  }

  async function deleteClip(id: string) {
    try { await fetch(`/api/v1/features/clipboard/${id}`, { method: 'DELETE' }); loadClips(); } catch { /* ignore */ }
  }

  function copyClip(content: string) {
    navigator.clipboard.writeText(content);
    setToast('Copied to clipboard!');
    setTimeout(() => setToast(''), 2000);
  }

  function clearAll() {
    if (confirm('Clear all clipboard history?')) { setClips([]); }
  }

  const filtered = clips.filter(c => {
    const matchSearch = !search || c.content.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'all' || (filter === 'pinned' && c.pinned) || (filter === c.content_type);
    return matchSearch && matchFilter;
  });

  const pinned = filtered.filter(c => c.pinned);
  const unpinned = filtered.filter(c => !c.pinned);

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 800, margin: '0 auto' }}>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, background: '#10b981', color: '#fff', padding: '8px 16px', borderRadius: 8, zIndex: 9999, fontSize: 14 }}>{toast}</div>}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>📋 Clipboard History</h1>
          <p style={{ color: '#888', fontSize: 14 }}>{clips.length} items saved</p>
        </div>
        <button onClick={clearAll} style={{ padding: '6px 14px', background: '#ef4444', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer', fontSize: 13 }}>Clear All</button>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search clipboard..." style={{ flex: 1, padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
        <select value={filter} onChange={e => setFilter(e.target.value)} style={{ padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }}>
          <option value="all">All</option>
          <option value="pinned">Pinned</option>
          <option value="text">Text</option>
          <option value="image">Images</option>
          <option value="code">Code</option>
        </select>
      </div>

      {pinned.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, color: '#888', marginBottom: 8 }}>⭐ Pinned</h3>
          {pinned.map(clip => <ClipCard key={clip.id} clip={clip} onCopy={copyClip} onTogglePin={togglePin} onDelete={deleteClip} />)}
        </div>
      )}

      <div>
        <h3 style={{ fontSize: 14, color: '#888', marginBottom: 8 }}>Recent</h3>
        {unpinned.map(clip => <ClipCard key={clip.id} clip={clip} onCopy={copyClip} onTogglePin={togglePin} onDelete={deleteClip} />)}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No clipboard entries found</div>}
      </div>
    </div>
  );
}

function ClipCard({ clip, onCopy, onTogglePin, onDelete }: { clip: ClipEntry; onCopy: (c: string) => void; onTogglePin: (id: string, p: boolean) => void; onDelete: (id: string) => void }) {
  return (
    <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 12, marginBottom: 8, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
      <div style={{ flex: 1, fontSize: 13, fontFamily: "'JetBrains Mono', monospace", whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 100, overflow: 'hidden', color: '#ccc' }}>
        {clip.content.slice(0, 500)}
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <button onClick={() => onCopy(clip.content)} style={{ background: '#333', border: 'none', borderRadius: 4, color: '#e0e0e0', padding: '4px 8px', cursor: 'pointer', fontSize: 12 }}>📋</button>
        <button onClick={() => onTogglePin(clip.id, clip.pinned)} style={{ background: clip.pinned ? '#f59e0b' : '#333', border: 'none', borderRadius: 4, color: '#fff', padding: '4px 8px', cursor: 'pointer', fontSize: 12 }}>⭐</button>
        <button onClick={() => onDelete(clip.id)} style={{ background: '#333', border: 'none', borderRadius: 4, color: '#ef4444', padding: '4px 8px', cursor: 'pointer', fontSize: 12 }}>🗑</button>
      </div>
      <div style={{ fontSize: 11, color: '#666', textAlign: 'right', whiteSpace: 'nowrap' }}>
        <div>{clip.content_type}</div>
        <div>{clip.source_app}</div>
      </div>
    </div>
  );
}
