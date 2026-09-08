import { useState, useEffect } from 'react';

interface Screenshot { id: string; url: string; title: string; width: number; height: number; created_at: string; }

export default function ScreenshotCapturePage() {
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [url, setUrl] = useState('');
  const [fullPage, setFullPage] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [selected, setSelected] = useState<Screenshot | null>(null);

  useEffect(() => { loadScreenshots(); }, []);

  async function loadScreenshots() {
    try { const r = await fetch('/api/v1/features/screenshots'); if (r.ok) setScreenshots(await r.json()); } catch { /* */ }
  }

  async function capture() {
    if (!url) return;
    setCapturing(true);
    try {
      const r = await fetch('/api/v1/features/screenshots/capture', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, full_page: fullPage }) });
      if (r.ok) { setUrl(''); loadScreenshots(); }
    } catch { /* */ }
    setCapturing(false);
  }

  async function deleteScreenshot(id: string) {
    try { await fetch(`/api/v1/features/screenshots/${id}`, { method: 'DELETE' }); setSelected(null); loadScreenshots(); } catch { /* */ }
  }

  return (
    <div style={{ padding: 24, color: '#e0e0e0' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>📸 Screenshot Capture</h1>
      <p style={{ color: '#888', marginBottom: 20 }}>Capture web pages as screenshots</p>

      <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <input value={url} onChange={e => setUrl(e.target.value)} placeholder="Enter URL to capture..." style={{ flex: 1, padding: '10px 14px', background: '#12121e', border: '1px solid #333', borderRadius: 8, color: '#e0e0e0' }} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#888', fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={fullPage} onChange={e => setFullPage(e.target.checked)} /> Full page
          </label>
          <button onClick={capture} disabled={capturing || !url} style={{ padding: '10px 20px', background: url && !capturing ? '#6366f1' : '#333', border: 'none', borderRadius: 8, color: '#fff', cursor: url && !capturing ? 'pointer' : 'default' }}>{capturing ? '⏳ Capturing...' : '📸 Capture'}</button>
        </div>
      </div>

      {selected && (
        <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3>{selected.title || 'Screenshot'}</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <a href={selected.url} download style={{ padding: '6px 12px', background: '#10b981', border: 'none', borderRadius: 6, color: '#fff', textDecoration: 'none', fontSize: 13 }}>⬇ Download</a>
              <button onClick={() => deleteScreenshot(selected.id)} style={{ padding: '6px 12px', background: '#ef4444', border: 'none', borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 13 }}>🗑</button>
              <button onClick={() => setSelected(null)} style={{ padding: '6px 12px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>✕</button>
            </div>
          </div>
          <div style={{ background: '#0a0a0f', borderRadius: 8, overflow: 'hidden', textAlign: 'center' }}>
            <img src={selected.url} alt={selected.title} style={{ maxWidth: '100%', maxHeight: 500 }} />
          </div>
          <div style={{ fontSize: 12, color: '#888', marginTop: 8 }}>{selected.width}×{selected.height} • {new Date(selected.created_at).toLocaleString()}</div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
        {screenshots.map(s => (
          <div key={s.id} onClick={() => setSelected(s)} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, overflow: 'hidden', cursor: 'pointer', transition: 'border-color 0.2s' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = '#6366f1')} onMouseLeave={e => (e.currentTarget.style.borderColor = '#333')}>
            <div style={{ height: 150, background: '#0a0a0f', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <img src={s.url} alt={s.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>
            <div style={{ padding: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{s.title || 'Untitled'}</div>
              <div style={{ fontSize: 11, color: '#888' }}>{s.width}×{s.height} • {new Date(s.created_at).toLocaleDateString()}</div>
            </div>
          </div>
        ))}
        {screenshots.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40, gridColumn: 'span 3' }}>No screenshots yet. Enter a URL above to capture one.</div>}
      </div>
    </div>
  );
}
