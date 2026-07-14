import { useAgentStore } from './agentStore';
import { AgentStatus } from './agentTypes';
import './agent.css';

export function MachineInfoPanel() {
  const { machineInfo, status } = useAgentStore();

  if (status !== AgentStatus.connected || !machineInfo) {
    return null;
  }

  return (
    <div className="machine-info">
      <div className="machine-info__title">Machine Info</div>
      <div className="machine-info__row">
        <span className="machine-info__label">Platform</span>
        <span className="machine-info__value">{machineInfo.platform}</span>
      </div>
      <div className="machine-info__row">
        <span className="machine-info__label">CPU</span>
        <span className="machine-info__value">{machineInfo.cpu}</span>
      </div>
      <div className="machine-info__row">
        <span className="machine-info__label">Memory</span>
        <span className="machine-info__value">{machineInfo.memory}</span>
      </div>
      <div className="machine-info__row">
        <span className="machine-info__label">Uptime</span>
        <span className="machine-info__value">{machineInfo.uptime}</span>
      </div>
    </div>
  );
}