import { useState, useEffect } from 'react';

interface SprintItem { id: string; sprint_id: string; title: string; description: string; status: string; story_points: number; assignee: string; tags: string[]; }
interface Sprint { id: string; name: string; goal: string; start_date: string; end_date: string; status: string; }

export default function SprintBoardPage() {
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [items, setItems] = useState<SprintItem[]>([]);
  const [activeSprint, setActiveSprint] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [newItem, setNewItem] = useState({ title: '', description: '', story_points: 1, assignee: '' });
  const statuses = ['backlog', 'todo', 'in-progress', 'review', 'done'];

  useEffect(() => { loadSprints(); loadItems(); }, []);

  async function loadSprints() {
    try { const r = await fetch('/api/v1/phase4/sprints'); if (r.ok) { const data = await r.json(); setSprints(data); if (data.length > 0 && !activeSprint) setActiveSprint(data[0].id); } } catch { /* */ }
  }
  async function loadItems() {
    try { const r = await fetch('/api/v1/phase4/sprint-items'); if (r.ok) setItems(await r.json()); } catch { /* */ }
  }
  async function createSprint() {
    const name = `Sprint ${sprints.length + 1}`;
    const now = new Date(); const end = new Date(now.getTime() + 14 * 86400000);
    try { await fetch('/api/v1/phase4/sprints', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, start_date: now.toISOString(), end_date: end.toISOString() }) }); loadSprints(); } catch { /* */ }
  }
  async function addItem() {
    if (!newItem.title) return;
    try { await fetch('/api/v1/phase4/sprint-items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newItem, sprint_id: activeSprint }) }); setNewItem({ title: '', description: '', story_points: 1, assignee: '' }); setShowAdd(false); loadItems(); } catch { /* */ }
  }
  async function moveItem(id: string, status: string) {
    try { await fetch(`/api/v1/phase4/sprint-items/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) }); loadItems(); } catch { /* */ }
  }
  async function deleteItem(id: string) {
    try { await fetch(`/api/v1/phase4/sprint-items/${id}`, { method: 'DELETE' }); loadItems(); } catch { /* */ }
  }

  const sprintItems = items.filter(i => i.sprint_id === activeSprint);
  const totalPoints = sprintItems.reduce((s, i) => s + i.story_points, 0);
  const donePoints = sprintItems.filter(i => i.status === 'done').reduce((s, i) => s + i.story_points, 0);

  return (
    <div style={{ padding: 24, color: '#e0e0e0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div><h1 style={{ fontSize: 24, fontWeight: 700 }}>🏃 Sprint Board</h1><p style={{ color: '#888' }}>{sprintItems.length} items • {donePoints}/{totalPoints} points</p></div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={createSprint} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 8, color: '#e0e0e0', cursor: 'pointer' }}>+ New Sprint</button>
          <button onClick={() => setShowAdd(true)} style={{ padding: '8px 16px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>+ Add Item</button>
        </div>
      </div>

      {/* Sprint Selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {sprints.map(s => (
          <button key={s.id} onClick={() => setActiveSprint(s.id)} style={{ padding: '6px 14px', background: activeSprint === s.id ? '#6366f1' : '#333', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>{s.name}</button>
        ))}
      </div>

      {/* Progress Bar */}
      <div style={{ height: 6, background: '#333', borderRadius: 3, marginBottom: 20 }}>
        <div style={{ height: '100%', background: '#10b981', borderRadius: 3, width: `${totalPoints ? (donePoints / totalPoints) * 100 : 0}%`, transition: 'width 0.3s' }} />
      </div>

      {showAdd && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 16, marginBottom: 20, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <input placeholder="Title" value={newItem.title} onChange={e => setNewItem(p => ({ ...p, title: e.target.value }))} style={{ flex: 1, minWidth: 150, padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
          <input placeholder="Assignee" value={newItem.assignee} onChange={e => setNewItem(p => ({ ...p, assignee: e.target.value }))} style={{ width: 120, padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
          <select value={newItem.story_points} onChange={e => setNewItem(p => ({ ...p, story_points: +e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }}>
            {[1, 2, 3, 5, 8, 13].map(p => <option key={p} value={p}>{p} pts</option>)}
          </select>
          <button onClick={addItem} style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Add</button>
          <button onClick={() => setShowAdd(false)} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
        </div>
      )}

      {/* Kanban Board */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, minHeight: 400 }}>
        {statuses.map(status => (
          <div key={status} style={{ background: '#12121e', borderRadius: 10, padding: 12, border: '1px solid #222' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#888', textTransform: 'uppercase', marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
              <span>{status}</span>
              <span style={{ background: '#333', padding: '1px 6px', borderRadius: 4 }}>{sprintItems.filter(i => i.status === status).length}</span>
            </div>
            {sprintItems.filter(i => i.status === status).map(item => (
              <div key={item.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, padding: 12, marginBottom: 8 }}>
                <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>{item.title}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: '#888' }}>{item.assignee || 'Unassigned'}</span>
                  <span style={{ background: '#333', padding: '1px 6px', borderRadius: 4, fontSize: 11 }}>{item.story_points}pt</span>
                </div>
                <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
                  {statuses.filter(s => s !== status).slice(0, 2).map(s => (
                    <button key={s} onClick={() => moveItem(item.id, s)} style={{ padding: '2px 6px', background: '#333', border: 'none', borderRadius: 3, color: '#aaa', cursor: 'pointer', fontSize: 10 }}>→ {s.split('-')[0]}</button>
                  ))}
                  <button onClick={() => deleteItem(item.id)} style={{ marginLeft: 'auto', padding: '2px 6px', background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 10 }}>🗑</button>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
