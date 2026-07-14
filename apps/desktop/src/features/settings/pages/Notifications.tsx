import { useSettingsStore } from '../settingsStore';
import { SettingsCard } from '../components/SettingsCard';
import { ToggleRow } from '../components/controls/ToggleRow';

export function NotificationsSettings() {
  const { notifications, setNotifications } = useSettingsStore();

  return (
    <SettingsCard
      title="Notifications"
      description="Desktop notification behavior (UI-only)."
    >
      <div className="settingsGrid">
        <ToggleRow
          label="Enable notifications"
          description="Show assistant notifications."
          checked={notifications.enabled}
          onChange={(v) => setNotifications({ enabled: v })}
        />

        <ToggleRow
          label="Desktop only"
          description="Avoid forwarding notifications to other devices."
          checked={notifications.desktopOnly}
          onChange={(v) => setNotifications({ desktopOnly: v })}
        />
      </div>
      <div className="settingsSaved">Saved locally (no backend).</div>
    </SettingsCard>
  );
}


