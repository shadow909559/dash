import { useState, useEffect } from 'react';

interface VaultEntry {
  id: string;
  title: string;
  username: string;
  password_encrypted: string;
  url: string;
  notes: string;
  category: string;
  tags: string[];
  favorite: boolean;
  created_at: string;
  updated_at: string;
}

export default function PasswordManagerPage() {
  const [entries, setEntries] = useState<VaultEntry[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [showAdd, setShowAdd] = useState(false);
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [newEntry, setNewEntry] = useState({ title: '', username: '', password: '', url: '', notes: '', category: 'general' });
  const [toast, setToast] = useState('');

  useEffect(() => { loadEntries(); }, []);

  async function loadEntries() {
    try {
      const r = await fetch('/api/v1/features/vault/entries');
      if (r.ok) setEntries(await r.json());
    } catch { /* ignore */ }
  }

  async function addEntry() {
    if (!newEntry.title || !newEntry.password) return;
    try {
      const r = await fetch('/api/v1/features/vault/entries', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newEntry),
      });
      if (r.ok) { setNewEntry({ title: '', username: '', password: '', url: '', notes: '', category: 'general' }); setShowAdd(false); loadEntries(); }
    } catch { /* ignore */ }
  }

  async function deleteEntry(id: string) {
    try { await fetch(`/api/v1/features/vault/entries/${id}`, { method: 'DELETE' }); loadEntries(); } catch { /* ignore */ }
  }

  function togglePassword(id: string) {
    setShowPasswords(prev => ({ ...prev, [id]: !prev[id] }));
  }

  function copyPassword(password: string) {
    navigator.clipboard.writeText(password);
    setToast('Password copied!');
    setTimeout(() => setToast(''), 2000);
  }

  async function generatePassword() {
    try {
      const r = await fetch('/api/v1/features/vault/generate-password');
      if (r.ok) { const d = await r.json(); setNewEntry(p => ({ ...p, password: d.password || d.generated })); }
    } catch { /* ignore */ }
  }

  const filtered = entries.filter(e => {
    const matchSearch = !search || e.title.toLowerCase().includes(search.toLowerCase()) || e.username.toLowerCase().includes(search.toLowerCase());
    const matchCat = category === 'all' || e.category === category;
    return matchSearch && matchCat;
  });

  const categories = ['all', ...new Set(entries.map(e => e.category))];

  return (
    <div style={{ padding: 24, color: '#e0e0e0' }}>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, background: '#10b981', color: '#fff', padding: '8px 16px', borderRadius: 8, zIndex: 9999, fontSize: 14 }}>{toast}</div>}
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>🔐 Password Manager</h1>
      <p style={{ color: '#888', marginBottom: 20 }}>Secure vault for your credentials</p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search vault..." style={{ flex: 1, minWidth: 200, padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
        <select value={category} onChange={e => setCategory(e.target.value)} style={{ padding: '8px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }}>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button onClick={() => setShowAdd(!showAdd)} style={{ padding: '8px 16px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>+ Add Entry</button>
      </div>

      {showAdd && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <h3 style={{ marginBottom: 12 }}>New Vault Entry</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <input placeholder="Title" value={newEntry.title} onChange={e => setNewEntry(p => ({ ...p, title: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Username" value={newEntry.username} onChange={e => setNewEntry(p => ({ ...p, username: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <div style={{ display: 'flex', gap: 8 }}>
              <input placeholder="Password" type="password" value={newEntry.password} onChange={e => setNewEntry(p => ({ ...p, password: e.target.value }))} style={{ flex: 1, padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
              <button onClick={generatePassword} style={{ padding: '8px 12px', background: '#8b5cf6', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>🎲</button>
            </div>
            <input placeholder="URL" value={newEntry.url} onChange={e => setNewEntry(p => ({ ...p, url: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <input placeholder="Category" value={newEntry.category} onChange={e => setNewEntry(p => ({ ...p, category: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
            <textarea placeholder="Notes" value={newEntry.notes} onChange={e => setNewEntry(p => ({ ...p, notes: e.target.value }))} style={{ padding: 8, background: '#12121e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0', minHeight: 60 }} />
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={addEntry} style={{ padding: '8px 16px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer' }}>Save</button>
            <button onClick={() => setShowAdd(false)} style={{ padding: '8px 16px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gap: 12 }}>
        {filtered.map(entry => (
          <div key={entry.id} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ width: 40, height: 40, borderRadius: 10, background: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>{entry.favorite ? '⭐' : '🔑'}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{entry.title}</div>
              <div style={{ color: '#888', fontSize: 13 }}>{entry.username} • {entry.category}</div>
            </div>
            <button onClick={() => togglePassword(entry.id)} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: 16 }}>{showPasswords[entry.id] ? '🙈' : '👁'}</button>
            <button onClick={() => copyPassword(entry.password_encrypted)} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: 16 }}>📋</button>
            <button onClick={() => deleteEntry(entry.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 16 }}>🗑</button>
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No vault entries yet. Add your first credential above.</div>}
      </div>
    </div>
  );
}
