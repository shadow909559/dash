/**
 * VoiceActivityDetection - Detects when user is speaking, silent, or has stopped
 * 
 * Features:
 * - Real-time speech detection
 * - Silence detection
 * - Speech pause detection
 * - User interruption detection
 * - Configurable thresholds
 */

import { EventEmitter } from '../EventEmitter';

export interface VADConfig {
  speechThreshold: number;
  silenceThreshold: number;
  minSpeechDuration: number;
  minSilenceDuration: number;
  pauseThreshold: number;
}

export interface VADState {
  isSpeaking: boolean;
  isSilent: boolean;
  isPaused: boolean;
  speechStartTime: number | null;
  silenceStartTime: number | null;
  lastSpeechTime: number;
}

export class VoiceActivityDetection extends EventEmitter {
  private config: VADConfig;
  private state: VADState;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private isInitialized: boolean = false;
  private isRunning: boolean = false;
  private processingInterval: number | null = null;
  private energyHistory: number[] = [];
  private maxHistoryLength: number = 50;

  constructor(config: any) {
    super();
    this.config = {
      speechThreshold: config.speechThreshold || 0.15,
      silenceThreshold: config.silenceThreshold || 0.05,
      minSpeechDuration: config.minSpeechDuration || 300,
      minSilenceDuration: config.minSilenceDuration || 500,
      pauseThreshold: config.pauseThreshold || 1000,
    };

    this.state = {
      isSpeaking: false,
      isSilent: true,
      isPaused: false,
      speechStartTime: null,
      silenceStartTime: null,
      lastSpeechTime: 0,
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[VoiceActivityDetection] Initializing...');

      const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioContext({
        sampleRate: 16000,
      });

      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 2048;
      this.analyser.smoothingTimeConstant = 0.5;

      this.isInitialized = true;
      console.log('[VoiceActivityDetection] Initialized successfully');

    } catch (error) {
      console.error('[VoiceActivityDetection] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async start(): Promise<void> {
    if (!this.isInitialized) {
      throw new Error('VoiceActivityDetection not initialized');
    }

    if (this.isRunning) {
      console.warn('[VoiceActivityDetection] Already running');
      return;
    }

    try {
      this.isRunning = true;
      this.energyHistory = [];

      // Process audio every 50ms for responsive detection
      this.processingInterval = window.setInterval(() => {
        this.processAudio();
      }, 50);

      this.emit('started');
      console.log('[VoiceActivityDetection] Started');

    } catch (error) {
      console.error('[VoiceActivityDetection] Failed to start:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async stop(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    try {
      if (this.processingInterval) {
        clearInterval(this.processingInterval);
        this.processingInterval = null;
      }

      this.isRunning = false;
      this.emit('stopped');

      console.log('[VoiceActivityDetection] Stopped');

    } catch (error) {
      console.error('[VoiceActivityDetection] Failed to stop:', error);
      this.emit('error', error);
    }
  }

  processAudioData(audioData: Float32Array): void {
    if (!this.isRunning) {
      return;
    }

    // Calculate RMS energy
    let sum = 0;
    for (let i = 0; i < audioData.length; i++) {
      sum += audioData[i] * audioData[i];
    }
    const rms = Math.sqrt(sum / audioData.length);

    this.analyzeEnergy(rms);
  }

  getState(): VADState {
    return { ...this.state };
  }

  updateConfig(config: Partial<VADConfig>): void {
    this.config = { ...this.config, ...config };
  }

  async shutdown(): Promise<void> {
    await this.stop();

    if (this.audioContext) {
      await this.audioContext.close();
      this.audioContext = null;
    }

    this.isInitialized = false;
    console.log('[VoiceActivityDetection] Shutdown complete');
  }

  private processAudio(): void {
    if (!this.analyser) {
      return;
    }

    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Float32Array(bufferLength);
    this.analyser.getFloatTimeDomainData(dataArray);

    // Calculate RMS energy
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i] * dataArray[i];
    }
    const rms = Math.sqrt(sum / dataArray.length);

    this.analyzeEnergy(rms);
  }

  private analyzeEnergy(currentEnergy: number): void {
    const now = Date.now();

    // Add to energy history
    this.energyHistory.push(currentEnergy);
    if (this.energyHistory.length > this.maxHistoryLength) {
      this.energyHistory.shift();
    }

    // Calculate average energy over recent history
    const averageEnergy = this.energyHistory.reduce((a, b) => a + b, 0) / this.energyHistory.length;

    // Detect speech vs silence
    if (averageEnergy > this.config.speechThreshold) {
      this.handleSpeechDetected(now);
    } else if (averageEnergy < this.config.silenceThreshold) {
      this.handleSilenceDetected(now);
    } else {
      this.handleAmbientLevel(now);
    }

    // Check for pause (speech stopped but not silence)
    if (this.state.isSpeaking && !this.state.isSilent) {
      const timeSinceLastSpeech = now - this.state.lastSpeechTime;
      if (timeSinceLastSpeech > this.config.pauseThreshold) {
        this.handlePauseDetected(now);
      }
    }
  }

  private handleSpeechDetected(now: number): void {
    if (!this.state.isSpeaking) {
      // Speech just started
      this.state.isSpeaking = true;
      this.state.isSilent = false;
      this.state.isPaused = false;
      this.state.speechStartTime = now;
      this.emit('speechStarted');
      console.log('[VoiceActivityDetection] Speech started');
    }

    this.state.lastSpeechTime = now;
    this.state.silenceStartTime = null;
  }

  private handleSilenceDetected(now: number): void {
    if (!this.state.isSilent) {
      // Silence just started
      this.state.isSilent = true;
      this.state.silenceStartTime = now;
    }

    // Check if silence has lasted long enough to consider speech ended
    if (this.state.isSpeaking && this.state.silenceStartTime) {
      const silenceDuration = now - this.state.silenceStartTime;
      if (silenceDuration >= this.config.minSilenceDuration) {
        this.handleSpeechEnded(now);
      }
    }

    this.emit('silenceDetected');
  }

  private handleAmbientLevel(now: number): void {
    // Between speech and silence thresholds - maintain current state
    this.state.lastSpeechTime = now;
  }

  private handleSpeechEnded(now: number): void {
    if (!this.state.isSpeaking) {
      return;
    }

    // Check if speech lasted long enough to be valid
    if (this.state.speechStartTime) {
      const speechDuration = now - this.state.speechStartTime;
      if (speechDuration >= this.config.minSpeechDuration) {
        this.state.isSpeaking = false;
        this.state.isPaused = false;
        this.emit('speechEnded');
        console.log('[VoiceActivityDetection] Speech ended');
      } else {
        // Speech was too short, ignore it
        this.state.isSpeaking = false;
        this.state.speechStartTime = null;
      }
    }
  }

  private handlePauseDetected(now: number): void {
    if (!this.state.isPaused) {
      this.state.isPaused = true;
      this.emit('pauseDetected');
      console.log('[VoiceActivityDetection] Pause detected');
    }
  }

  /**
   * Check if user interrupted (started speaking while AI was speaking)
   */
  checkInterruption(audioData: Float32Array): boolean {
    let sum = 0;
    for (let i = 0; i < audioData.length; i++) {
      sum += audioData[i] * audioData[i];
    }
    const rms = Math.sqrt(sum / audioData.length);

    // If energy is high, user might be interrupting
    return rms > this.config.speechThreshold * 1.5;
  }
}
