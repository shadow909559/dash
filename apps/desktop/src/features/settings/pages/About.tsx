import { SettingsCard } from '../components/SettingsCard';

export function AboutSettings() {
  return (
    <SettingsCard
      title="About"
      description="This settings UI is frontend-only and currently stored locally in memory."
    >
      <div className="settingsAbout">
        <div className="settingsAbout__row">
          <div className="settingsAbout__label">Version</div>
          <div className="settingsAbout__value">0.1.0</div>
        </div>
        <div className="settingsAbout__row">
          <div className="settingsAbout__label">Backend</div>
          <div className="settingsAbout__value">None (UI-only)</div>
        </div>
        <div className="settingsAbout__row">
          <div className="settingsAbout__label">Scope</div>
          <div className="settingsAbout__value">Settings module (desktop)</div>
        </div>
      </div>

      <div className="settingsSaved">Saved locally (no backend).</div>
    </SettingsCard>
  );
}

