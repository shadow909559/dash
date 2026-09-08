import { useState, useEffect } from 'react';

interface ActionItem { id: string; title: string; description: string; assignee: string; status: string; priority: number; due_date: string; source: string; tags: string[]; created_at: string; completed_at: string; }

export default function ActionItemsPage() {
  const [items, setItems] = useState<ActionItem[]>([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('pending');
  const [showAdd, setShowAdd] = useState(false);
  const [newItem, setNewItem] = useState({ title: '', description: '', assignee: '', priority: 0, due_date: '', source: 'manual', tags: '' });

  useEffect(() => { loadItems(); }, []);

  async function loadItems() {
    try { const r = await fetch('/api/v1/phase4/action-items'); if (r.ok) setItems(await r.json()); } catch { /* */ }
  }

  async function addItem() {
    if (!newItem.title) return;
    try { await fetch('/api/v1/phase4/action-items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newItem, tags: newItem.tags.split(',').map(t => t.trim()).filter(Boolean) }) }); setNewItem({ title: '', description: '', assignee: '', priority: 0, due_date: '', source: 'manual', tags: '' }); setShowAdd(false); loadItems(); } catch { /* */ }
  }

  async function completeItem(id: string) {
    try { await fetch(`/api/v1/phase4/action-items/${id}/complete`, { method: 'POST' }); loadItems(); } catch { /* */ }
  }

  async function deleteItem(id: string) {
    try { await fetch(`/api/v1/phase4/action-items/${id}`, { method: 'DELETE' }); loadItems(); } catch { /* */ }
  }

  const filtered = items.filter(i => {
    const matchSearch = !search || i.title.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'all' || i.status === filter;
    return matchSearch && matchFilter;
  });

  const isOverdue = (d: string) => d && new Date(d) < new Date();

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 800, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div><h1 style={{ fontSize: 24, fontWeight: 700 }}>✅ Action Items</h1><p style={{ color: '#888' }}>{items.filter(i => i.status === 'pending').length} pending • {items.filter(i => isOverdue(i.due_date) && i.status === 'pending').length} overdue</p></div>
        <button onClick={() => setShowAdd(!showAdd)} style={{ padding: '8px 16px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>+ Add</button>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." style={{ flex: 1, padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
        {['pending', 'completed', 'all'].map(f => <button key={f} onClick={() => setFilter(f)} style={{ padding: '6px 12px', background: filter === f ? '#6366f1' : '#333', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 13 }}>{f}</button>)}
      </div>

      {showAdd && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <input placeholder="Title" value={newItem.title} onChange={e => setNewItem(p => ({ ...p, title: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Assignee" value={newItem.assignee} onChange={e => setNewItem(p => ({ ...p, assignee: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input type="date" value={newItem.due_date} onChange={e => setNewItem(p => ({ ...p, due_date: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <select value={newItem.priority} onChange={e => setNewItem(p => ({ ...p, priority: +e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }}>
              <option value={0}>Low</option><option value={1}>Medium</option><option value={2}>High</option>
            </select>
            <input placeholder="Description" value={newItem.description} onChange={e => setNewItem(p => ({ ...p, description: e.target.value }))} style={{ gridColumn: 'span 2', padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={addItem} style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Save</button>
            <button onClick={() => setShowAdd(false)} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gap: 8 }}>
        {filtered.map(item => (
          <div key={item.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16, display: 'flex', alignItems: 'center', gap: 14, opacity: item.status === 'completed' ? 0.6 : 1 }}>
            <div style={{ width: 8, height: 40, borderRadius: 4, background: item.priority === 2 ? '#ef4444' : item.priority === 1 ? '#f59e0b' : '#10b981', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, textDecoration: item.status === 'completed' ? 'line-through' : 'none' }}>{item.title}</div>
              <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                {item.assignee && `👤 ${item.assignee} • `}
                {item.due_date && <span style={{ color: isOverdue(item.due_date) && item.status === 'pending' ? '#ef4444' : '#888' }}>📅 {item.due_date}</span>}
                {item.source && item.source !== 'manual' && ` • Source: ${item.source}`}
              </div>
            </div>
            <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, background: item.status === 'completed' ? '#10b981' : '#333', color: '#fff' }}>{item.status}</span>
            {item.status !== 'completed' && <button onClick={() => completeItem(item.id)} style={{ background: '#10b981', border: 'none', borderRadius: 4, color: '#fff', padding: '6px 10px', cursor: 'pointer' }}>✓</button>}
            <button onClick={() => deleteItem(item.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>🗑</button>
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No action items</div>}
      </div>
    </div>
  );
}
