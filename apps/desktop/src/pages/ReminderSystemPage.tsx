import { useState, useEffect } from 'react';

interface Reminder { id: string; title: string; description: string; due_date: string; priority: number; completed: boolean; recurrence: string; tags: string[]; created_at: string; }

export default function ReminderSystemPage() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('pending');
  const [showAdd, setShowAdd] = useState(false);
  const [newReminder, setNewReminder] = useState({ title: '', description: '', due_date: '', priority: 0, recurrence: '', tags: '' });
  const [toast, setToast] = useState('');

  useEffect(() => { loadReminders(); }, []);

  async function loadReminders() {
    try { const r = await fetch('/api/v1/phase4/reminders'); if (r.ok) setReminders(await r.json()); } catch { /* */ }
  }

  async function addReminder() {
    if (!newReminder.title) return;
    try { await fetch('/api/v1/phase4/reminders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newReminder, tags: newReminder.tags.split(',').map(t => t.trim()).filter(Boolean) }) }); setNewReminder({ title: '', description: '', due_date: '', priority: 0, recurrence: '', tags: '' }); setShowAdd(false); loadReminders(); } catch { /* */ }
  }

  async function completeReminder(id: string) {
    try { await fetch(`/api/v1/phase4/reminders/${id}/complete`, { method: 'POST' }); loadReminders(); } catch { /* */ }
  }

  async function deleteReminder(id: string) {
    try { await fetch(`/api/v1/phase4/reminders/${id}`, { method: 'DELETE' }); loadReminders(); } catch { /* */ }
  }

  function isOverdue(d: string) { return d && new Date(d) < new Date(); }
  function formatDue(d: string) {
    if (!d) return 'No due date';
    const diff = new Date(d).getTime() - Date.now();
    if (diff < 0) return `Overdue by ${Math.ceil(-diff / 86400000)} days`;
    if (diff < 3600000) return `Due in ${Math.ceil(diff / 60000)} min`;
    if (diff < 86400000) return `Due in ${Math.ceil(diff / 3600000)} hours`;
    return `Due in ${Math.ceil(diff / 86400000)} days`;
  }

  const filtered = reminders.filter(r => {
    const matchSearch = !search || r.title.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'all' || (filter === 'pending' && !r.completed) || (filter === 'completed' && r.completed) || (filter === 'overdue' && isOverdue(r.due_date) && !r.completed);
    return matchSearch && matchFilter;
  });

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 800, margin: '0 auto' }}>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, background: '#10b981', color: '#fff', padding: '8px 16px', borderRadius: 8, zIndex: 9999 }}>{toast}</div>}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div><h1 style={{ fontSize: 24, fontWeight: 700 }}>🔔 Reminders</h1><p style={{ color: '#888' }}>{reminders.filter(r => !r.completed).length} active • {reminders.filter(r => isOverdue(r.due_date) && !r.completed).length} overdue</p></div>
        <button onClick={() => setShowAdd(!showAdd)} style={{ padding: '8px 16px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>+ Add</button>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search reminders..." style={{ flex: 1, padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
        {['pending', 'overdue', 'completed', 'all'].map(f => <button key={f} onClick={() => setFilter(f)} style={{ padding: '6px 12px', background: filter === f ? '#6366f1' : '#333', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 13 }}>{f}</button>)}
      </div>

      {showAdd && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <input placeholder="Title" value={newReminder.title} onChange={e => setNewReminder(p => ({ ...p, title: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input type="datetime-local" value={newReminder.due_date} onChange={e => setNewReminder(p => ({ ...p, due_date: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Description" value={newReminder.description} onChange={e => setNewReminder(p => ({ ...p, description: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <select value={newReminder.priority} onChange={e => setNewReminder(p => ({ ...p, priority: +e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }}>
              <option value={0}>Low Priority</option><option value={1}>Medium</option><option value={2}>High</option><option value={3}>Urgent</option>
            </select>
            <select value={newReminder.recurrence} onChange={e => setNewReminder(p => ({ ...p, recurrence: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }}>
              <option value="">No repeat</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option>
            </select>
            <input placeholder="Tags (comma-separated)" value={newReminder.tags} onChange={e => setNewReminder(p => ({ ...p, tags: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={addReminder} style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Save</button>
            <button onClick={() => setShowAdd(false)} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gap: 8 }}>
        {filtered.sort((a, b) => b.priority - a.priority).map(r => (
          <div key={r.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16, display: 'flex', alignItems: 'center', gap: 14, opacity: r.completed ? 0.5 : 1 }}>
            <div style={{ width: 8, height: 40, borderRadius: 4, background: r.priority >= 3 ? '#ef4444' : r.priority === 2 ? '#f59e0b' : r.priority === 1 ? '#6366f1' : '#10b981', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, textDecoration: r.completed ? 'line-through' : 'none' }}>{r.title}</div>
              <div style={{ fontSize: 12, color: isOverdue(r.due_date) && !r.completed ? '#ef4444' : '#888', marginTop: 2 }}>
                🕐 {formatDue(r.due_date)}
                {r.recurrence && <span> • 🔄 {r.recurrence}</span>}
              </div>
              {r.description && <div style={{ fontSize: 13, color: '#aaa', marginTop: 4 }}>{r.description}</div>}
            </div>
            {!r.completed && <button onClick={() => completeReminder(r.id)} style={{ background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', padding: '6px 12px', cursor: 'pointer', fontSize: 13 }}>✓ Done</button>}
            <button onClick={() => deleteReminder(r.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 16 }}>🗑</button>
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No reminders {filter !== 'all' ? `with filter "${filter}"` : ''}</div>}
      </div>
    </div>
  );
}
