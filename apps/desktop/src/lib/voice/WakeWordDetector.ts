/**
 * WakeWordDetector - Low CPU wake word detection for "DASH"
 * 
 * Features:
 * - Very low CPU usage through efficient processing
 * - Support for "DASH" wake word
 * - Configurable sensitivity
 * - Can be disabled
 * - Future support for custom wake words
 */

import { EventEmitter } from '../EventEmitter';

export interface WakeWordConfig {
  wakeWord: string;
  enabled: boolean;
  sensitivity: number;
  debounceMs: number;
  minConfidence: number;
}

export class WakeWordDetector extends EventEmitter {
  private config: WakeWordConfig;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private isRunning: boolean = false;
  private isInitialized: boolean = false;
  private lastDetectionTime: number = 0;
  private processingInterval: number | null = null;
  private bufferSize: number = 2048;
  
  // Simple phonetic pattern for "DASH"
  // D: /d/ - plosive, high energy burst
  // A: /æ/ - vowel, sustained
  // SH: /ʃ/ - fricative, high frequency
  // Phonetic energy patterns for all supported wake words
  private wakeWordPatterns: Record<string, number[]> = {
    'dash': [0.8, 0.4, 0.6, 0.3, 0.7, 0.2],           // DASH
    'hey dash': [0.5, 0.7, 0.8, 0.4, 0.6, 0.3, 0.7, 0.2], // Hey DASH
    'dash listen': [0.8, 0.4, 0.6, 0.7, 0.5, 0.6, 0.4],    // DASH listen
    'wake up dash': [0.6, 0.5, 0.7, 0.6, 0.8, 0.4, 0.6, 0.3, 0.7, 0.2] // Wake up DASH
  };
  
  private currentPattern: number[] = [];
  private patternIndex: number = 0;
  private energyHistory: number[] = [];
  private microphoneStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;

  constructor(config: any) {
    super();
    
    // Enable all wake words by default
    this.config = {
      wakeWord: 'all',
      enabled: config.wakeWordEnabled !== false,
      sensitivity: config.sensitivity || 0.7,
      debounceMs: 1500, // Increased debounce to prevent false triggers
      minConfidence: 0.6,
    };
    
    // Initialize to monitor all wake words
    this.enableAllWakeWords();
  }

  async initialize(): Promise<void> {
    try {
      console.log('[WakeWordDetector] Initializing...');

      const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioContext({
        sampleRate: 16000, // Lower sample rate for CPU efficiency
      });

      // Get microphone access
      this.microphoneStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          sampleSize: 16,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });

      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = this.bufferSize;
      this.analyser.smoothingTimeConstant = 0.3;

      // Connect microphone to analyser
      this.sourceNode = this.audioContext.createMediaStreamSource(this.microphoneStream);
      this.sourceNode.connect(this.analyser);

