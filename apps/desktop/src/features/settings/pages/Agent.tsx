import { useCallback, useState } from 'react';
import { useAgentStore } from '../../agent/agentStore';
import { AgentStatus, DEFAULT_WS_URL } from '../../agent/agentTypes';
import { getAgentStatusLabel } from '../../agent/agentStore';
import { SettingsCard } from '../components/SettingsCard';
import '../settings.css';

export function AgentSettings() {
  const { status, url, connectionDetails, lastError, lastHeartbeatLatency, connect, disconnect } =
    useAgentStore();

  const [customUrl, setCustomUrl] = useState(url);
  const [urlDirty, setUrlDirty] = useState(false);

  const handleConnect = useCallback(() => {
    connect(urlDirty ? customUrl : undefined);
    setUrlDirty(false);
  }, [connect, customUrl, urlDirty]);

  const handleDisconnect = useCallback(() => {
    disconnect();
  }, [disconnect]);

  const isConnected = status === AgentStatus.connected;
  const isConnecting = status === AgentStatus.connecting;

  return (
    <SettingsCard title="Agent Connection" description="Configure the backend agent connection.">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Connection URL */}
        <div className="settingsField">
          <label className="settingsField__label">Backend WebSocket URL</label>
          <input
            className="settingsField__input"
            type="text"
            value={customUrl}
            onChange={(e) => {
              setCustomUrl(e.target.value);
              setUrlDirty(true);
            }}
            placeholder={DEFAULT_WS_URL}
            disabled={isConnected || isConnecting}
          />
          <span className="settingsField__desc">Default: {DEFAULT_WS_URL}</span>
        </div>

        {/* Status display */}
        <div className="settingsField">
          <span className="settingsField__label">Connection Status</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: isConnected ? '#27ae60' : isConnecting ? '#b8d4b8' : '#666',
                flexShrink: 0,
              }}
            />
            <span>{getAgentStatusLabel(status)}</span>
          </div>
        </div>

        {/* Heartbeat latency */}
        {isConnected && lastHeartbeatLatency !== null && (
          <div className="settingsField">
            <span className="settingsField__label">Heartbeat Latency</span>
            <span style={{ color: 'var(--settingsMuted)', fontSize: 12.5 }}>{lastHeartbeatLatency}ms</span>
          </div>
        )}

        {/* Reconnect info */}
        {connectionDetails.reconnecting && (
          <div className="settingsField">
            <span className="settingsField__label">Reconnecting</span>
            <span style={{ color: 'var(--settingsMuted)', fontSize: 12.5 }}>
              Attempt {connectionDetails.reconnectAttempts}/5
              {connectionDetails.reconnectAttempts >= 5 && ' (max reached)'}
            </span>
          </div>
        )}

        {/* Last error */}
        {lastError && (
          <div className="settingsField">
            <span className="settingsField__label" style={{ color: '#eb5757' }}>Error</span>
            <span style={{ color: '#eb5757', fontSize: 12.5 }}>{lastError}</span>
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
          {isConnected ? (
            <button
              style={{
                background: 'rgba(235, 87, 87, 0.15)',
                border: '1px solid rgba(235, 87, 87, 0.5)',
                borderRadius: 12,
                padding: '10px 14px',
                color: '#eb5757',
                cursor: 'pointer',
                fontWeight: 650,
              }}
              type="button"
              onClick={handleDisconnect}
            >
              Disconnect
            </button>
          ) : (
            <button
              style={{
                background: 'rgba(110, 168, 254, 0.16)',
                border: '1px solid rgba(110, 168, 254, 0.55)',
                borderRadius: 12,
                padding: '10px 14px',
                color: 'var(--settingsText)',
                cursor: 'pointer',
                fontWeight: 650,
                opacity: isConnecting ? 0.5 : 1,
              }}
              type="button"
              onClick={handleConnect}
              disabled={isConnecting}
            >
              {isConnecting ? 'Connecting…' : 'Connect'}
            </button>
          )}
        </div>
      </div>
    </SettingsCard>
  );
}
