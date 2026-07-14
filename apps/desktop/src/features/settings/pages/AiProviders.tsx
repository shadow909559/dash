import { useSettingsStore } from '../settingsStore';
import { SettingsCard } from '../components/SettingsCard';
import { SelectField } from '../components/controls/SelectField';
import { TextField } from '../components/controls/TextField';

export function AiProvidersSettings() {
  const { aiProviders, setAiProviders } = useSettingsStore();

  const handleApiKeyChange = (value: string) => {
    setAiProviders({ apiKey: value });
  };

  return (
    <SettingsCard
      title="AI Providers"
      description="Select which provider, model and API key to use."
    >
      <div className="settingsGrid">
        <SelectField
          label="Provider"
          description="How the assistant should connect to an AI model."
          value={aiProviders.provider}
          onChange={(v) => setAiProviders({ provider: v as SettingsStoreProvider })}
          options={[
            { value: 'openai', label: 'OpenAI-compatible' },
            { value: 'ollama', label: 'Ollama (local)' },
            { value: 'other', label: 'Other / Custom' },
          ]}
        />

        <TextField
          label="Model"
          description="Model identifier (provider-dependent)."
          value={aiProviders.model}
          placeholder="e.g. gpt-4o-mini"
          onChange={(v) => setAiProviders({ model: v })}
        />

        <TextField
          label="API Key"
          description={
            aiProviders.provider === 'ollama'
              ? 'Not required for local Ollama.'
              : 'Your API key for the selected provider.'
          }
          value={aiProviders.apiKey}
          placeholder={
            aiProviders.provider === 'ollama'
              ? 'Ollama does not require an API key'
              : 'sk-...'
          }
          onChange={handleApiKeyChange}
        />
      </div>

      <div className="settingsSaved">All settings are saved locally and applied in real-time.</div>
    </SettingsCard>
  );
}

type SettingsStoreProvider = 'openai' | 'ollama' | 'other';