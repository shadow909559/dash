import React, { useState, useRef, useEffect } from 'react';
import { useAIStore } from '@/stores/aiStore';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
}

interface SuspectedCause {
  file: string;
  line?: number;
  description: string;
  confidence: number;
}

interface DebuggingData {
  problem: string;
  logs: LogEntry[];
  suspectedCauses: SuspectedCause[];
  affectedFiles: string[];
  suggestedFixes: string[];
  status: 'analyzing' | 'diagnosing' | 'fixing' | 'resolved';
}

interface DebuggingModePanelProps {
  className?: string;
}

export const DebuggingModePanel: React.FC<DebuggingModePanelProps> = ({ className = '' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [debuggingData, setDebuggingData] = useState<DebuggingData | null>(null);
  const [position, setPosition] = useState({ x: 660, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  
  const panelRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const logsRef = useRef<HTMLDivElement>(null);
  
  const { dashState } = useAIStore();

  // Show panel when in debugging state
  useEffect(() => {
    if (dashState === 'debugging') {
      setIsOpen(true);
      // Simulate debugging data
      setDebuggingData({
        problem: 'WebSocket connection timeout after 30 seconds',
        logs: [
          { timestamp: '12:34:56', level: 'info', message: 'Connecting to ws://127.0.0.1:8000/api/v1/ws' },
          { timestamp: '12:35:26', level: 'warning', message: 'Connection timeout exceeded' },
          { timestamp: '12:35:27', level: 'error', message: 'Failed to establish WebSocket connection' },
          { timestamp: '12:35:28', level: 'debug', message: 'Retrying with exponential backoff' },
          { timestamp: '12:35:58', level: 'error', message: 'Max retries exceeded' },
        ],
        suspectedCauses: [
          { file: 'src/lib/ws.ts', line: 45, description: 'Timeout value too low for slow connections', confidence: 0.85 },
          { file: 'apps/backend/main.py', line: 120, description: 'Backend not responding to health checks', confidence: 0.60 },
        ],
        affectedFiles: ['src/lib/ws.ts', 'src/stores/aiStore.ts', 'apps/backend/main.py'],
        suggestedFixes: [
          'Increase WebSocket timeout from 30s to 60s',
          'Add connection retry with exponential backoff',
          'Implement health check fallback',
        ],
        status: 'diagnosing',
      });
    }
  }, [dashState]);

  // Auto-scroll logs
  useEffect(() => {
    if (logsRef.current && debuggingData?.logs) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [debuggingData?.logs]);

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

  const getLogLevelColor = (level: string) => {
    switch (level) {
      case 'error':
        return 'text-red-400';
      case 'warning':
        return 'text-yellow-400';
      case 'debug':
        return 'text-gray-400';
      case 'info':
      default:
        return 'text-blue-400';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'resolved':
        return 'text-green-400';
      case 'fixing':
        return 'text-yellow-400';
      case 'diagnosing':
        return 'text-purple-400';
      case 'analyzing':
      default:
        return 'text-blue-400';
    }
  };

  if (!isOpen) return null;

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    left: position.x,
    top: position.y,
    width: isExpanded ? '520px' : '400px',
    backgroundColor: 'rgba(0, 10, 30, 0.85)',
    border: '1px solid rgba(100, 200, 255, 0.3)',
    borderRadius: '12px',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    boxShadow: '0 0 30px rgba(100, 200, 255, 0.2), 0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(100, 200, 255, 0.1)',
    zIndex: 100,
    overflow: 'hidden',
    transition: 'width 0.3s ease, box-shadow 0.3s ease',
  };

  const panelWidth = isExpanded ? 600 : 400;
  const panelHeight = isExpanded ? 700 : 500;

  return (
    <div
      ref={panelRef}
      className={`fixed bg-gray-900/95 backdrop-blur-md rounded-xl border border-purple-500/30 shadow-2xl overflow-hidden ${className}`}
      style={panelStyle}
      onMouseDown={handleMouseDown}
    >
      {/* Header - Draggable */}
      <div
        ref={headerRef}
        style={{
          background: 'linear-gradient(90deg, rgba(100, 200, 255, 0.15), rgba(0, 255, 255, 0.15))',
          padding: '12px 16px',
          cursor: 'move',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(100, 200, 255, 0.2)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'rgba(100, 200, 255, 0.8)', boxShadow: '0 0 10px rgba(100, 200, 255, 0.6)', animation: 'pulse 2s infinite' }} />
          <span style={{ color: 'rgba(100, 200, 255, 0.95)', fontWeight: 600, fontSize: '13px', letterSpacing: '0.5px', textShadow: '0 0 8px rgba(100, 200, 255, 0.5)' }}>DEBUGGING</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            style={{
              background: 'rgba(100, 200, 255, 0.1)',
              border: '1px solid rgba(100, 200, 255, 0.3)',
              color: 'rgba(100, 200, 255, 0.9)',
              padding: '4px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(100, 200, 255, 0.2)';
              e.currentTarget.style.boxShadow = '0 0 10px rgba(100, 200, 255, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(100, 200, 255, 0.1)';
              e.currentTarget.style.boxShadow = 'none';
            }}
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? '−' : '+'}
          </button>
          <button
            onClick={() => setIsOpen(false)}
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
        {!debuggingData ? (
          <div style={{ textAlign: 'center', color: 'rgba(100, 200, 255, 0.6)', padding: '32px 0' }}>
            <p style={{ fontSize: '13px' }}>Analyzing problem...</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Status */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ color: 'rgba(100, 200, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', textShadow: '0 0 8px rgba(100, 200, 255, 0.4)' }}>Status</span>
              <span style={{ color: 'rgba(100, 200, 255, 0.9)', fontSize: '12px', fontWeight: 600 }}>{debuggingData.status}</span>
            </div>

            {/* Problem */}
            <div>
              <h3 style={{ color: 'rgba(100, 200, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(100, 200, 255, 0.4)' }}>Problem</h3>
              <p style={{ color: 'rgba(200, 220, 255, 0.9)', fontSize: '13px', lineHeight: '1.6' }}>{debuggingData.problem}</p>
            </div>

            {/* Logs */}
            {isExpanded && (
              <div>
                <h3 style={{ color: 'rgba(100, 200, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(100, 200, 255, 0.4)' }}>Logs</h3>
                <div ref={logsRef} style={{ 
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
                  {debuggingData.logs.map((log, idx) => (
                    <div key={idx} style={{ marginBottom: '4px', display: 'flex', gap: '8px' }}>
                      <span style={{ color: 'rgba(100, 200, 255, 0.6)' }}>{log.timestamp}</span>
                      <span style={{ 
                        color: log.level === 'error' ? 'rgba(255, 50, 50, 0.9)' : 
                              log.level === 'warning' ? 'rgba(255, 200, 0, 0.9)' : 
                              'rgba(0, 255, 255, 0.85)',
                        fontWeight: log.level === 'error' ? 600 : 400
                      }}>[{log.level.toUpperCase()}]</span>
                      <span style={{ color: 'rgba(200, 220, 255, 0.85)' }}>{log.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Suspected Causes */}
            {isExpanded && debuggingData.suspectedCauses.length > 0 && (
              <div>
                <h3 style={{ color: 'rgba(100, 200, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(100, 200, 255, 0.4)' }}>Suspected Causes</h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {debuggingData.suspectedCauses.map((cause, idx) => (
                    <li key={idx} style={{ padding: '8px', background: 'rgba(100, 200, 255, 0.05)', borderRadius: '4px', border: '1px solid rgba(100, 200, 255, 0.1)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={{ color: 'rgba(200, 220, 255, 0.9)', fontSize: '12px', fontWeight: 600 }}>{cause.file}:{cause.line || '?'}</span>
                        <span style={{ color: 'rgba(0, 255, 255, 0.9)', fontSize: '11px' }}>{Math.round(cause.confidence * 100)}%</span>
                      </div>
                      <p style={{ color: 'rgba(200, 220, 255, 0.7)', fontSize: '12px' }}>{cause.description}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Suggested Fixes */}
            {isExpanded && debuggingData.suggestedFixes.length > 0 && (
              <div>
                <h3 style={{ color: 'rgba(100, 200, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(100, 200, 255, 0.4)' }}>Suggested Fixes</h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {debuggingData.suggestedFixes.map((fix, idx) => (
                    <li key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', padding: '8px', background: 'rgba(100, 200, 255, 0.05)', borderRadius: '4px', border: '1px solid rgba(100, 200, 255, 0.1)' }}>
                      <span style={{ color: 'rgba(0, 255, 255, 0.8)' }}>{idx + 1}.</span>
                      <span style={{ color: 'rgba(200, 220, 255, 0.85)', fontSize: '12px' }}>{fix}</span>
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
