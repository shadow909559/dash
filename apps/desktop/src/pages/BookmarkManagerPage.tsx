import { useState, useEffect } from 'react';

interface Bookmark { id: string; url: string; title: string; description: string; favicon: string; tags: string[]; folder: string; ai_summary: string; created_at: string; }

export default function BookmarkManagerPage() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [search, setSearch] = useState('');
  const [folder, setFolder] = useState('/');
  const [showAdd, setShowAdd] = useState(false);
  const [newBm, setNewBm] = useState({ url: '', title: '', description: '', tags: '', folder: '/' });
  const [toast, setToast] = useState('');

  useEffect(() => { loadBookmarks(); }, []);

  async function loadBookmarks() {
    try { const r = await fetch('/api/v1/features/browser/bookmarks'); if (r.ok) setBookmarks(await r.json()); } catch { /* */ }
  }

  async function addBookmark() {
    if (!newBm.url || !newBm.title) return;
    try {
      await fetch('/api/v1/features/browser/bookmarks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newBm, tags: newBm.tags.split(',').map(t => t.trim()).filter(Boolean) }) });
      setNewBm({ url: '', title: '', description: '', tags: '', folder: '/' }); setShowAdd(false); loadBookmarks();
    } catch { /* */ }
  }

  async function deleteBookmark(id: string) {
    try { await fetch(`/api/v1/features/browser/bookmarks/${id}`, { method: 'DELETE' }); loadBookmarks(); } catch { /* */ }
  }

  function openUrl(url: string) { window.open(url, '_blank'); }

  const filtered = bookmarks.filter(b => (!search || b.title.toLowerCase().includes(search.toLowerCase()) || b.url.toLowerCase().includes(search.toLowerCase())) && (folder === '/' || b.folder === folder));
  const folders = ['/', ...new Set(bookmarks.map(b => b.folder))];

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 900, margin: '0 auto' }}>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, background: '#10b981', color: '#fff', padding: '8px 16px', borderRadius: 8, zIndex: 9999 }}>{toast}</div>}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div><h1 style={{ fontSize: 24, fontWeight: 700 }}>🔖 Bookmarks</h1><p style={{ color: '#888', fontSize: 14 }}>{bookmarks.length} saved</p></div>
        <button onClick={() => setShowAdd(!showAdd)} style={{ padding: '8px 16px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>+ Add</button>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search bookmarks..." style={{ flex: 1, padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
        <select value={folder} onChange={e => setFolder(e.target.value)} style={{ padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }}>
          {folders.map(f => <option key={f} value={f}>{f}</option>)}
        </select>
      </div>

      {showAdd && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <input placeholder="URL" value={newBm.url} onChange={e => setNewBm(p => ({ ...p, url: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Title" value={newBm.title} onChange={e => setNewBm(p => ({ ...p, title: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Description" value={newBm.description} onChange={e => setNewBm(p => ({ ...p, description: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Tags (comma-separated)" value={newBm.tags} onChange={e => setNewBm(p => ({ ...p, tags: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Folder" value={newBm.folder} onChange={e => setNewBm(p => ({ ...p, folder: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={addBookmark} style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Save</button>
            <button onClick={() => setShowAdd(false)} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gap: 10 }}>
        {filtered.map(bm => (
          <div key={bm.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16, display: 'flex', gap: 14, alignItems: 'flex-start' }}>
            <div style={{ width: 36, height: 36, borderRadius: 8, background: '#333', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>🔖</div>
            <div style={{ flex: 1 }}>
              <div onClick={() => openUrl(bm.url)} style={{ fontWeight: 600, cursor: 'pointer', color: '#6366f1', marginBottom: 4 }}>{bm.title}</div>
              <div style={{ fontSize: 13, color: '#888', wordBreak: 'break-all' }}>{bm.url}</div>
              {bm.description && <div style={{ fontSize: 13, color: '#aaa', marginTop: 4 }}>{bm.description}</div>}
              {bm.ai_summary && <div style={{ fontSize: 12, color: '#10b981', marginTop: 4, fontStyle: 'italic' }}>AI: {bm.ai_summary}</div>}
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>{bm.tags.map(t => <span key={t} style={{ background: '#333', padding: '2px 8px', borderRadius: 4, fontSize: 11, color: '#aaa' }}>{t}</span>)}</div>
            </div>
            <button onClick={() => deleteBookmark(bm.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>🗑</button>
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No bookmarks found</div>}
      </div>
    </div>
  );
}
