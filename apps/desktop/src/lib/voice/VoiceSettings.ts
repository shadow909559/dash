/**
 * VoiceSettings - Manages voice configuration and settings UI
 * 
 * Features:
 * - Voice speed control
 * - Pitch control
 * - Volume control
 * - Voice selection
 * - Language selection
 * - Accent selection
 * - Settings persistence
 */

import { EventEmitter } from '../EventEmitter';

export interface VoiceSettingsConfig {
  speed: number;
  pitch: number;
  volume: number;
  voice: string;
  language: string;
  accent: string;
  wakeWordEnabled: boolean;
  wakeWord: string;
  sensitivity: number;
  autoGain: boolean;
  noiseSuppression: boolean;
  echoCancellation: boolean;
}

export class VoiceSettings extends EventEmitter {
  private config: VoiceSettingsConfig;
  private isInitialized: boolean = false;
  private availableVoices: SpeechSynthesisVoice[] = [];
  private supportedLanguages: string[] = [
    'en-US',
    'en-GB',
    'hi-IN',
    'mr-IN',
    'es-ES',
    'fr-FR',
    'de-DE',
    'ja-JP',
    'zh-CN',
  ];

  constructor(config?: Partial<VoiceSettingsConfig>) {
    super();
    this.config = {
      speed: 1.0,
      pitch: 1.0,
      volume: 1.0,
      voice: 'default',
      language: 'en-US',
      accent: 'neutral',
      wakeWordEnabled: true,
      wakeWord: 'DASH',
      sensitivity: 0.7,
      autoGain: true,
      noiseSuppression: true,
      echoCancellation: true,
      ...config,
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[VoiceSettings] Initializing...');

      // Load saved settings
      await this.loadSettings();

      // Load available voices
      await this.loadVoices();

      this.isInitialized = true;
      console.log('[VoiceSettings] Initialized successfully');

    } catch (error) {
      console.error('[VoiceSettings] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async loadVoices(): Promise<void> {
    return new Promise((resolve) => {
      const synthesis = window.speechSynthesis;
      
      const loadVoices = () => {
        this.availableVoices = synthesis.getVoices();
        console.log(`[VoiceSettings] Loaded ${this.availableVoices.length} voices`);
        resolve();
      };

      if (synthesis.getVoices().length > 0) {
        loadVoices();
      } else {
        synthesis.onvoiceschanged = loadVoices;
      }
    });
  }

  getAvailableVoices(): SpeechSynthesisVoice[] {
    return [...this.availableVoices];
  }

  getVoicesForLanguage(language: string): SpeechSynthesisVoice[] {
    return this.availableVoices.filter(voice => voice.lang === language);
  }

  getSupportedLanguages(): string[] {
    return [...this.supportedLanguages];
  }

  getLanguageName(languageCode: string): string {
    const names: Record<string, string> = {
      'en-US': 'English (US)',
      'en-GB': 'English (UK)',
      'hi-IN': 'Hindi (India)',
      'mr-IN': 'Marathi (India)',
      'es-ES': 'Spanish (Spain)',
      'fr-FR': 'French (France)',
      'de-DE': 'German (Germany)',
      'ja-JP': 'Japanese (Japan)',
      'zh-CN': 'Chinese (China)',
    };
    return names[languageCode] || languageCode;
  }

  // Settings getters/setters
  setSpeed(speed: number): void {
    const clampedSpeed = Math.max(0.5, Math.min(2.0, speed));
    this.config.speed = clampedSpeed;
    this.emit('speedChanged', clampedSpeed);
    this.saveSettings();
  }

  getSpeed(): number {
    return this.config.speed;
  }

  setPitch(pitch: number): void {
    const clampedPitch = Math.max(0.5, Math.min(2.0, pitch));
    this.config.pitch = clampedPitch;
    this.emit('pitchChanged', clampedPitch);
    this.saveSettings();
  }

  getPitch(): number {
    return this.config.pitch;
  }

  setVolume(volume: number): void {
    const clampedVolume = Math.max(0, Math.min(1.0, volume));
    this.config.volume = clampedVolume;
    this.emit('volumeChanged', clampedVolume);
    this.saveSettings();
  }

  getVolume(): number {
    return this.config.volume;
  }

  setVoice(voice: string): void {
    this.config.voice = voice;
    this.emit('voiceChanged', voice);
    this.saveSettings();
  }

  getVoice(): string {
    return this.config.voice;
  }

  setLanguage(language: string): void {
    if (this.supportedLanguages.includes(language)) {
      this.config.language = language;
      this.emit('languageChanged', language);
      this.saveSettings();
    } else {
      console.warn('[VoiceSettings] Unsupported language:', language);
    }
  }

  getLanguage(): string {
    return this.config.language;
  }

  setAccent(accent: string): void {
    this.config.accent = accent;
    this.emit('accentChanged', accent);
    this.saveSettings();
  }

  getAccent(): string {
    return this.config.accent;
  }

  setWakeWordEnabled(enabled: boolean): void {
    this.config.wakeWordEnabled = enabled;
    this.emit('wakeWordEnabledChanged', enabled);
    this.saveSettings();
  }

  isWakeWordEnabled(): boolean {
    return this.config.wakeWordEnabled;
  }

  setWakeWord(wakeWord: string): void {
    this.config.wakeWord = wakeWord;
    this.emit('wakeWordChanged', wakeWord);
    this.saveSettings();
  }

  getWakeWord(): string {
    return this.config.wakeWord;
  }

  setSensitivity(sensitivity: number): void {
    const clampedSensitivity = Math.max(0, Math.min(1.0, sensitivity));
    this.config.sensitivity = clampedSensitivity;
    this.emit('sensitivityChanged', clampedSensitivity);
    this.saveSettings();
  }

  getSensitivity(): number {
    return this.config.sensitivity;
  }

  setAutoGain(enabled: boolean): void {
    this.config.autoGain = enabled;
    this.emit('autoGainChanged', enabled);
    this.saveSettings();
  }

  isAutoGainEnabled(): boolean {
    return this.config.autoGain;
  }

  setNoiseSuppression(enabled: boolean): void {
    this.config.noiseSuppression = enabled;
    this.emit('noiseSuppressionChanged', enabled);
    this.saveSettings();
  }

  isNoiseSuppressionEnabled(): boolean {
    return this.config.noiseSuppression;
  }

  setEchoCancellation(enabled: boolean): void {
    this.config.echoCancellation = enabled;
    this.emit('echoCancellationChanged', enabled);
    this.saveSettings();
  }

  isEchoCancellationEnabled(): boolean {
    return this.config.echoCancellation;
  }

  getAllSettings(): VoiceSettingsConfig {
    return { ...this.config };
  }

  updateSettings(settings: Partial<VoiceSettingsConfig>): void {
    this.config = { ...this.config, ...settings };
    this.emit('settingsUpdated', this.config);
    this.saveSettings();
  }

  resetToDefaults(): void {
    this.config = {
      speed: 1.0,
      pitch: 1.0,
      volume: 1.0,
      voice: 'default',
      language: 'en-US',
      accent: 'neutral',
      wakeWordEnabled: true,
      wakeWord: 'DASH',
      sensitivity: 0.7,
      autoGain: true,
      noiseSuppression: true,
      echoCancellation: true,
    };
    this.emit('settingsReset', this.config);
    this.saveSettings();
  }

  private async loadSettings(): Promise<void> {
    try {
      const stored = localStorage.getItem('dash_voice_settings');
      if (stored) {
        const settings = JSON.parse(stored);
        this.config = { ...this.config, ...settings };
        console.log('[VoiceSettings] Settings loaded from storage');
      }
    } catch (error) {
      console.error('[VoiceSettings] Failed to load settings:', error);
    }
  }

  private async saveSettings(): Promise<void> {
    try {
      localStorage.setItem('dash_voice_settings', JSON.stringify(this.config));
    } catch (error) {
      console.error('[VoiceSettings] Failed to save settings:', error);
    }
  }

  async shutdown(): Promise<void> {
    await this.saveSettings();
    this.isInitialized = false;
    console.log('[VoiceSettings] Shutdown complete');
  }
}