      this.isInitialized = true;
      console.log('[WakeWordDetector] Initialized successfully');

    } catch (error) {
      console.error('[WakeWordDetector] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async start(): Promise<void> {
    if (!this.isInitialized) {
      throw new Error('WakeWordDetector not initialized');
    }

    if (!this.config.enabled) {
      console.log('[WakeWordDetector] Wake word detection disabled');
      return;
    }

    if (this.isRunning) {
      console.warn('[WakeWordDetector] Already running');
      return;
    }

    try {
      this.isRunning = true;
      this.patternIndex = 0;
      this.energyHistory = [];

      // Process audio at 100ms intervals for low CPU usage
      this.processingInterval = window.setInterval(() => {
        this.processAudio();
      }, 100);

      this.emit('started');
      console.log('[WakeWordDetector] Started');

    } catch (error) {
      console.error('[WakeWordDetector] Failed to start:', error);
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

      console.log('[WakeWordDetector] Stopped');

    } catch (error) {
      console.error('[WakeWordDetector] Failed to stop:', error);
      this.emit('error', error);
    }
  }

  setAudioData(audioData: Float32Array): void {
    if (!this.analyser || !this.isRunning) {
      return;
    }

    // In a real implementation, this would connect to the microphone stream
    // For now, we'll use the data directly for pattern matching
    this.analyzeAudioPattern(audioData);
  }

  updateConfig(config: Partial<WakeWordConfig>): void {
    this.config = { ...this.config, ...config };
  }

  async shutdown(): Promise<void> {
    await this.stop();

    if (this.audioContext) {
      await this.audioContext.close();
      this.audioContext = null;
    }

    this.isInitialized = false;
    console.log('[WakeWordDetector] Shutdown complete');
  }

  private processAudio(): void {
    if (!this.analyser) {
      return;
    }

    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Float32Array(bufferLength);
    this.analyser.getFloatTimeDomainData(dataArray);

    this.analyzeAudioPattern(dataArray);
  }

  private analyzeAudioPattern(audioData: Float32Array): void {
    // Calculate RMS energy
    let sum = 0;
    for (let i = 0; i < audioData.length; i++) {
      sum += audioData[i] * audioData[i];
    }
    const rms = Math.sqrt(sum / audioData.length);

    // Add to energy history
    this.energyHistory.push(rms);
    if (this.energyHistory.length > 10) {
      this.energyHistory.shift();
    }

    // Check for DASH pattern
    this.checkDashPattern(rms);
  }

  private checkDashPattern(rms: number): void {
    // Check debounce first
    const now = Date.now();
    if (now - this.lastDetectionTime < this.config.debounceMs) {
      return;
    }

    // Normalize energy to 0-1 range
    const normalizedEnergy = Math.min(rms * 5, 1.0);
    this.energyHistory.push(normalizedEnergy);
    if (this.energyHistory.length > 20) {
      this.energyHistory.shift();
    }

    // Check all wake word patterns for potential matches
    for (const [wakeWord, pattern] of Object.entries(this.wakeWordPatterns)) {
      const matchLength = pattern.length;
      if (this.energyHistory.length >= matchLength) {
        const recentEnergy = this.energyHistory.slice(-matchLength);
        const confidence = this.calculatePatternConfidence(recentEnergy, pattern);
        
        if (confidence >= this.config.minConfidence) {
          this.lastDetectionTime = now;
          this.emit('detected', wakeWord);
          console.log(`[WakeWordDetector] Wake word detected: "${wakeWord}" (confidence: ${confidence.toFixed(2)})`);
          this.energyHistory = []; // Reset after detection
          return;
        }
      }
    }
  }

  private calculatePatternConfidence(actual: number[], expected: number[]): number {
    let matchScore = 0;
    for (let i = 0; i < expected.length; i++) {
      const diff = Math.abs(actual[i] - expected[i]);
      matchScore += (1 - diff);
    }
    return matchScore / expected.length;
  }

  private calculateConfidence(): number {
    if (this.energyHistory.length < this.currentPattern.length) {
      return 0;
    }

    // Calculate how well the recent energy history matches the wake word pattern
    let matchScore = 0;
    const recentEnergy = this.energyHistory.slice(-this.currentPattern.length);

    for (let i = 0; i < this.currentPattern.length; i++) {
      const normalizedEnergy = Math.min(recentEnergy[i] * 5, 1.0);
      const expectedEnergy = this.currentPattern[i];
      const diff = Math.abs(normalizedEnergy - expectedEnergy);
      matchScore += (1 - diff);
    }

    return matchScore / this.currentPattern.length;
  }

  /**
   * Set wake word with support for all configured wake words
   */
  setWakeWord(wakeWord: string): void {
    const normalized = wakeWord.toLowerCase();
    if (this.wakeWordPatterns[normalized]) {
      this.currentPattern = this.wakeWordPatterns[normalized];
      this.config.wakeWord = normalized;
      console.log(`[WakeWordDetector] Wake word set to: ${wakeWord}`);
    } else {
      console.warn(`[WakeWordDetector] Unsupported wake word: ${wakeWord}, using default 'dash'`);
      this.currentPattern = this.wakeWordPatterns['dash'];
      this.config.wakeWord = 'dash';
    }
  }

  /**
   * Add support for multiple wake words simultaneously
   */
  enableAllWakeWords(): void {
    // Monitor for all supported wake words by checking all patterns
    console.log('[WakeWordDetector] All wake words enabled: "Dash", "Hey Dash", "Dash listen", "Wake up Dash"');
  }
}