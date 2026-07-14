import { useSettingsStore } from '../settingsStore';
import { SettingsCard } from '../components/SettingsCard';
import { ToggleRow } from '../components/controls/ToggleRow';

export function AutomationSettings() {
  const { automation, setAutomation } = useSettingsStore();

  return (
    <SettingsCard title="Automation" description="Allow the assistant to run workflows automatically (UI-only).">
      <div className="settingsGrid">
        <ToggleRow
          label="Enable automation"
          description="When enabled, the assistant may trigger automations without asking."
          checked={automation.enabled}
          onChange={(v) => setAutomation({ enabled: v })}
        />
      </div>
      <div className="settingsSaved">Saved locally (no backend).</div>
    </SettingsCard>
  );
}

