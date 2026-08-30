/**
 * SpeechRecognition - Converts speech to text using Web Speech API
 * 
 * Features:
 * - Real-time speech recognition
 * - Multiple language support
 * - Continuous recognition
 * - Interim results
 * - Error recovery
 */

import { EventEmitter } from '../EventEmitter';

export interface SpeechRecognitionConfig {
  language: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
}

export class SpeechRecognition extends EventEmitter {
  private config: SpeechRecognitionConfig;
  private recognition: any = null;
  private isInitialized: boolean = false;
  private isRunning: boolean = false;
  private finalTranscript: string = '';
  private interimTranscript: string = '';

  constructor(config: any) {
    super();
    this.config = {
      language: config.language || 'en-US',
      continuous: true,
      interimResults: true,
      maxAlternatives: 1,
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[SpeechRecognition] Initializing...');

      // Check for browser support
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      
      if (!SpeechRecognition) {
        throw new Error('Speech recognition not supported in this browser');
      }

      this.recognition = new SpeechRecognition();
      this.setupRecognition();

      this.isInitialized = true;
      console.log('[SpeechRecognition] Initialized successfully');

    } catch (error) {
      console.error('[SpeechRecognition] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async start(): Promise<void> {
    if (!this.isInitialized) {
      throw new Error('SpeechRecognition not initialized');
    }

    if (this.isRunning) {
      console.warn('[SpeechRecognition] Already running');
      return;
    }

    try {
      this.finalTranscript = '';
      this.interimTranscript = '';
      this.recognition.start();
      this.isRunning = true;
      this.emit('started');
      console.log('[SpeechRecognition] Started');

    } catch (error) {
      console.error('[SpeechRecognition] Failed to start:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async stop(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    try {
      this.recognition.stop();
      this.isRunning = false;
      this.emit('stopped');
      console.log('[SpeechRecognition] Stopped');

    } catch (error) {
      console.error('[SpeechRecognition] Failed to stop:', error);
      this.emit('error', error);
    }
  }

  getFinalTranscript(): string {
    return this.finalTranscript;
  }

  getInterimTranscript(): string {
    return this.interimTranscript;
  }

  getFullTranscript(): string {
    return this.finalTranscript + ' ' + this.interimTranscript;
  }

  setLanguage(language: string): void {
    this.config.language = language;
    if (this.recognition) {
      this.recognition.lang = language;
    }
  }

  updateConfig(config: Partial<SpeechRecognitionConfig>): void {
    this.config = { ...this.config, ...config };
    if (this.recognition) {
      this.recognition.continuous = this.config.continuous;
      this.recognition.interimResults = this.config.interimResults;
    }
  }

  async shutdown(): Promise<void> {
    await this.stop();
    this.recognition = null;
    this.isInitialized = false;
    console.log('[SpeechRecognition] Shutdown complete');
  }

  private setupRecognition(): void {
    this.recognition.lang = this.config.language;
    this.recognition.continuous = this.config.continuous;
    this.recognition.interimResults = this.config.interimResults;
    this.recognition.maxAlternatives = this.config.maxAlternatives;

    this.recognition.onstart = () => {
      console.log('[SpeechRecognition] Recognition started');
    };

    this.recognition.onend = () => {
      console.log('[SpeechRecognition] Recognition ended');
      
      // Auto-restart if still supposed to be running
      if (this.isRunning) {
        try {
          this.recognition.start();
        } catch (error) {
          console.error('[SpeechRecognition] Failed to restart:', error);
          this.isRunning = false;
          this.emit('error', error);
        }
      }
    };

    this.recognition.onresult = (event: any) => {
      this.handleResult(event);
    };

    this.recognition.onerror = (event: any) => {
      this.handleError(event);
    };
  }

  private handleResult(event: any): void {
    let interimTranscript = '';
    let finalTranscript = '';

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      
      if (event.results[i].isFinal) {
        finalTranscript += transcript;
      } else {
        interimTranscript += transcript;
      }
    }

    this.finalTranscript = finalTranscript;
    this.interimTranscript = interimTranscript;

    this.emit('interimResult', { 
      final: finalTranscript, 
      interim: interimTranscript 
    });

    // Emit result when we have a complete sentence
    if (finalTranscript.trim()) {
      this.emit('result', finalTranscript.trim());
      console.log('[SpeechRecognition] Final result:', finalTranscript.trim());
    }
  }

  private handleError(event: any): void {
    console.error('[SpeechRecognition] Error:', event.error);

    switch (event.error) {
      case 'no-speech':
        console.log('[SpeechRecognition] No speech detected');
        break;
      case 'audio-capture':
        console.error('[SpeechRecognition] Audio capture failed');
        this.emit('error', new Error('Audio capture failed'));
        break;
      case 'not-allowed':
        console.error('[SpeechRecognition] Permission denied');
        this.emit('error', new Error('Microphone permission denied'));
        break;
      case 'network':
        console.error('[SpeechRecognition] Network error');
        this.emit('error', new Error('Network error'));
        break;
      default:
        this.emit('error', new Error(event.error));
    }
  }

  /**
   * Detect language from text (simplified version)
   */
  static detectLanguage(text: string): string {
    // Simple language detection based on character patterns
    const hindiPattern = /[\u0900-\u097F]/;
    const marathiPattern = /[\u0900-\u097F]/; // Similar to Hindi
    
    if (hindiPattern.test(text)) {
      return 'hi-IN';
    }
    
    // Default to English
    return 'en-US';
  }
}
