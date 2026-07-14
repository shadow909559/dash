import { useEffect } from 'react';
import { useSettingsStore } from '../settingsStore';
import { SettingsCard } from '../components/SettingsCard';
import { SelectField } from '../components/controls/SelectField';

function applyTheme(theme: string, accentColor: string) {
  const root = document.documentElement;

  // Set data-theme attribute for CSS-based theming
  root.setAttribute('data-theme', theme);

  // Set CSS custom properties for accent color
  root.style.setProperty('--accent-color', accentColor);

  // Smooth transition class
  root.classList.add('theme-transitioning');
  setTimeout(() => root.classList.remove('theme-transitioning'), 300);
}

export function AppearanceSettings() {
  const { appearance, setAppearance } = useSettingsStore();

  // Apply theme on mount and whenever it changes
  useEffect(() => {
    applyTheme(appearance.theme, appearance.accentColor);
  }, [appearance.theme, appearance.accentColor]);

  const handleThemeChange = (value: string) => {
    setAppearance({ theme: value as AppearanceTheme });
  };

  const handleAccentColorChange = (value: string) => {
    setAppearance({ accentColor: value });
  };

  return (
    <SettingsCard title="Appearance" description="Look & feel for the desktop UI. Changes apply instantly.">
      <div className="settingsGrid">
        <SelectField
          label="Theme"
          value={appearance.theme}
          onChange={handleThemeChange}
          options={[
            { value: 'dark', label: 'Dark' },
            { value: 'light', label: 'Light' },
            { value: 'system', label: 'System' },
          ]}
        />

        <div className="settingsField">
          <div className="settingsField__labelRow">
            <span className="settingsField__label">Accent color</span>
            <span className="settingsField__desc">Hex color used for highlights.</span>
          </div>
          <div className="settingsColorRow">
            <input
              className="settingsColorInput"
              type="color"
              value={appearance.accentColor}
              onChange={(e) => handleAccentColorChange(e.target.value)}
            />
            <input
              className="settingsField__input settingsField__input--compact"
              type="text"
              value={appearance.accentColor}
              placeholder="#6ea8fe"
              onChange={(e) => handleAccentColorChange(e.target.value)}
            />
          </div>
        </div>
      </div>
      <div className="settingsSaved">Changes applied instantly — no restart needed.</div>
    </SettingsCard>
  );
}

type AppearanceTheme = 'dark' | 'light' | 'system';