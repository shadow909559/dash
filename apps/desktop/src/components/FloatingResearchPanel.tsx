import React, { useState, useRef, useEffect } from 'react';
import { useAIStore } from '@/stores/aiStore';
import { getWsClient } from '@/lib/wsClient';
import { Search, CheckCircle, AlertCircle, Clock } from 'lucide-react';

interface ResearchSource {
  title: string;
  url: string;
  content?: string;
}

interface ResearchData {
  query: string;
  status: 'searching' | 'analyzing' | 'complete' | 'error';
  summary: string;
  sources: ResearchSource[];
  keyFindings: string[];
  confidence: number;
  currentAction?: string;
  progress?: number;
}

interface FloatingResearchPanelProps {
  className?: string;
}

export const FloatingResearchPanel: React.FC<FloatingResearchPanelProps> = ({ className = '' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [researchData, setResearchData] = useState<ResearchData | null>(null);
  const [position, setPosition] = useState({ x: 20, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  
  const panelRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  
  const { dashState, setDashState } = useAIStore();
  const wsClient = getWsClient();

  // Show panel when in researching state
  useEffect(() => {
    if (dashState === 'researching') {
      setIsOpen(true);
      // Start with empty research data
      setResearchData({
        query: '',
        status: 'searching',
        summary: '',
        sources: [],
        keyFindings: [],
        confidence: 0,
        currentAction: 'Initializing research...',
        progress: 0,
      });
    }
  }, [dashState]);

  // Listen for research events from WebSocket
  useEffect(() => {
    const handleResearchStart = (data: Record<string, unknown>) => {
      const query = data.query as string || '';
      setResearchData({
        query,
        status: 'searching',
        summary: '',
        sources: [],
        keyFindings: [],
        confidence: 0,
        currentAction: 'Searching for sources...',
        progress: 10,
      });
      setIsOpen(true);
      setDashState('researching');
    };

    const handleResearchProgress = (data: Record<string, unknown>) => {
      setResearchData(prev => {
        if (!prev) return null;
        return {
          ...prev,
          status: data.status as 'searching' | 'analyzing' | 'complete' | 'error' || prev.status,
          currentAction: data.current_action as string || prev.currentAction,
          progress: data.progress as number || prev.progress,
        };
      });
    };

    const handleResearchComplete = (data: Record<string, unknown>) => {
      setResearchData({
        query: data.query as string || '',
        status: 'complete',
        summary: data.summary as string || '',
        sources: (data.sources as ResearchSource[]) || [],
        keyFindings: (data.key_findings as string[]) || [],
        confidence: (data.confidence as number) || 0,
        currentAction: 'Research complete',
        progress: 100,
      });
      setDashState('idle');
    };

    const handleResearchError = (data: Record<string, unknown>) => {
      setResearchData(prev => {
        if (!prev) return null;
        return {
          ...prev,
          status: 'error',
          currentAction: data.error as string || 'Research failed',
        };
      });
      setDashState('error');
    };

    wsClient.on('research.start', handleResearchStart);
    wsClient.on('research.progress', handleResearchProgress);
    wsClient.on('research.complete', handleResearchComplete);
    wsClient.on('research.error', handleResearchError);

    return () => {
      wsClient.off('research.start', handleResearchStart);
      wsClient.off('research.progress', handleResearchProgress);
      wsClient.off('research.complete', handleResearchComplete);
      wsClient.off('research.error', handleResearchError);
    };
  }, [wsClient, setDashState]);

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

  if (!isOpen) return null;

  const getStatusIcon = () => {
    switch (researchData?.status) {
      case 'searching':
      case 'analyzing':
        return <Clock size={14} color="rgba(251, 191, 36, 0.9)" />;
      case 'complete':
        return <CheckCircle size={14} color="rgba(74, 222, 128, 0.9)" />;
      case 'error':
        return <AlertCircle size={14} color="rgba(63, 169, 245, 0.9)" />;
      default:
        return <Search size={14} color="rgba(0, 255, 255, 0.9)" />;
    }
  };

  const panelStyle: React.CSSProperties = {
    position: 'fixed',
    left: position.x,
    top: position.y,
    width: isExpanded ? '500px' : '380px',
    backgroundColor: 'rgba(0, 10, 30, 0.85)',
    border: '1px solid rgba(0, 255, 255, 0.3)',
    borderRadius: '12px',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    boxShadow: '0 0 30px rgba(0, 255, 255, 0.2), 0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(0, 255, 255, 0.1)',
    zIndex: 100,
    overflow: 'hidden',
    transition: 'width 0.3s ease, box-shadow 0.3s ease',
  };

  return (
    <div
      ref={panelRef}
      className={`rounded-xl ${className}`}
      style={panelStyle}
      onMouseDown={handleMouseDown}
    >
      {/* Header - Draggable */}
      <div
        ref={headerRef}
        style={{
          background: 'linear-gradient(90deg, rgba(0, 255, 255, 0.15), rgba(255, 0, 255, 0.15))',
          padding: '12px 16px',
          cursor: 'move',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(0, 255, 255, 0.2)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {getStatusIcon()}
          <span style={{ color: 'rgba(0, 255, 255, 0.95)', fontWeight: 600, fontSize: '13px', letterSpacing: '0.5px', textShadow: '0 0 8px rgba(0, 255, 255, 0.5)' }}>RESEARCH</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            style={{
              background: 'rgba(0, 255, 255, 0.1)',
              border: '1px solid rgba(0, 255, 255, 0.3)',
              color: 'rgba(0, 255, 255, 0.9)',
              padding: '4px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(0, 255, 255, 0.2)';
              e.currentTarget.style.boxShadow = '0 0 10px rgba(0, 255, 255, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(0, 255, 255, 0.1)';
              e.currentTarget.style.boxShadow = 'none';
            }}
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? '−' : '+'}
          </button>
          <button
            onClick={() => {
              setIsOpen(false);
              setDashState('idle');
            }}
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
        {!researchData ? (
          <div style={{ textAlign: 'center', color: 'rgba(0, 255, 255, 0.6)', padding: '32px 0' }}>
            <p style={{ fontSize: '13px' }}>Ready to research</p>
          </div>
        ) : researchData.status === 'searching' || researchData.status === 'analyzing' ? (
          <div style={{ textAlign: 'center', color: 'rgba(0, 255, 255, 0.6)', padding: '32px 0' }}>
            <p style={{ fontSize: '13px', marginBottom: '12px' }}>{researchData.currentAction}</p>
            <div style={{ marginTop: '16px', width: '100%', background: 'rgba(0, 255, 255, 0.1)', borderRadius: '4px', height: '8px' }}>
              <div 
                style={{ 
                  background: 'rgba(0, 255, 255, 0.8)', 
                  height: '8px', 
                  borderRadius: '4px', 
                  width: `${researchData.progress || 0}%`,
                  boxShadow: '0 0 10px rgba(0, 255, 255, 0.5)',
                  transition: 'width 0.3s ease'
                }} 
              />
            </div>
            <p style={{ fontSize: '11px', marginTop: '8px', color: 'rgba(0, 255, 255, 0.5)' }}>{Math.round(researchData.progress || 0)}%</p>
          </div>
        ) : researchData.status === 'error' ? (
          <div style={{ textAlign: 'center', color: 'rgba(63, 169, 245, 0.8)', padding: '32px 0' }}>
            <AlertCircle size={32} style={{ marginBottom: '12px' }} />
            <p style={{ fontSize: '13px' }}>{researchData.currentAction}</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Query */}
            <div>
              <h3 style={{ color: 'rgba(0, 255, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(0, 255, 255, 0.4)' }}>Query</h3>
              <p style={{ color: 'rgba(255, 255, 255, 0.9)', fontSize: '13px' }}>{researchData.query}</p>
            </div>

            {/* Summary */}
            {isExpanded && (
              <div>
                <h3 style={{ color: 'rgba(0, 255, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(0, 255, 255, 0.4)' }}>Summary</h3>
                <p style={{ color: 'rgba(200, 220, 255, 0.85)', fontSize: '13px', lineHeight: '1.6' }}>{researchData.summary}</p>
              </div>
            )}

            {/* Key Findings */}
            {isExpanded && researchData.keyFindings.length > 0 && (
              <div>
                <h3 style={{ color: 'rgba(0, 255, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(0, 255, 255, 0.4)' }}>Key Findings</h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {researchData.keyFindings.map((finding, idx) => (
                    <li key={idx} style={{ color: 'rgba(200, 220, 255, 0.85)', fontSize: '13px', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <span style={{ color: 'rgba(0, 255, 255, 0.8)' }}>•</span>
                      <span>{finding}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Sources */}
            <div>
              <h3 style={{ color: 'rgba(0, 255, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(0, 255, 255, 0.4)' }}>Sources ({researchData.sources.length})</h3>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {researchData.sources.map((source, idx) => (
                  <li key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'rgba(100, 200, 255, 0.9)', fontSize: '12px', textDecoration: 'none', transition: 'all 0.2s' }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = 'rgba(0, 255, 255, 1)';
                        e.currentTarget.style.textShadow = '0 0 10px rgba(0, 255, 255, 0.6)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = 'rgba(100, 200, 255, 0.9)';
                        e.currentTarget.style.textShadow = 'none';
                      }}
                    >
                      {source.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            {/* Confidence */}
            {isExpanded && (
              <div>
                <h3 style={{ color: 'rgba(0, 255, 255, 0.9)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', textShadow: '0 0 8px rgba(0, 255, 255, 0.4)' }}>Confidence</h3>
                <div style={{ width: '100%', background: 'rgba(0, 255, 255, 0.1)', borderRadius: '4px', height: '8px' }}>
                  <div
                    style={{
                      background: `linear-gradient(90deg, rgba(0, 255, 255, 0.8), rgba(255, 0, 255, 0.8))`,
                      height: '8px',
                      borderRadius: '4px',
                      width: `${researchData.confidence * 100}%`,
                      boxShadow: '0 0 10px rgba(0, 255, 255, 0.5)',
                      transition: 'width 0.5s ease'
                    }}
                  />
                </div>
                <p style={{ color: 'rgba(200, 220, 255, 0.7)', fontSize: '12px', marginTop: '4px' }}>{Math.round(researchData.confidence * 100)}%</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
