import { useState, useEffect, useRef } from 'react';

interface TerminalLine { id: string; type: 'input' | 'output' | 'error'; content: string; timestamp: string; }

export default function TerminalPage() {
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const [isRunning, setIsRunning] = useState(false);
  const [shell, setShell] = useState('bash');
  const inputRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    addLine('output', `DASH Terminal v1.0 — ${shell} shell`);
    addLine('output', 'Type commands below. Use ↑↓ for history.\n');
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  function addLine(type: 'input' | 'output' | 'error', content: string) {
    setLines(prev => [...prev, { id: crypto.randomUUID(), type, content, timestamp: new Date().toISOString() }]);
  }

  async function executeCommand() {
    if (!input.trim()) return;
    addLine('input', `$ ${input}`);
    setHistory(prev => [...prev, input]);
    setHistoryIdx(-1);
    setIsRunning(true);

    try {
      const r = await fetch('/api/v1/features/terminal/exec', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: input, shell }),
      });
      if (r.ok) {
        const data = await r.json();
        if (data.stdout) addLine('output', data.stdout);
        if (data.stderr) addLine('error', data.stderr);
        if (data.exit_code !== undefined && data.exit_code !== 0) {
          addLine('error', `Exit code: ${data.exit_code}`);
        }
      } else {
        addLine('error', `Command failed: ${r.statusText}`);
      }
    } catch (e) {
      addLine('error', `Error: ${e instanceof Error ? e.message : 'Unknown error'}`);
    }

    setIsRunning(false);
    setInput('');
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') { e.preventDefault(); executeCommand(); }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length > 0) {
        const idx = historyIdx < 0 ? history.length - 1 : Math.max(0, historyIdx - 1);
        setHistoryIdx(idx);
        setInput(history[idx]);
      }
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx >= 0) {
        const idx = historyIdx + 1;
        if (idx >= history.length) { setHistoryIdx(-1); setInput(''); }
        else { setHistoryIdx(idx); setInput(history[idx]); }
      }
    }
    if (e.key === 'l' && e.ctrlKey) { e.preventDefault(); setLines([]); }
  }

  function clearTerminal() { setLines([]); }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 60px)', background: '#0a0a0f', color: '#00ff00', fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '8px 16px', background: '#12121e', borderBottom: '1px solid #333', gap: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>⬛ Terminal</span>
        <select value={shell} onChange={e => setShell(e.target.value)} style={{ background: '#1e1e2e', border: '1px solid #333', borderRadius: 4, color: '#e0e0e0', padding: '4px 8px', fontSize: 12 }}>
          <option value="bash">Bash</option>
          <option value="powershell">PowerShell</option>
          <option value="cmd">CMD</option>
        </select>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: isRunning ? '#f59e0b' : '#10b981' }}>{isRunning ? '● Running' : '● Ready'}</span>
        <button onClick={clearTerminal} style={{ background: '#333', border: 'none', borderRadius: 4, color: '#e0e0e0', padding: '4px 10px', fontSize: 12, cursor: 'pointer' }}>Clear</button>
      </div>

      {/* Terminal Output */}
      <div style={{ flex: 1, overflow: 'auto', padding: 16 }} onClick={() => inputRef.current?.focus()}>
        {lines.map(line => (
          <div key={line.id} style={{ marginBottom: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: line.type === 'error' ? '#ef4444' : line.type === 'input' ? '#6366f1' : '#00ff00', fontSize: 13 }}>
            {line.content}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '8px 16px', background: '#0d0d15', borderTop: '1px solid #333', gap: 8 }}>
        <span style={{ color: '#6366f1', fontSize: 13, userSelect: 'none' }}>$</span>
        <div ref={inputRef} style={{ flex: 1 }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isRunning}
            style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', color: '#00ff00', fontSize: 13, fontFamily: 'inherit' }}
            placeholder={isRunning ? 'Running...' : 'Type a command...'}
            autoFocus
          />
        </div>
      </div>

      {/* History Panel */}
      <div style={{ padding: '4px 16px', background: '#0a0a0f', borderTop: '1px solid #222', fontSize: 11, color: '#444' }}>
        Command history: {history.length} commands • Ctrl+L to clear
      </div>
    </div>
  );
}
