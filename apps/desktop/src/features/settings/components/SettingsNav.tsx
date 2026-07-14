import { SettingsSectionKey } from '../settingsStore';
import './settings.css';

const navItems: Array<{ key: SettingsSectionKey; label: string }> = [
  { key: 'general', label: 'General' },
  { key: 'agent', label: 'Agent' },
  { key: 'aiProviders', label: 'AI Providers' },
  { key: 'voice', label: 'Voice' },
  { key: 'memory', label: 'Memory' },
  { key: 'automation', label: 'Automation' },
  { key: 'notifications', label: 'Notifications' },
  { key: 'appearance', label: 'Appearance' },
  { key: 'about', label: 'About' },
];

export function SettingsNav({
  active,
  onChange,
}: {
  active: SettingsSectionKey;
  onChange: (key: SettingsSectionKey) => void;
}) {
  return (
    <div className="settingsNav">
      <div className="settingsNav__title">Settings</div>
      <div className="settingsNav__items">
        {navItems.map((it) => (
          <button
            key={it.key}
            type="button"
            className={`settingsNav__item ${active === it.key ? 'settingsNav__item--active' : ''}`}
            onClick={() => onChange(it.key)}
          >
            {it.label}
          </button>
        ))}
      </div>
    </div>
  );
}

