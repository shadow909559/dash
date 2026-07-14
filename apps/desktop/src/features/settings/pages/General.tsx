import { useState } from 'react';
import { useSettingsStore, validateHttpUrl, validateWsUrl } from '../settingsStore';
import { SettingsCard } from '../components/SettingsCard';
import { ToggleRow } from '../components/controls/ToggleRow';
import { TextField } from '../components/controls/TextField';
import { useAgentStore } from '../../agent/agentStore';

export function GeneralSettings() {
  const { general, setGeneral } = useSettingsStore();
  const agentConnect = useAgentStore((s) => s.connect);
  const agentStatus = useAgentStore((s) => s.status);

  const [backendUrlError, setBackendUrlError] = useState<string | null>(null);
  const [wsUrlError, setWsUrlError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const handleBackendUrlChange = (value: string) => {
    setGeneral({ backendUrl: value });
    const result = validateHttpUrl(value);
    if (!result.valid) {
      setBackendUrlError(result.error);
    } else {
      setBackendUrlError(null);
    }
    setSaved(false);
  };

  const handleWsUrlChange = (value: string) => {
    setGeneral({ wsUrl: value });
    const result = validateWsUrl(value);
    if (!result.valid) {
      setWsUrlError(result.error);
    } else {
      setWsUrlError(null);
    }
    setSaved(false);
  };

  const handleApplyConnection = () => {
    const httpOk = validateHttpUrl(general.backendUrl);
    const wsOk = validateWsUrl(general.wsUrl);
    if (!httpOk.valid) {
      setBackendUrlError(httpOk.error);
      return;
    }
    if (!wsOk.valid) {
      setWsUrlError(wsOk.error);
      return;
    }

    // Reconnect the WebSocket agent with the new URL
    agentConnect(general.wsUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <SettingsCard title="General" description="Local UI preferences and connection settings.">
      <div className="settingsGrid">
        <TextField
          label="Backend URL"
          description="REST API base URL for the backend server."
          value={general.backendUrl}
          placeholder="http://localhost:8000"
          onChange={handleBackendUrlChange}
        />
        {backendUrlError && <div className="settingsFieldError">{backendUrlError}</div>}

        <TextField
          label="WebSocket URL"
          description="WebSocket endpoint for real-time agent communication."
          value={general.wsUrl}
          placeholder="ws://localhost:8000/api/v1/ws"
          onChange={handleWsUrlChange}
        />
        {wsUrlError && <div className="settingsFieldError">{wsUrlError}</div>}

        <ToggleRow
          label="Auto-scroll"
          description="Keep the message view pinned to the latest message."
          checked={general.autoScroll}
          onChange={(v) => setGeneral({ autoScroll: v })}
        />
        <ToggleRow
          label="Render Markdown"
          description="Show Markdown formatting in chat messages."
          checked={general.showMarkdown}
          onChange={(v) => setGeneral({ showMarkdown: v })}
        />
      </div>

      <div className="settingsActions">
        <button
          className="settingsButton"
          onClick={handleApplyConnection}
          disabled={!!backendUrlError || !!wsUrlError}
        >
          {saved ? 'Applied ✓' : 'Apply Connection'}
        </button>
        <span className="settingsStatus">
          Agent: <span className={`settingsStatus__dot settingsStatus__dot--${agentStatus}`} />
          {agentStatus}
        </span>
      </div>

      <div className="settingsSaved">Changes saved locally. Click "Apply Connection" to reconnect.</div>
    </SettingsCard>
  );
}