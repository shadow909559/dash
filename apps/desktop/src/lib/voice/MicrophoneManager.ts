/**
 * MicrophoneManager - Handles microphone selection, audio capture, and preprocessing
 * 
 * Features:
 * - Automatic microphone selection
 * - Noise suppression
 * - Echo cancellation
 * - Auto gain control
 * - Multi-microphone support
 * - Error recovery
 */

import { EventEmitter } from '../EventEmitter';

export interface MicrophoneDevice {
  deviceId: string;
  label: string;
  groupId: string;
}

export interface AudioConfig {
  autoGain: boolean;
  noiseSuppression: boolean;
  echoCancellation: boolean;
  sampleRate: number;
  channelCount: number;
}

export class MicrophoneManager extends EventEmitter {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private gainNode: GainNode | null = null;
  private noiseFilter: BiquadFilterNode | null = null;
  private analyser: AnalyserNode | null = null;
  private currentDeviceId: string | null = null;
  private devices: MicrophoneDevice[] = [];
  private config: AudioConfig;
  private isInitialized: boolean = false;
  private isRecording: boolean = false;

  constructor(config: any) {
    super();
    this.config = {
      autoGain: config.autoGain ?? true,
      noiseSuppression: config.noiseSuppression ?? true,
      echoCancellation: config.echoCancellation ?? true,
      sampleRate: 16000,
      channelCount: 1,
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[MicrophoneManager] Initializing...');

      // Request microphone permissions
      await this.requestPermissions();

      // Initialize audio context
      const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioContext({
        sampleRate: this.config.sampleRate,
      });

      // Get available devices
      await this.enumerateDevices();

      // Select best microphone
      await this.selectBestMicrophone();

      this.isInitialized = true;
      console.log('[MicrophoneManager] Initialized successfully');

    } catch (error) {
      console.error('[MicrophoneManager] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async start(): Promise<void> {
    if (!this.isInitialized) {
      throw new Error('MicrophoneManager not initialized');
    }

    if (this.isRecording) {
      console.warn('[MicrophoneManager] Already recording');
      return;
    }

    try {
      // Get stream with selected device
      const constraints: MediaStreamConstraints = {
        audio: {
          deviceId: this.currentDeviceId ? { exact: this.currentDeviceId } : undefined,
          noiseSuppression: this.config.noiseSuppression,
          echoCancellation: this.config.echoCancellation,
          sampleRate: this.config.sampleRate,
          channelCount: this.config.channelCount,
        },
      };

      this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);

      // Create audio processing chain
      this.createAudioChain();

      this.isRecording = true;
      this.emit('started');

      console.log('[MicrophoneManager] Started recording');

    } catch (error) {
      console.error('[MicrophoneManager] Failed to start:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async stop(): Promise<void> {
    if (!this.isRecording) {
      return;
    }

    try {
      // Stop media stream
      if (this.mediaStream) {
        this.mediaStream.getTracks().forEach(track => track.stop());
        this.mediaStream = null;
      }

      // Disconnect audio nodes
      if (this.sourceNode) {
        this.sourceNode.disconnect();
        this.sourceNode = null;
      }

      if (this.gainNode) {
        this.gainNode.disconnect();
        this.gainNode = null;
      }

      if (this.noiseFilter) {
        this.noiseFilter.disconnect();
        this.noiseFilter = null;
      }

      this.isRecording = false;
      this.emit('stopped');

      console.log('[MicrophoneManager] Stopped recording');

    } catch (error) {
      console.error('[MicrophoneManager] Failed to stop:', error);
      this.emit('error', error);
    }
  }

  async selectDevice(deviceId: string): Promise<void> {
    if (this.currentDeviceId === deviceId) {
      return;
    }

    const wasRecording = this.isRecording;
    if (wasRecording) {
      await this.stop();
    }

    this.currentDeviceId = deviceId;
    this.emit('deviceChanged', deviceId);

    if (wasRecording) {
      await this.start();
    }
  }

  getAudioData(): Float32Array | null {
    if (!this.analyser) {
      return null;
    }

    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Float32Array(bufferLength);
    this.analyser.getFloatTimeDomainData(dataArray);
    return dataArray;
  }

  getAmplitude(): number {
    const audioData = this.getAudioData();
    if (!audioData) {
      return 0;
    }

    let sum = 0;
    for (let i = 0; i < audioData.length; i++) {
      sum += audioData[i] * audioData[i];
    }
    return Math.sqrt(sum / audioData.length);
  }

  getDevices(): MicrophoneDevice[] {
    return [...this.devices];
  }

  getCurrentDevice(): string | null {
    return this.currentDeviceId;
  }

  updateConfig(config: Partial<AudioConfig>): void {
    this.config = { ...this.config, ...config };
  }

  async shutdown(): Promise<void> {
    await this.stop();

    if (this.audioContext) {
      await this.audioContext.close();
      this.audioContext = null;
    }

    this.isInitialized = false;
    console.log('[MicrophoneManager] Shutdown complete');
  }

  private async requestPermissions(): Promise<void> {
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('[MicrophoneManager] Microphone permissions granted');
    } catch (error) {
      console.error('[MicrophoneManager] Microphone permissions denied:', error);
      throw new Error('Microphone permissions required');
    }
  }

  private async enumerateDevices(): Promise<void> {
    const devices = await navigator.mediaDevices.enumerateDevices();
    this.devices = devices
      .filter(device => device.kind === 'audioinput')
      .map(device => ({
        deviceId: device.deviceId,
        label: device.label || `Microphone ${this.devices.length + 1}`,
        groupId: device.groupId,
      }));

    console.log(`[MicrophoneManager] Found ${this.devices.length} microphones`);
  }

  private async selectBestMicrophone(): Promise<void> {
    if (this.devices.length === 0) {
      throw new Error('No microphones found');
    }

    // Prefer devices with labels (system permissions granted)
    const labeledDevices = this.devices.filter(d => d.label && !d.label.startsWith('Microphone '));
    
    if (labeledDevices.length > 0) {
      // Select first labeled device (usually default)
      this.currentDeviceId = labeledDevices[0].deviceId;
    } else {
      // Fallback to first available device
      this.currentDeviceId = this.devices[0].deviceId;
    }

    console.log(`[MicrophoneManager] Selected microphone: ${this.currentDeviceId}`);
  }

  private createAudioChain(): void {
    if (!this.audioContext || !this.mediaStream) {
      throw new Error('Audio context or media stream not available');
    }

    // Create source from media stream
    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

    // Create noise filter (high-pass to remove low-frequency noise)
    this.noiseFilter = this.audioContext.createBiquadFilter();
    this.noiseFilter.type = 'highpass';
    this.noiseFilter.frequency.value = 80; // Remove frequencies below 80Hz
    this.noiseFilter.Q.value = 0.5;

    // Create gain node for auto gain
    this.gainNode = this.audioContext.createGain();
    this.gainNode.gain.value = 1.0;

    // Create analyser for amplitude detection
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 2048;
    this.analyser.smoothingTimeConstant = 0.8;

    // Connect audio chain: source -> noise filter -> gain -> analyser
    this.sourceNode.connect(this.noiseFilter);
    this.noiseFilter.connect(this.gainNode);
    this.gainNode.connect(this.analyser);

    // Don't connect to destination to avoid feedback
  }

  private applyAutoGain(): void {
    if (!this.gainNode || !this.analyser) {
      return;
    }

    const amplitude = this.getAmplitude();
    const targetAmplitude = 0.3; // Target RMS level
    const gain = this.gainNode.gain.value;

    // Simple AGC - adjust gain based on amplitude
    if (amplitude < targetAmplitude * 0.5) {
      this.gainNode.gain.value = Math.min(gain * 1.01, 3.0);
    } else if (amplitude > targetAmplitude * 1.5) {
      this.gainNode.gain.value = Math.max(gain * 0.99, 0.5);
    }
  }
}
