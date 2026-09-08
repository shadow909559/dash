import { useState, useEffect } from 'react';

interface MeetingNote { id: string; title: string; date: string; attendees: string[]; agenda: string; notes: string; action_items: string[]; tags: string[]; created_at: string; }

export default function MeetingNotesPage() {
  const [meetings, setMeetings] = useState<MeetingNote[]>([]);
  const [search, setSearch] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [newMeeting, setNewMeeting] = useState({ title: '', date: new Date().toISOString().split('T')[0], attendees: '', agenda: '', notes: '', action_items: '', tags: '' });

  useEffect(() => { loadMeetings(); }, []);

  async function loadMeetings() {
    try { const r = await fetch('/api/v1/features/meetings'); if (r.ok) setMeetings(await r.json()); } catch { /* */ }
  }

  async function addMeeting() {
    if (!newMeeting.title) return;
    const payload = { ...newMeeting, attendees: newMeeting.attendees.split(',').map(a => a.trim()).filter(Boolean), action_items: newMeeting.action_items.split('\n').filter(Boolean), tags: newMeeting.tags.split(',').map(t => t.trim()).filter(Boolean) };
    try {
      await fetch('/api/v1/features/meetings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      setNewMeeting({ title: '', date: new Date().toISOString().split('T')[0], attendees: '', agenda: '', notes: '', action_items: '', tags: '' }); setShowAdd(false); loadMeetings();
    } catch { /* */ }
  }

  async function deleteMeeting(id: string) {
    try { await fetch(`/api/v1/features/meetings/${id}`, { method: 'DELETE' }); loadMeetings(); } catch { /* */ }
  }

  const filtered = meetings.filter(m => !search || m.title.toLowerCase().includes(search.toLowerCase()) || m.notes.toLowerCase().includes(search.toLowerCase()));

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div><h1 style={{ fontSize: 24, fontWeight: 700 }}>📋 Meeting Notes</h1><p style={{ color: '#888' }}>{meetings.length} meetings</p></div>
        <button onClick={() => setShowAdd(!showAdd)} style={{ padding: '8px 16px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>+ New Meeting</button>
      </div>

      <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search meetings..." style={{ width: '100%', padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0', marginBottom: 20 }} />

      {showAdd && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <h3 style={{ marginBottom: 12 }}>New Meeting Note</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <input placeholder="Title" value={newMeeting.title} onChange={e => setNewMeeting(p => ({ ...p, title: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input type="date" value={newMeeting.date} onChange={e => setNewMeeting(p => ({ ...p, date: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Attendees (comma-separated)" value={newMeeting.attendees} onChange={e => setNewMeeting(p => ({ ...p, attendees: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Tags (comma-separated)" value={newMeeting.tags} onChange={e => setNewMeeting(p => ({ ...p, tags: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <textarea placeholder="Agenda" value={newMeeting.agenda} onChange={e => setNewMeeting(p => ({ ...p, agenda: e.target.value }))} style={{ gridColumn: 'span 2', padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0', minHeight: 60 }} />
            <textarea placeholder="Notes" value={newMeeting.notes} onChange={e => setNewMeeting(p => ({ ...p, notes: e.target.value }))} style={{ gridColumn: 'span 2', padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0', minHeight: 100 }} />
            <textarea placeholder="Action Items (one per line)" value={newMeeting.action_items} onChange={e => setNewMeeting(p => ({ ...p, action_items: e.target.value }))} style={{ gridColumn: 'span 2', padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0', minHeight: 60 }} />
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={addMeeting} style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Save</button>
            <button onClick={() => setShowAdd(false)} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gap: 12 }}>
        {filtered.map(m => (
          <div key={m.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div>
                <h3 style={{ fontSize: 18, marginBottom: 4 }}>{m.title}</h3>
                <div style={{ fontSize: 13, color: '#888' }}>📅 {m.date} • 👥 {m.attendees?.length || 0} attendees</div>
              </div>
              <button onClick={() => deleteMeeting(m.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>🗑</button>
            </div>
            {m.agenda && <div style={{ marginBottom: 12 }}><div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>Agenda</div><div style={{ fontSize: 14, background: '#12121e', padding: 12, borderRadius: 6 }}>{m.agenda}</div></div>}
            {m.notes && <div style={{ marginBottom: 12 }}><div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>Notes</div><div style={{ fontSize: 14, background: '#12121e', padding: 12, borderRadius: 6, whiteSpace: 'pre-wrap' }}>{m.notes}</div></div>}
            {m.action_items && m.action_items.length > 0 && <div><div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>Action Items</div><div style={{ display: 'grid', gap: 4 }}>{m.action_items.map((ai, i) => <div key={i} style={{ background: '#12121e', padding: '6px 12px', borderRadius: 4, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}><input type="checkbox" />{ai}</div>)}</div></div>}
            {m.tags?.length > 0 && <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>{m.tags.map(t => <span key={t} style={{ background: '#333', padding: '2px 8px', borderRadius: 4, fontSize: 11 }}>{t}</span>)}</div>}
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No meeting notes yet</div>}
      </div>
    </div>
  );
}
