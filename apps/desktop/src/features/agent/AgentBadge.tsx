import { useCallback, useState } from 'react';
import { useAgentStore, getAgentStatusLabel } from './agentStore';
import { AgentStatus } from './agentTypes';
import './agent.css';

export function AgentBadge() {
  const { status, lastHeartbeatLatency, machineInfo, connectionDetails, lastError } =
    useAgentStore();

  const [showTooltip, setShowTooltip] = useState(false);

  const toggleTooltip = useCallback(() => {
    setShowTooltip((prev) => !prev);
  }, []);

  const statusLabel = getAgentStatusLabel(status);
  const latencyMs = lastHeartbeatLatency;

  return (
    <div className="agent-area">
      <button
        type="button"
        className={`agent-badge agent-badge--${status}`}
        onClick={toggleTooltip}
        title={`Agent: ${statusLabel}`}
      >
        <span className="agent-badge__dot" />
        <span className="agent-badge__label">{statusLabel}</span>
        {status === AgentStatus.connected && latencyMs !== null && (
          <span className="agent-badge__heartbeat">{latencyMs}ms</span>
        )}
      </button>

      {showTooltip && (
        <div className="agent-details">
          <dl>
            <dt>Status</dt>
            <dd>{statusLabel}</dd>

            <dt>Server</dt>
            <dd>{connectionDetails.url}</dd>

            {status === AgentStatus.connected && (
              <>
                <dt>Heartbeat Latency</dt>
                <dd>{latencyMs !== null ? `${latencyMs}ms` : 'N/A'}</dd>
              </>
            )}

            {machineInfo && (
              <>
                <dt>Platform</dt>
                <dd>{machineInfo.platform}</dd>

                <dt>OS</dt>
                <dd>{machineInfo.os}</dd>

                <dt>CPU</dt>
                <dd>{machineInfo.cpu}</dd>

                <dt>Memory</dt>
                <dd>{machineInfo.memory}</dd>
              </>
            )}

            {lastError && (
              <>
                <dt>Error</dt>
                <dd style={{ color: '#eb5757' }}>{lastError}</dd>
              </>
            )}

            {connectionDetails.reconnecting && (
              <>
                <dt>Reconnecting</dt>
                <dd>
                  Attempt {connectionDetails.reconnectAttempts}/5
                </dd>
              </>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}