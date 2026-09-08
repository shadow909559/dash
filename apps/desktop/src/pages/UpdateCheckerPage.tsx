import { useState, useEffect } from 'react';

interface UpdateInfo { version: string; release_date: string; release_notes: string; download_url: string; size: string; }

export default function UpdateCheckerPage() {
  const [currentVersion, setCurrentVersion] = useState('2.0.0');
  const [latestVersion, setLatestVersion] = useState<UpdateInfo | null>(null);
  const [checking, setChecking] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [autoUpdate, setAutoUpdate] = useState(true);
  const [changelog, setChangelog] = useState<{ version: string; date: string; changes: string[] }[]>([]);
  const [toast, setToast] = useState('');

  useEffect(() => { checkForUpdates(); loadChangelog(); }, []);

  async function checkForUpdates() {
    setChecking(true);
    try {
      const r = await fetch('/api/v1/features/updates/check');
      if (r.ok) { const data = await r.json(); setLatestVersion(data); }
    } catch { /* */ }
    setChecking(false);
  }

  async function performUpdate() {
    setUpdating(true);
    try {
      const r = await fetch('/api/v1/features/updates/install', { method: 'POST' });
      if (r.ok) { setToast('Update installed!'); setTimeout(() => setToast(''), 3000); }
    } catch { /* */ }
    setUpdating(false);
  }

  async function loadChangelog() {
    try { const r = await fetch('/api/v1/features/updates/changelog'); if (r.ok) setChangelog(await r.json()); } catch { /* */ }
  }

  const hasUpdate = latestVersion && latestVersion.version !== currentVersion;

  return (
    <div style={{ padding: 24, color: '#e0e0e0', maxWidth: 800, margin: '0 auto' }}>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, background: '#10b981', color: '#fff', padding: '8px 16px', borderRadius: 8, zIndex: 9999 }}>{toast}</div>}
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>🔄 Update Checker</h1>
      <p style={{ color: '#888', marginBottom: 20 }}>Keep DASH up to date</p>

      <div style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 12, padding: 24, marginBottom: 20, textAlign: 'center' }}>
        <div style={{ fontSize: 64, marginBottom: 16 }}>{hasUpdate ? '🔄' : '✅'}</div>
        <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 4 }}>DASH v{currentVersion}</div>
        <div style={{ color: '#888', marginBottom: 16 }}>
          {hasUpdate ? `Update available: v${latestVersion.version}` : 'You are up to date'}
        </div>
        {hasUpdate && (
          <div style={{ background: '#12121e', borderRadius: 8, padding: 16, marginBottom: 16, textAlign: 'left' }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Release Notes — v{latestVersion.version}</div>
            <div style={{ color: '#aaa', fontSize: 13, whiteSpace: 'pre-wrap' }}>{latestVersion.release_notes || 'No release notes available.'}</div>
            <div style={{ fontSize: 12, color: '#666', marginTop: 8 }}>Released: {latestVersion.release_date} • Size: {latestVersion.size}</div>
          </div>
        )}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button onClick={checkForUpdates} disabled={checking} style={{ padding: '10px 24px', background: '#333', border: 'none', borderRadius: 8, color: '#e0e0e0', cursor: 'pointer' }}>{checking ? '⏳ Checking...' : '🔍 Check for Updates'}</button>
          {hasUpdate && <button onClick={performUpdate} disabled={updating} style={{ padding: '10px 24px', background: '#6366f1', border: 'none', borderRadius: 8, color: '#fff', cursor: 'pointer' }}>{updating ? '⏳ Updating...' : '⬇ Install Update'}</button>}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3>Changelog</h3>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#888', cursor: 'pointer' }}>
          <input type="checkbox" checked={autoUpdate} onChange={e => setAutoUpdate(e.target.checked)} /> Auto-update
        </label>
      </div>

      <div style={{ display: 'grid', gap: 12 }}>
        {changelog.map(entry => (
          <div key={entry.version} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 10, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontWeight: 600 }}>v{entry.version}</span>
              <span style={{ fontSize: 12, color: '#888' }}>{entry.date}</span>
            </div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>{entry.changes.map((c, i) => <li key={i} style={{ fontSize: 13, color: '#aaa', marginBottom: 4 }}>{c}</li>)}</ul>
          </div>
        ))}
        {changelog.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>No changelog available</div>}
      </div>
    </div>
  );
}
