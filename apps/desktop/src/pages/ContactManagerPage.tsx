import { useState, useEffect } from 'react';

interface Contact { id: string; name: string; email: string; phone: string; company: string; role: string; notes: string; tags: string[]; avatar_url: string; created_at: string; }

export default function ContactManagerPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [search, setSearch] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [newContact, setNewContact] = useState({ name: '', email: '', phone: '', company: '', role: '', notes: '', tags: '' });

  useEffect(() => { loadContacts(); }, []);

  async function loadContacts() {
    try { const r = await fetch('/api/v1/features/contacts'); if (r.ok) setContacts(await r.json()); } catch { /* */ }
  }

  async function addContact() {
    if (!newContact.name) return;
    try { await fetch('/api/v1/features/contacts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...newContact, tags: newContact.tags.split(',').map(t => t.trim()).filter(Boolean) }) }); setNewContact({ name: '', email: '', phone: '', company: '', role: '', notes: '', tags: '' }); setShowAdd(false); loadContacts(); } catch { /* */ }
  }

  async function deleteContact(id: string) {
    try { await fetch(`/api/v1/features/contacts/${id}`, { method: 'DELETE' }); setSelectedContact(null); loadContacts(); } catch { /* */ }
  }

  const filtered = contacts.filter(c => !search || c.name.toLowerCase().includes(search.toLowerCase()) || c.email.toLowerCase().includes(search.toLowerCase()) || c.company.toLowerCase().includes(search.toLowerCase()));
  const initials = (name: string) => name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 60px)', color: '#e0e0e0' }}>
      {/* Contact List */}
      <div style={{ width: selectedContact ? 360 : '100%', maxWidth: 480, borderRight: selectedContact ? '1px solid #333' : 'none', display: 'flex', flexDirection: 'column', background: '#0d1117' }}>
        <div style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div><h1 style={{ fontSize: 24, fontWeight: 700 }}>👥 Contacts</h1><p style={{ color: '#888', fontSize: 14 }}>{contacts.length} contacts</p></div>
            <button onClick={() => setShowAdd(!showAdd)} style={{ padding: '8px 16px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>+ Add</button>
          </div>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search contacts..." style={{ width: '100%', padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0', marginBottom: 12 }} />
        </div>

        {showAdd && (
          <div style={{ padding: '0 20px 16px', background: '#1e1e2e', margin: '0 20px', borderRadius: 8 }}>
            <div style={{ display: 'grid', gap: 8, padding: 12 }}>
              {['name', 'email', 'phone', 'company', 'role'].map(f => <input key={f} placeholder={f.charAt(0).toUpperCase() + f.slice(1)} value={(newContact as any)[f]} onChange={e => setNewContact(p => ({ ...p, [f]: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />)}
              <input placeholder="Tags (comma-separated)" value={newContact.tags} onChange={e => setNewContact(p => ({ ...p, tags: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={addContact} style={{ flex: 1, padding: 8, background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Save</button>
                <button onClick={() => setShowAdd(false)} style={{ padding: 8, background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
              </div>
            </div>
          </div>
        )}

        <div style={{ flex: 1, overflow: 'auto', padding: '0 12px' }}>
          {filtered.map(c => (
            <div key={c.id} onClick={() => setSelectedContact(c)} style={{ padding: '12px', borderRadius: 8, cursor: 'pointer', background: selectedContact?.id === c.id ? '#1e1e3a' : 'transparent', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 12, transition: 'background 0.15s' }}
              onMouseEnter={e => { if (selectedContact?.id !== c.id) e.currentTarget.style.background = '#1e1e2e'; }}
              onMouseLeave={e => { if (selectedContact?.id !== c.id) e.currentTarget.style.background = 'transparent'; }}>
              <div style={{ width: 40, height: 40, borderRadius: '50%', background: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 600, flexShrink: 0 }}>{initials(c.name)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{c.name}</div>
                <div style={{ fontSize: 12, color: '#888', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.company || c.email || 'No details'}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Contact Detail */}
      {selectedContact && (
        <div style={{ flex: 1, overflow: 'auto', padding: 32 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20, marginBottom: 32 }}>
            <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, fontWeight: 700 }}>{initials(selectedContact.name)}</div>
            <div style={{ flex: 1 }}>
              <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>{selectedContact.name}</h2>
              <p style={{ color: '#888' }}>{selectedContact.role || 'No role'} {selectedContact.company ? `at ${selectedContact.company}` : ''}</p>
            </div>
            <button onClick={() => deleteContact(selectedContact.id)} style={{ padding: '6px 12px', background: '#ef4444', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Delete</button>
          </div>

          <div style={{ display: 'grid', gap: 16 }}>
            {[{ icon: '📧', label: 'Email', value: selectedContact.email }, { icon: '📱', label: 'Phone', value: selectedContact.phone }, { icon: '🏢', label: 'Company', value: selectedContact.company }, { icon: '💼', label: 'Role', value: selectedContact.role }].filter(f => f.value).map(field => (
              <div key={field.label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 18, width: 32 }}>{field.icon}</span>
                <div><div style={{ fontSize: 12, color: '#888' }}>{field.label}</div><div style={{ fontSize: 14 }}>{field.value}</div></div>
              </div>
            ))}
            {selectedContact.notes && <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, padding: 16 }}><div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>Notes</div><div style={{ fontSize: 14, whiteSpace: 'pre-wrap' }}>{selectedContact.notes}</div></div>}
            {selectedContact.tags?.length > 0 && <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{selectedContact.tags.map(t => <span key={t} style={{ background: '#333', padding: '4px 10px', borderRadius: 6, fontSize: 12 }}>{t}</span>)}</div>}
          </div>
        </div>
      )}
    </div>
  );
}
