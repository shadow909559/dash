import { useState, useEffect, useRef } from 'react';

interface FileNode { name: string; type: 'file' | 'directory'; path: string; children?: FileNode[]; }

const LANG_MAP: Record<string, string> = { ts: 'TypeScript', tsx: 'TypeScript React', js: 'JavaScript', jsx: 'JavaScript React', py: 'Python', rs: 'Rust', go: 'Go', java: 'Java', html: 'HTML', css: 'CSS', json: 'JSON', md: 'Markdown', sql: 'SQL', sh: 'Shell', yaml: 'YAML', yml: 'YAML', toml: 'TOML', xml: 'XML', cpp: 'C++', c: 'C', rb: 'Ruby', php: 'PHP' };

export default function CodeEditorPage() {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [openFile, setOpenFile] = useState<string>('');
  const [content, setContent] = useState('');
  const [language, setLanguage] = useState('plaintext');
  const [lineCount, setLineCount] = useState(0);
  const [modified, setModified] = useState(false);
  const [cursorLine, setCursorLine] = useState(1);
  const [cursorCol, setCursorCol] = useState(1);
  const [searchText, setSearchText] = useState('');
  const [fontSize, setFontSize] = useState(14);
  const [wordWrap, setWordWrap] = useState<'on' | 'off'>('off');
  const [minimap, setMinimap] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadWorkspace();
  }, []);

  function detectLanguage(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    return LANG_MAP[ext] || 'plaintext';
  }

  async function loadWorkspace() {
    try {
      const r = await fetch('/api/v1/features/code/workspace');
      if (r.ok) {
        const data = await r.json();
        setFiles(data.files || data.tree || []);
      }
    } catch { /* ignore */ }
  }

  function handleContentChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setContent(val);
    setModified(true);
    setLineCount(val.split('\n').length);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Tab') {
      e.preventDefault();
      const ta = textareaRef.current;
      if (ta) {
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const newContent = content.substring(0, start) + '  ' + content.substring(end);
        setContent(newContent);
        setTimeout(() => { ta.selectionStart = ta.selectionEnd = start + 2; }, 0);
      }
    }
    if (e.ctrlKey && e.key === 's') {
      e.preventDefault();
      saveFile();
    }
  }

  async function saveFile() {
    if (!openFile) return;
    try {
      await fetch('/api/v1/features/code/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: openFile, content }),
      });
      setModified(false);
    } catch { /* ignore */ }
  }

  function openFileNode(node: FileNode) {
    if (node.type === 'directory') return;
    setOpenFile(node.path);
    setLanguage(detectLanguage(node.name));
    setContent(`// ${node.name}\n// Click to load file content...\n`);
    setLineCount(2);
    setModified(false);
  }

  const highlightedLines = content.split('\n');

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 60px)', color: '#e0e0e0', fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>
      {/* File Tree */}
      <div style={{ width: 240, background: '#12121e', borderRight: '1px solid #333', overflow: 'auto', padding: 8 }}>
        <div style={{ padding: '8px 4px', fontWeight: 600, fontSize: 12, color: '#888', textTransform: 'uppercase' }}>Explorer</div>
        {files.map(f => (
          <FileTreeNode key={f.path} node={f} depth={0} onOpen={openFileNode} activeFile={openFile} />
        ))}
      </div>

      {/* Editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Tab Bar */}
        {openFile && (
          <div style={{ display: 'flex', alignItems: 'center', background: '#1a1a2e', borderBottom: '1px solid #333', padding: '0 12px', height: 36 }}>
            <div style={{ padding: '8px 12px', background: '#12121e', borderRadius: '6px 6px 0 0', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
              {openFile.split('/').pop()}
              {modified && <span style={{ color: '#f59e0b' }}>●</span>}
              <button onClick={() => { setOpenFile(''); setContent(''); }} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer' }}>×</button>
            </div>
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12, color: '#888' }}>
              <span>{language}</span>
              <span>Ln {cursorLine}, Col {cursorCol}</span>
              <button onClick={() => setFontSize(s => Math.min(24, s + 1))} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer' }}>A+</button>
              <button onClick={() => setFontSize(s => Math.max(10, s - 1))} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer' }}>A-</button>
              <button onClick={() => setWordWrap(w => w === 'on' ? 'off' : 'on')} style={{ background: 'none', border: 'none', color: wordWrap === 'on' ? '#6366f1' : '#888', cursor: 'pointer' }}>↵</button>
            </div>
          </div>
        )}

        {/* Search Bar */}
        {openFile && (
          <div style={{ display: 'flex', padding: '4px 12px', background: '#16162a', gap: 8, borderBottom: '1px solid #222' }}>
            <input value={searchText} onChange={e => setSearchText(e.target.value)} placeholder="Find..." style={{ flex: 1, padding: '4px 8px', background: '#1e1e2e', border: '1px solid #333', borderRadius: 4, color: '#e0e0e0', fontSize: 12 }} />
          </div>
        )}

        {/* Code Area */}
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', background: '#0d1117' }}>
          {openFile ? (
            <>
              {/* Line Numbers */}
              <div style={{ padding: '12px 0', minWidth: 50, textAlign: 'right', paddingRight: 12, color: '#555', fontSize, lineHeight: 1.6, userSelect: 'none' }}>
                {highlightedLines.map((_, i) => (
                  <div key={i} style={{ height: `${fontSize * 1.6}px` }}>{i + 1}</div>
                ))}
              </div>
              <textarea
                ref={textareaRef}
                value={content}
                onChange={handleContentChange}
                onKeyDown={handleKeyDown}
                onClick={e => {
                  const ta = e.target as HTMLTextAreaElement;
                  const lines = ta.value.substring(0, ta.selectionStart).split('\n');
                  setCursorLine(lines.length);
                  setCursorCol(lines[lines.length - 1].length + 1);
                }}
                style={{ flex: 1, background: 'transparent', color: '#e0e0e0', border: 'none', outline: 'none', resize: 'none', padding: 12, fontSize, lineHeight: 1.6, fontFamily: 'inherit', wordWrap: wordWrap === 'on' ? 'break-word' : undefined, whiteSpace: wordWrap === 'on' ? 'pre-wrap' : 'pre' }}
                spellCheck={false}
                placeholder="Open a file to start editing..."
              />
            </>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#555' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>📝</div>
              <div style={{ fontSize: 18, marginBottom: 8 }}>DASH Code Editor</div>
              <div style={{ fontSize: 14 }}>Select a file from the explorer to start editing</div>
              <div style={{ fontSize: 12, marginTop: 12, color: '#444' }}>Ctrl+S to save • Tab to indent • Ctrl+F to find</div>
            </div>
          )}
        </div>

        {/* Status Bar */}
        <div style={{ display: 'flex', alignItems: 'center', background: '#1a1a2e', borderTop: '1px solid #333', padding: '2px 12px', fontSize: 12, color: '#888', gap: 16 }}>
          <span>{lineCount} lines</span>
          <span>{content.length} chars</span>
          <span>{language}</span>
          <div style={{ flex: 1 }} />
          <span>Spaces: 2</span>
          <span>UTF-8</span>
          <span>{modified ? '● Modified' : ''}</span>
        </div>
      </div>
    </div>
  );
}

function FileTreeNode({ node, depth, onOpen, activeFile }: { node: FileNode; depth: number; onOpen: (n: FileNode) => void; activeFile: string }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const isDir = node.type === 'directory';
  const isActive = node.path === activeFile;

  return (
    <div>
      <div
        onClick={() => isDir ? setExpanded(!expanded) : onOpen(node)}
        style={{ padding: '4px 8px', paddingLeft: depth * 16 + 8, cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6, background: isActive ? '#1e1e3a' : 'transparent', borderRadius: 4, color: isActive ? '#e0e0e0' : '#aaa' }}
      >
        <span style={{ fontSize: 10, width: 12 }}>{isDir ? (expanded ? '▼' : '▶') : '📄'}</span>
        <span>{node.name}</span>
      </div>
      {isDir && expanded && node.children?.map(c => (
        <FileTreeNode key={c.path} node={c} depth={depth + 1} onOpen={onOpen} activeFile={activeFile} />
      ))}
    </div>
  );
}
