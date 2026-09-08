import { useState, useEffect } from 'react';

interface ReadingItem { id: string; url: string; title: string; description: string; status: string; priority: number; tags: string[]; estimated_read_time: number; created_at: string; completed_at: string; }

export default function ReadingListPage() {
  const [items, setItems] = useState<ReadingItem[]>([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('unread');
  const [showAdd, setShowAdd] = useState(false);
  const [newItem, setNewItem] = useState({ url: '', title: '', description: '', priority: 0 });
  const [toast, setToast] = useState('');

  useEffect(() => { loadItems(); }, []);

  async function loadItems() {
    try { const r = await fetch('/api/v1/features/reading-list'); if (r.ok) setItems(await r.json()); } catch { /* */ }
  }

  async function addItem() {
    if (!newItem.url) return;
    try {
      await fetch('/api/v1/features/reading-list', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newItem) });
      setNewItem({ url: '', title: '', description: '', priority: 0 }); setShowAdd(false); loadItems();
    } catch { /* */ }
  }

  async function markComplete(id: string) {
    try { await fetch(`/api/v1/features/reading-list/${id}/complete`, { method: 'POST' }); loadItems(); } catch { /* */ }
  }

  async function deleteItem(id: string) {
    try { await fetch(`/api/v1/features/reading-list/${id}`, { method: 'DELETE' }); loadItems(); } catch { /* */ }
  }

  const filtered = items.filter(i => {
    const matchSearch = !search || i.title.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'all' || i.status === filter;
    return matchSearch && matchFilter;
  });

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 800, margin: '0 auto' }}>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, background: '#10b981', color: '#fff', padding: '8px 16px', borderRadius: 8, zIndex: 9999 }}>{toast}</div>}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div><h1 style={{ fontSize: 24, fontWeight: 700 }}>📚 Reading List</h1><p style={{ color: '#888', fontSize: 14 }}>{items.filter(i => i.status === 'unread').length} unread</p></div>
        <button onClick={() => setShowAdd(!showAdd)} style={{ padding: '8px 16px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>+ Add</button>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." style={{ flex: 1, padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
        {['all', 'unread', 'reading', 'completed'].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{ padding: '6px 12px', background: filter === f ? '#6366f1' : '#333', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 13 }}>{f}</button>
        ))}
      </div>

      {showAdd && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <input placeholder="URL" value={newItem.url} onChange={e => setNewItem(p => ({ ...p, url: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Title" value={newItem.title} onChange={e => setNewItem(p => ({ ...p, title: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Description" value={newItem.description} onChange={e => setNewItem(p => ({ ...p, description: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <select value={newItem.priority} onChange={e => setNewItem(p => ({ ...p, priority: +e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }}>
              <option value={0}>Low Priority</option><option value={1}>Medium Priority</option><option value={2}>High Priority</option>
            </select>
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={addItem} style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Save</button>
            <button onClick={() => setShowAdd(false)} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gap: 10 }}>
        {filtered.map(item => (
          <div key={item.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16, display: 'flex', gap: 14, alignItems: 'center' }}>
            <div style={{ width: 8, height: 40, borderRadius: 4, background: item.priority === 2 ? '#ef4444' : item.priority === 1 ? '#f59e0b' : '#10b981', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{item.title || item.url}</div>
              <div style={{ fontSize: 13, color: '#888' }}>{item.description || item.url}</div>
              {item.estimated_read_time > 0 && <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>~{item.estimated_read_time} min read</div>}
            </div>
            <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, background: item.status === 'completed' ? '#10b981' : item.status === 'reading' ? '#f59e0b' : '#333', color: '#fff' }}>{item.status}</span>
            {item.status !== 'completed' && <button onClick={() => markComplete(item.id)} style={{ background: '#10b981', border: 'none', borderRadius: 4, color: '#fff', padding: '4px 8px', cursor: 'pointer', fontSize: 12 }}>✓</button>}
            <button onClick={() => deleteItem(item.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>🗑</button>
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No items in your reading list</div>}
      </div>
    </div>
  );
}
