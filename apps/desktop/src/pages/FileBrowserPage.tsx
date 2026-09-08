import { useState, useEffect } from 'react';

interface FileItem { name: string; path: string; type: 'file' | 'directory'; size: number; modified: string; }

export default function FileBrowserPage() {
  const [currentPath, setCurrentPath] = useState('/');
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [sortBy, setSortBy] = useState<'name' | 'size' | 'modified'>('name');
  const [searchQuery, setSearchQuery] = useState('');
  const [preview, setPreview] = useState<FileItem | null>(null);

  useEffect(() => { loadDir(currentPath); }, [currentPath]);

  async function loadDir(path: string) {
    try {
      const r = await fetch(`/api/v1/features/files/browse?path=${encodeURIComponent(path)}`);
      if (r.ok) { const data = await r.json(); setFiles(data.files || data.items || []); }
    } catch { setFiles([]); }
  }

  function navigate(item: FileItem) {
    if (item.type === 'directory') setCurrentPath(item.path);
    else setPreview(item);
  }

  function goUp() {
    const parts = currentPath.split('/').filter(Boolean);
    parts.pop();
    setCurrentPath('/' + parts.join('/'));
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function getIcon(item: FileItem): string {
    if (item.type === 'directory') return '📁';
    const ext = item.name.split('.').pop()?.toLowerCase() || '';
    const iconMap: Record<string, string> = { ts: '📘', tsx: '⚛️', js: '📙', py: '🐍', json: '📋', md: '📝', html: '🌐', css: '🎨', png: '🖼', jpg: '🖼', mp4: '🎬', mp3: '🎵', zip: '📦', pdf: '📄', exe: '⚙️', sql: '🗃' };
    return iconMap[ext] || '📄';
  }

  const sorted = [...files]
    .filter(f => !searchQuery || f.name.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => {
      if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
      if (sortBy === 'size') return b.size - a.size;
      if (sortBy === 'modified') return b.modified.localeCompare(a.modified);
      return a.name.localeCompare(b.name);
    });

  const breadcrumbs = currentPath.split('/').filter(Boolean);

  return (
    <div style={{ padding: 24, color: '#e0e0e0' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>📁 File Browser</h1>

      {/* Breadcrumbs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 16, fontSize: 14, flexWrap: 'wrap' }}>
        <button onClick={() => setCurrentPath('/')} style={{ background: 'none', border: 'none', color: '#6366f1', cursor: 'pointer' }}>🏠 root</button>
        {breadcrumbs.map((crumb, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: '#555' }}>/</span>
            <button onClick={() => setCurrentPath('/' + breadcrumbs.slice(0, i + 1).join('/'))} style={{ background: 'none', border: 'none', color: '#6366f1', cursor: 'pointer' }}>{crumb}</button>
          </span>
        ))}
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <button onClick={goUp} disabled={currentPath === '/'} style={{ padding: '6px 12px', background: currentPath === '/' ? '#222' : '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: currentPath === '/' ? 'default' : 'pointer' }}>⬆ Up</button>
        <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search files..." style={{ flex: 1, padding: '6px 12px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }} />
        <select value={sortBy} onChange={e => setSortBy(e.target.value as typeof sortBy)} style={{ padding: '6px 8px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 6, color: '#e0e0e0' }}>
          <option value="name">Name</option>
          <option value="size">Size</option>
          <option value="modified">Modified</option>
        </select>
        <button onClick={() => setViewMode(v => v === 'list' ? 'grid' : 'list')} style={{ padding: '6px 10px', background: '#333', border: 'none', borderRadius: 6, color: '#e0e0e0', cursor: 'pointer' }}>{viewMode === 'list' ? '▦' : '☰'}</button>
      </div>

      {/* File List */}
      <div style={{ display: 'grid', gap: 2 }}>
        {/* Header */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 150px 100px', gap: 12, padding: '8px 12px', color: '#666', fontSize: 12, fontWeight: 600, borderBottom: '1px solid #333' }}>
          <span>Name</span>
          <span>Size</span>
          <span>Modified</span>
          <span></span>
        </div>
        {sorted.map(item => (
          <div key={item.path} onClick={() => navigate(item)} onDoubleClick={() => navigate(item)} style={{ display: 'grid', gridTemplateColumns: '1fr 100px 150px 100px', gap: 12, padding: '10px 12px', background: selected.has(item.path) ? '#1e1e3a' : 'transparent', borderRadius: 6, cursor: 'pointer', alignItems: 'center', transition: 'background 0.15s' }}
            onMouseEnter={e => (e.currentTarget.style.background = '#1e1e2e')}
            onMouseLeave={e => (e.currentTarget.style.background = selected.has(item.path) ? '#1e1e3a' : 'transparent')}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>{getIcon(item)}</span>
              <span style={{ fontSize: 14 }}>{item.name}</span>
            </div>
            <span style={{ fontSize: 13, color: '#888' }}>{item.type === 'directory' ? '-' : formatSize(item.size)}</span>
            <span style={{ fontSize: 12, color: '#888' }}>{item.modified ? new Date(item.modified).toLocaleDateString() : '-'}</span>
            <span style={{ fontSize: 12, color: '#666' }}>{item.type === 'directory' ? '📁' : '📄'}</span>
          </div>
        ))}
        {sorted.length === 0 && <div style={{ color: '#666', textAlign: 'center', padding: 40 }}>This directory is empty</div>}
      </div>

      <div style={{ marginTop: 12, fontSize: 12, color: '#555' }}>
        {sorted.length} items • {sorted.filter(f => f.type === 'directory').length} folders • {sorted.filter(f => f.type === 'file').length} files
      </div>
    </div>
  );
}
