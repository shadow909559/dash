import React, { useState, useRef, useEffect } from 'react';
import { useAIStore } from '@/stores/aiStore';

interface CodeFile {
  path: string;
  status: 'modified' | 'added' | 'deleted';
  changes?: number;
}

interface CodeOperation {
  type: 'edit' | 'create' | 'delete' | 'move';
  target: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

interface TestResult {
  name: string;
  status: 'passed' | 'failed' | 'skipped';
  duration?: number;
}

interface CodingData {
  project: string;
  files: CodeFile[];
  operations: CodeOperation[];
  terminalOutput: string[];
  tests: TestResult[];
  status: 'idle' | 'editing' | 'running' | 'testing' | 'completed';
}

interface CodingModePanelProps {
  className?: string;
}

export const CodingModePanel: React.FC<CodingModePanelProps> = ({ className = '' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [codingData, setCodingData] = useState<CodingData | null>(null);
  const [position, setPosition] = useState({ x: 340, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  
  const panelRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  
  const { dashState } = useAIStore();

  // Show panel when in coding state
  useEffect(() => {
    if (dashState === 'coding') {
      setIsOpen(true);
      // Simulate coding data
      setCodingData({
        project: 'DASH AI OS',
        files: [
          { path: 'src/App.tsx', status: 'modified', changes: 5 },
          { path: 'src/components/NeuralOrb.tsx', status: 'modified', changes: 12 },
          { path: 'src/stores/dashState.ts', status: 'added', changes: 0 },
        ],
        operations: [
          { type: 'edit', target: 'src/App.tsx', status: 'completed' },
          { type: 'create', target: 'src/components/FloatingResearchPanel.tsx', status: 'completed' },
          { type: 'edit', target: 'src/stores/aiStore.ts', status: 'running' },
        ],
        terminalOutput: [
          '> npm run dev',
          'VITE v5.0.0  ready in 234 ms',
          '  ➜  Local:   http://localhost:5173/',
          '  ➜  Network: use --host to expose',
          '> Compiling...',
          '✓ Compiled successfully in 1.2s',
        ],
        tests: [
          { name: 'WindowModeSwitcher', status: 'passed', duration: 45 },
          { name: 'FloatingResearchPanel', status: 'passed', duration: 32 },
          { name: 'DashState', status: 'passed', duration: 28 },
        ],
        status: 'editing',
      });
    }
  }, [dashState]);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current && codingData?.terminalOutput) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [codingData?.terminalOutput]);

  // Handle drag start
  const handleMouseDown = (e: React.MouseEvent) => {
    if (headerRef.current && headerRef.current.contains(e.target as Node)) {
      setIsDragging(true);
      setDragOffset({
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      });
    }
  };

  // Handle drag move
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        setPosition({
          x: e.clientX - dragOffset.x,
          y: e.clientY - dragOffset.y,
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
      case 'passed':
        return 'text-green-400';
      case 'failed':
        return 'text-red-400';
      case 'running':
        return 'text-yellow-400';
      case 'pending':
      case 'skipped':
        return 'text-gray-400';
      default:
        return 'text-gray-300';
    }
  };

  const getFileStatusColor = (status: string) => {
    switch (status) {
      case 'modified':
        return 'text-yellow-400';
      case 'added':
        return 'text-green-400';
      case 'deleted':
        return 'text-red-400';
      default:
        return 'text-gray-300';
    }
  };

  if (!isOpen) return null;

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    left: position.x,
    top: position.y,
    width: isExpanded ? '550px' : '420px',
    backgroundColor: 'rgba(0, 10, 30, 0.85)',
    border: '1px solid rgba(255, 0, 255, 0.3)',
    borderRadius: '12px',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    boxShadow: '0 0 30px rgba(255, 0, 255, 0.2), 0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 0, 255, 0.1)',
    zIndex: 100,
    overflow: 'hidden',
    transition: 'width 0.3s ease, box-shadow 0.3s ease',
  };

  return (
    <div
      ref={panelRef}
      className={` ${className}`}
      style={panelStyle}
      onMouseDown={handleMouseDown}
    >
      {/* Header - Draggable */}
      <div
        ref={headerRef}
        style={{
          background: 'linear-gradient(90deg, rgba(255, 0, 255, 0.15), rgba(100, 200, 255, 0.15))',
          padding: '12px 16px',
          cursor: 'move',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(255, 0, 255, 0.2)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'rgba(255, 0, 255, 0.8)', boxShadow: '0 0 10px rgba(255, 0, 255, 0.6)', animation: 'pulse 2s infinite' }} />
          <span style={{ color: 'rgba(255, 0, 255, 0.95)', fontWeight: 600, fontSize: '13px', letterSpacing: '0.5px', textShadow: '0 0 8px rgba(255, 0, 255, 0.5)' }}>CODING</span>
          {codingData && (
            <span style={{ color: 'rgba(200, 220, 255, 0.6)', fontSize: '11px', marginLeft: '8px' }}>{codingData.project}</span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse coding panel' : 'Expand coding panel'}
            aria-expanded={isExpanded}
            style={{
              background: 'rgba(255, 0, 255, 0.1)',
              border: '1px solid rgba(255, 0, 255, 0.3)',
              color: 'rgba(255, 0, 255, 0.9)',
              padding: '4px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255, 0, 255, 0.2)';
              e.currentTarget.style.boxShadow = '0 0 10px rgba(255, 0, 255, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255, 0, 255, 0.1)';
              e.currentTarget.style.boxShadow = 'none';
            }}
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? '−' : '+'}
          </button>
          <button
            onClick={() => setIsOpen(false)}
            aria-label="Close coding panel"
            style={{
              background: 'rgba(255, 50, 50, 0.1)',
              border: '1px solid rgba(255, 50, 50, 0.3)',
              color: 'rgba(255, 50, 50, 0.9)',
              padding: '4px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255, 50, 50, 0.2)';
              e.currentTarget.style.boxShadow = '0 0 10px rgba(255, 50, 50, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255, 50, 50, 0.1)';
              e.currentTarget.style.boxShadow = 'none';
            }}
            title="Close"
          >
            ×
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: '16px', overflowY: 'auto', height: 'calc(100% - 48px)' }}>
        {!codingData ? (
          <div style={{ textAlign: 'center', color: 'rgba(255, 0, 255, 0.6)', padding: '32px 0' }}>
            <p style={{ fontSize: '13px' }}>Initializing coding environment...</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Status */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ color: 'rgba(255, 0, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', textShadow: '0 0 8px rgba(255, 0, 255, 0.4)' }}>Status</span>
              <span style={{ color: 'rgba(100, 200, 255, 0.9)', fontSize: '12px', fontWeight: 600 }}>{codingData.status}</span>
            </div>

            {/* Files */}
            <div>
              <h3 style={{ color: 'rgba(255, 0, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(255, 0, 255, 0.4)' }}>Files</h3>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {codingData.files.map((file, idx) => (
                  <li key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px', background: 'rgba(255, 0, 255, 0.05)', borderRadius: '4px', border: '1px solid rgba(255, 0, 255, 0.1)' }}>
                    <span style={{ color: 'rgba(200, 220, 255, 0.9)', fontSize: '12px' }}>{file.path}</span>
                    <span style={{ 
                      color: file.status === 'modified' ? 'rgba(255, 200, 0, 0.9)' : 
                            file.status === 'added' ? 'rgba(0, 255, 0, 0.9)' : 
                            'rgba(255, 50, 50, 0.9)',
                      fontSize: '11px',
                      fontWeight: 600,
                      textTransform: 'uppercase'
                    }}>{file.status}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Operations */}
            {isExpanded && (
              <div>
                <h3 style={{ color: 'rgba(255, 0, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(255, 0, 255, 0.4)' }}>Operations</h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {codingData.operations.map((op, idx) => (
                    <li key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px', background: 'rgba(255, 0, 255, 0.05)', borderRadius: '4px', border: '1px solid rgba(255, 0, 255, 0.1)' }}>
                      <span style={{ color: 'rgba(200, 220, 255, 0.9)', fontSize: '12px' }}>{op.type}: {op.target}</span>
                      <span style={{ 
                        color: op.status === 'completed' ? 'rgba(0, 255, 0, 0.9)' : 
                              op.status === 'running' ? 'rgba(255, 200, 0, 0.9)' : 
                              op.status === 'failed' ? 'rgba(255, 50, 50, 0.9)' : 
                              'rgba(200, 220, 255, 0.7)',
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'uppercase'
                      }}>{op.status}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Terminal */}
            {isExpanded && (
              <div>
                <h3 style={{ color: 'rgba(255, 0, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(255, 0, 255, 0.4)' }}>Terminal</h3>
                <div style={{ 
                  background: 'rgba(0, 5, 15, 0.8)', 
                  borderRadius: '4px', 
                  padding: '12px', 
                  fontFamily: 'monospace',
                  fontSize: '11px',
                  color: 'rgba(0, 255, 255, 0.85)',
                  border: '1px solid rgba(0, 255, 255, 0.2)',
                  maxHeight: '150px',
                  overflowY: 'auto'
                }}>
                  {codingData.terminalOutput.map((line, idx) => (
                    <div key={idx} style={{ marginBottom: '4px' }}>{line}</div>
                  ))}
                </div>
              </div>
            )}

            {/* Tests */}
            {isExpanded && codingData.tests.length > 0 && (
              <div>
                <h3 style={{ color: 'rgba(255, 0, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(255, 0, 255, 0.4)' }}>Tests</h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {codingData.tests.map((test, idx) => (
                    <li key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px', background: 'rgba(255, 0, 255, 0.05)', borderRadius: '4px', border: '1px solid rgba(255, 0, 255, 0.1)' }}>
                      <span style={{ color: 'rgba(200, 220, 255, 0.9)', fontSize: '12px' }}>{test.name}</span>
                      <span style={{ 
                        color: test.status === 'passed' ? 'rgba(0, 255, 0, 0.9)' : 
                              test.status === 'failed' ? 'rgba(255, 50, 50, 0.9)' : 
                              'rgba(200, 220, 255, 0.7)',
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'uppercase'
                      }}>{test.status}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
