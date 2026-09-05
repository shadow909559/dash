/**
 * InterruptController - Handles user interruption during AI speech
 * 
 * Features:
 * - Detect user interruption
 * - Stop AI speech immediately
 * - Switch to listening mode
 * - Resume conversation after interruption
 * - Configurable sensitivity
 */

import { EventEmitter } from '../EventEmitter';

export interface InterruptConfig {
  enabled: boolean;
  sensitivity: number;
  minInterruptionDuration: number;
  autoResumeListening: boolean;
}

export class InterruptController extends EventEmitter {
  private config: InterruptConfig;
  private isInitialized: boolean = false;
  private isMonitoring: boolean = false;
  private vad: any = null;
  private interruptionStartTime: number = 0;
  private monitoringInterval: number | null = null;

  constructor(config: any) {
    super();
    this.config = {
      enabled: true,
      sensitivity: config.sensitivity || 0.7,
      minInterruptionDuration: 300,
      autoResumeListening: true,
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[InterruptController] Initializing...');

      // Initialize VAD for interruption detection
      const { VoiceActivityDetection } = await import('./VoiceActivityDetection');
      this.vad = new VoiceActivityDetection(this.config);
      await this.vad.initialize();

      // Setup VAD event handlers
      this.vad.on('speechStarted', () => {
        this.handleSpeechStarted();
      });

      this.vad.on('speechEnded', () => {
        this.handleSpeechEnded();
      });

      this.isInitialized = true;
      console.log('[InterruptController] Initialized successfully');

    } catch (error) {
      console.error('[InterruptController] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async startMonitoring(): Promise<void> {
    if (!this.isInitialized) {
      throw new Error('InterruptController not initialized');
    }

    if (!this.config.enabled) {
      console.log('[InterruptController] Interrupt detection disabled');
      return;
    }

    if (this.isMonitoring) {
      console.warn('[InterruptController] Already monitoring');
      return;
    }

    try {
      await this.vad.start();
      this.isMonitoring = true;
      this.emit('monitoringStarted');
      console.log('[InterruptController] Started monitoring');

    } catch (error) {
      console.error('[InterruptController] Failed to start monitoring:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async stopMonitoring(): Promise<void> {
    if (!this.isMonitoring) {
      return;
    }

    try {
      await this.vad.stop();
      this.isMonitoring = false;
      this.emit('monitoringStopped');
      console.log('[InterruptController] Stopped monitoring');

    } catch (error) {
      console.error('[InterruptController] Failed to stop monitoring:', error);
      this.emit('error', error);
    }
  }

  processAudioData(audioData: Float32Array): void {
    if (!this.isMonitoring || !this.vad) {
      return;
    }

    // Check for interruption
    const isInterrupting = this.vad.checkInterruption(audioData);
    
    if (isInterrupting) {
      this.handleInterruption();
    }
  }

  private handleSpeechStarted(): void {
    const now = Date.now();
    this.interruptionStartTime = now;
  }

  private handleSpeechEnded(): void {
    const now = Date.now();
    const duration = now - this.interruptionStartTime;

    if (duration >= this.config.minInterruptionDuration) {
      this.handleInterruption();
    }
  }

  private handleInterruption(): void {
    this.emit('interrupt');
    console.log('[InterruptController] User interruption detected');
  }

  updateConfig(config: Partial<InterruptConfig>): void {
    this.config = { ...this.config, ...config };
    
    if (this.vad) {
      this.vad.updateConfig(this.config);
    }
  }

  async shutdown(): Promise<void> {
    await this.stopMonitoring();

    if (this.vad) {
      await this.vad.shutdown();
      this.vad = null;
    }

    this.isInitialized = false;
    console.log('[InterruptController] Shutdown complete');
  }
}
