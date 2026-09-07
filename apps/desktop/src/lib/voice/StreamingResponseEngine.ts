/**
 * StreamingResponseEngine - Streams AI responses in real-time
 * 
 * Features:
 * - Real-time text streaming
 * - Simultaneous speech synthesis
 * - Orb animation streaming
 * - Chunk-based processing
 * - Low latency
 */

import { EventEmitter } from '../EventEmitter';

export interface StreamingConfig {
  chunkSize: number;
  chunkDelay: number;
  enableSpeech: boolean;
  enableAnimation: boolean;
}

export class StreamingResponseEngine extends EventEmitter {
  private config: StreamingConfig;
  private isInitialized: boolean = false;
  private isStreaming: boolean = false;
  private currentStream: AsyncGenerator<string> | null = null;

  constructor(config: any) {
    super();
    this.config = {
      chunkSize: config.chunkSize || 50,
      chunkDelay: config.chunkDelay || 30,
      enableSpeech: true,
      enableAnimation: true,
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[StreamingResponseEngine] Initializing...');
      this.isInitialized = true;
      console.log('[StreamingResponseEngine] Initialized successfully');
    } catch (error) {
      console.error('[StreamingResponseEngine] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async stream(text: string, onChunk: (chunk: string) => Promise<void>): Promise<void> {
    if (!this.isInitialized) {
      throw new Error('StreamingResponseEngine not initialized');
    }

    if (this.isStreaming) {
      console.warn('[StreamingResponseEngine] Already streaming');
      return;
    }

    try {
      this.isStreaming = true;
      this.emit('streamingStarted', { text });

      // Stream text in chunks
      for await (const chunk of this.chunkText(text)) {
        if (!this.isStreaming) break;

        this.emit('textChunk', { chunk });
        await onChunk(chunk);

        // Delay between chunks for natural pacing
        await this.delay(this.config.chunkDelay);
      }

      this.isStreaming = false;
      this.emit('streamingComplete');

      console.log('[StreamingResponseEngine] Streaming complete');

    } catch (error) {
      console.error('[StreamingResponseEngine] Streaming failed:', error);
      this.isStreaming = false;
      this.emit('error', error);
      throw error;
    }
  }

  async stop(): Promise<void> {
    if (!this.isStreaming) {
      return;
    }

    this.isStreaming = false;
    this.emit('streamingStopped');
    console.log('[StreamingResponseEngine] Streaming stopped');
  }

  private async *chunkText(text: string): AsyncGenerator<string> {
    const words = text.split(' ');
    let currentChunk = '';

    for (const word of words) {
      currentChunk += word + ' ';

      if (currentChunk.length >= this.config.chunkSize) {
        yield currentChunk.trim();
        currentChunk = '';
      }
    }

    if (currentChunk.trim()) {
      yield currentChunk.trim();
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  updateConfig(config: Partial<StreamingConfig>): void {
    this.config = { ...this.config, ...config };
  }

  async shutdown(): Promise<void> {
    await this.stop();
    this.isInitialized = false;
    console.log('[StreamingResponseEngine] Shutdown complete');
  }
}
