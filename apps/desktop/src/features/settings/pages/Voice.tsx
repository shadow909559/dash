import { useSettingsStore } from '../settingsStore';
import { SettingsCard } from '../components/SettingsCard';
import { ToggleRow } from '../components/controls/ToggleRow';
import { SliderField } from '../components/controls/SliderField';

export function VoiceSettings() {
  const { voice, setVoice } = useSettingsStore();

  return (
    <SettingsCard title="Voice" description="Voice input/output controls (UI-only).">
      <div className="settingsGrid">
        <ToggleRow
          label="Enable voice"
          description="Allows using microphone and speaking responses."
          checked={voice.voiceEnabled}
          onChange={(v) => setVoice({ voiceEnabled: v })}
        />

        <SliderField
          label="TTS volume"
          description="How loud the assistant speaks."
          value={voice.ttsVolume}
          onChange={(v) => setVoice({ ttsVolume: v })}
        />

        <SliderField
          label="STT sensitivity"
          description="How aggressively the assistant detects voice."
          value={voice.sttSensitivity}
          onChange={(v) => setVoice({ sttSensitivity: v })}
        />
      </div>
      <div className="settingsSaved">Saved locally (no backend).</div>
    </SettingsCard>
  );
}

