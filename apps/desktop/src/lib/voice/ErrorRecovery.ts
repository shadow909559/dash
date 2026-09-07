/**
 * ErrorRecovery - Handles error detection and recovery for voice system
 * 
 * Features:
 * - Microphone failure detection
 * - Automatic reconnection
 * - Alternative device suggestion
 * - Error logging
 * - Graceful degradation
 * - User notification
 */

import { EventEmitter } from '../EventEmitter';

export interface ErrorRecoveryConfig {
  maxRetryAttempts: number;
  retryDelay: number;
  enableAutoRecovery: boolean;
  enableNotifications: boolean;
  logErrors: boolean;
}

export interface ErrorInfo {
  type: 'microphone' | 'recognition' | 'synthesis' | 'network' | 'general';
  message: string;
  timestamp: number;
  resolved: boolean;
  retryCount: number;
}

export class ErrorRecovery extends EventEmitter {
  private config: ErrorRecoveryConfig;
  private errorHistory: ErrorInfo[] = [];
  private isInitialized: boolean = false;
  private recoveryAttempts: Map<string, number> = new Map();
  private monitoringInterval: number | null = null;

  constructor(config: any) {
    super();
    this.config = {
      maxRetryAttempts: config.maxRetryAttempts || 3,
      retryDelay: config.retryDelay || 2000,
      enableAutoRecovery: config.enableAutoRecovery !== false,
      enableNotifications: config.enableNotifications !== false,
      logErrors: config.logErrors !== false,
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[ErrorRecovery] Initializing...');

      // Load error history
      await this.loadErrorHistory();

      this.isInitialized = true;
      console.log('[ErrorRecovery] Initialized successfully');

    } catch (error) {
      console.error('[ErrorRecovery] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async startMonitoring(): Promise<void> {
    if (!this.isInitialized) {
      throw new Error('ErrorRecovery not initialized');
    }

    try {
      // Monitor system health every 10 seconds
      this.monitoringInterval = window.setInterval(() => {
        this.checkSystemHealth();
      }, 10000);

      this.emit('monitoringStarted');
      console.log('[ErrorRecovery] Started monitoring');

    } catch (error) {
      console.error('[ErrorRecovery] Failed to start monitoring:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async stopMonitoring(): Promise<void> {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }

    this.emit('monitoringStopped');
    console.log('[ErrorRecovery] Stopped monitoring');
  }

  async handleError(error: Error, type: ErrorInfo['type']): Promise<void> {
    console.error('[ErrorRecovery] Handling error:', error);

    const errorInfo: ErrorInfo = {
      type,
      message: error.message,
      timestamp: Date.now(),
      resolved: false,
      retryCount: 0,
    };

    this.errorHistory.push(errorInfo);
    this.emit('errorOccurred', errorInfo);

    if (this.config.logErrors) {
      await this.logError(errorInfo);
    }

    if (this.config.enableAutoRecovery) {
      await this.attemptRecovery(errorInfo);
    }
  }

  private async attemptRecovery(errorInfo: ErrorInfo): Promise<void> {
    const errorKey = `${errorInfo.type}_${errorInfo.message}`;
    const currentAttempts = this.recoveryAttempts.get(errorKey) || 0;

    if (currentAttempts >= this.config.maxRetryAttempts) {
      console.error('[ErrorRecovery] Max retry attempts reached for:', errorKey);
      this.emit('recoveryFailed', errorInfo);
      return;
    }

    try {
      this.recoveryAttempts.set(errorKey, currentAttempts + 1);
      errorInfo.retryCount = currentAttempts + 1;

      console.log(`[ErrorRecovery] Attempting recovery ${currentAttempts + 1}/${this.config.maxRetryAttempts}`);

      await this.delay(this.config.retryDelay);

      switch (errorInfo.type) {
        case 'microphone':
          await this.recoverMicrophone(errorInfo);
          break;
        case 'recognition':
          await this.recoverRecognition(errorInfo);
          break;
        case 'synthesis':
          await this.recoverSynthesis(errorInfo);
          break;
        case 'network':
          await this.recoverNetwork(errorInfo);
          break;
        default:
          await this.recoverGeneral(errorInfo);
      }

      errorInfo.resolved = true;
      this.recoveryAttempts.delete(errorKey);
      this.emit('recoverySuccess', errorInfo);
      console.log('[ErrorRecovery] Recovery successful');

    } catch (recoveryError) {
      console.error('[ErrorRecovery] Recovery failed:', recoveryError);
      this.emit('recoveryFailed', errorInfo);
    }
  }

  private async recoverMicrophone(errorInfo: ErrorInfo): Promise<void> {
    console.log('[ErrorRecovery] Attempting microphone recovery');

    // Try to reinitialize microphone
    this.emit('microphoneRecoveryAttempt');

    // Suggest alternative device
    if (this.config.enableNotifications) {
      this.emit('suggestAlternativeDevice', {
        type: 'microphone',
        message: 'Microphone failed. Please check your microphone or try a different device.',
      });
    }
  }

  private async recoverRecognition(errorInfo: ErrorInfo): Promise<void> {
    console.log('[ErrorRecovery] Attempting speech recognition recovery');

    // Try to reinitialize speech recognition
    this.emit('recognitionRecoveryAttempt');

    // Suggest browser check
    if (this.config.enableNotifications) {
      this.emit('notification', {
        type: 'recognition',
        message: 'Speech recognition failed. Please check your browser permissions.',
      });
    }
  }

  private async recoverSynthesis(errorInfo: ErrorInfo): Promise<void> {
    console.log('[ErrorRecovery] Attempting speech synthesis recovery');

    // Try to reinitialize speech synthesis
    this.emit('synthesisRecoveryAttempt');

    // Suggest alternative output
    if (this.config.enableNotifications) {
      this.emit('notification', {
        type: 'synthesis',
        message: 'Speech synthesis failed. Text responses will be shown instead.',
      });
    }
  }

  private async recoverNetwork(errorInfo: ErrorInfo): Promise<void> {
    console.log('[ErrorRecovery] Attempting network recovery');

    // Check network status
    if (!navigator.onLine) {
      this.emit('notification', {
        type: 'network',
        message: 'You appear to be offline. Please check your internet connection.',
      });
    }
  }

  private async recoverGeneral(errorInfo: ErrorInfo): Promise<void> {
    console.log('[ErrorRecovery] Attempting general recovery');

    // Try to reinitialize affected component
    this.emit('generalRecoveryAttempt');
  }

  private checkSystemHealth(): void {
    // Check microphone access
    this.checkMicrophoneHealth();

    // Check speech recognition support
    this.checkRecognitionHealth();

    // Check speech synthesis support
    this.checkSynthesisHealth();

    // Check network status
    this.checkNetworkHealth();
  }

  private checkMicrophoneHealth(): void {
    // This would check if microphone is still accessible
    // For now, it's a placeholder
  }

  private checkRecognitionHealth(): void {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      this.emit('healthIssue', {
        type: 'recognition',
        message: 'Speech recognition not supported in this browser',
      });
    }
  }

  private checkSynthesisHealth(): void {
    if (!window.speechSynthesis) {
      this.emit('healthIssue', {
        type: 'synthesis',
        message: 'Speech synthesis not supported in this browser',
      });
    }
  }

  private checkNetworkHealth(): void {
    if (!navigator.onLine) {
      this.emit('healthIssue', {
        type: 'network',
        message: 'Network connection lost',
      });
    }
  }

  getErrorHistory(): ErrorInfo[] {
    return [...this.errorHistory];
  }

  getRecentErrors(count: number = 10): ErrorInfo[] {
    return this.errorHistory.slice(-count);
  }

  getUnresolvedErrors(): ErrorInfo[] {
    return this.errorHistory.filter(error => !error.resolved);
  }

  clearErrorHistory(): void {
    this.errorHistory = [];
    this.recoveryAttempts.clear();
    this.emit('errorHistoryCleared');
  }

  private async logError(errorInfo: ErrorInfo): Promise<void> {
    try {
      const logs = JSON.parse(localStorage.getItem('dash_error_logs') || '[]');
      logs.push(errorInfo);
      
      // Keep only last 100 errors
      if (logs.length > 100) {
        logs.shift();
      }
      
      localStorage.setItem('dash_error_logs', JSON.stringify(logs));
    } catch (error) {
      console.error('[ErrorRecovery] Failed to log error:', error);
    }
  }

  private async loadErrorHistory(): Promise<void> {
    try {
      const stored = localStorage.getItem('dash_error_logs');
      if (stored) {
        this.errorHistory = JSON.parse(stored);
        console.log(`[ErrorRecovery] Loaded ${this.errorHistory.length} error records`);
      }
    } catch (error) {
      console.error('[ErrorRecovery] Failed to load error history:', error);
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  updateConfig(config: Partial<ErrorRecoveryConfig>): void {
    this.config = { ...this.config, ...config };
  }

  async shutdown(): Promise<void> {
    await this.stopMonitoring();
    this.isInitialized = false;
    console.log('[ErrorRecovery] Shutdown complete');
  }
}
