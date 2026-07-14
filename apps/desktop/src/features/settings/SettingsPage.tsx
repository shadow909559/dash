import { useMemo, useState } from 'react';
import './settings.css';
import { SettingsLayout } from './components/SettingsLayout';
import { SettingsNav } from './components/SettingsNav';
import { SettingsSectionKey } from './settingsStore';
import { GeneralSettings } from './pages/General';
import { AgentSettings } from './pages/Agent';
import { AiProvidersSettings } from './pages/AiProviders';
import { VoiceSettings } from './pages/Voice';
import { MemorySettings } from './pages/Memory';
import { AutomationSettings } from './pages/Automation';
import { NotificationsSettings } from './pages/Notifications';
import { AppearanceSettings } from './pages/Appearance';
import { AboutSettings } from './pages/About';

export function SettingsPage() {
  const [active, setActive] = useState<SettingsSectionKey>('general');

  const content = useMemo(() => {
    switch (active) {
      case 'general':
        return <GeneralSettings />;
      case 'agent':
        return <AgentSettings />;
      case 'aiProviders':
        return <AiProvidersSettings />;
      case 'voice':
        return <VoiceSettings />;
      case 'memory':
        return <MemorySettings />;
      case 'automation':
        return <AutomationSettings />;
      case 'notifications':
        return <NotificationsSettings />;
      case 'appearance':
        return <AppearanceSettings />;
      case 'about':
        return <AboutSettings />;
      default:
        return <GeneralSettings />;
    }
  }, [active]);

  return (
    <SettingsLayout
      nav={<SettingsNav active={active} onChange={(k) => setActive(k)} />}
    >
      <div className="settingsPage">
        {content}
      </div>
    </SettingsLayout>
  );
}

