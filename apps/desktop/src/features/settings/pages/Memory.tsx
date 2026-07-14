import { useSettingsStore } from '../settingsStore';
import { SettingsCard } from '../components/SettingsCard';
import { ToggleRow } from '../components/controls/ToggleRow';
import { SliderField } from '../components/controls/SliderField';

export function MemorySettings() {
  const { memory, setMemory } = useSettingsStore();

  return (
    <SettingsCard title="Memory" description="Local memory behavior (UI-only for now).">
      <div className="settingsGrid">
        <ToggleRow
          label="Enable memory"
          description="Let the assistant store long-term details."
          checked={memory.enabled}
          onChange={(v) => setMemory({ enabled: v })}
        />

        <SliderField
          label="Max items"
          description="Upper limit for stored memory entries."
          min={50}
          max={2000}
          step={50}
          value={memory.maxItems}
          onChange={(v) => setMemory({ maxItems: v })}
          formatValue={(v) => `${v} items`}
        />
      </div>
      <div className="settingsSaved">Saved locally (no backend).</div>
    </SettingsCard>
  );
}

