/**
 * ConversationEngine - Handles natural conversation flow and context
 * 
 * Features:
 * - Context understanding
 * - Follow-up question handling
 * - Pronoun resolution
 * - Reference resolution
 * - Natural conversation flow
 * - Memory integration
 */

import { EventEmitter } from '../EventEmitter';

export interface ConversationContext {
  currentTopic: string | null;
  previousTopics: string[];
  entities: Map<string, any>;
  references: Map<string, any>;
  lastUserIntent: string | null;
  lastSystemResponse: string | null;
  conversationHistory: Array<{ role: 'user' | 'assistant', content: string, timestamp: number }>;
}

export interface ConversationConfig {
  maxHistoryLength: number;
  contextWindowSize: number;
  enableProactive: boolean;
  language: string;
}

export class ConversationEngine extends EventEmitter {
  private config: ConversationConfig;
  private context: ConversationContext;
  private isInitialized: boolean = false;
  private memory: any = null;
  private tts: any = null;
  private interruptController: any = null;
  private isSpeaking: boolean = false;

  constructor(config: any) {
    super();
    this.config = {
      maxHistoryLength: 20,
      contextWindowSize: 5,
      enableProactive: true,
      language: config.language || 'en-US',
    };

    this.context = {
      currentTopic: null,
      previousTopics: [],
      entities: new Map(),
      references: new Map(),
      lastUserIntent: null,
      lastSystemResponse: null,
      conversationHistory: [],
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[ConversationEngine] Initializing...');

      // Initialize memory integration
      const { ConversationMemory } = await import('./ConversationMemory');
      this.memory = new ConversationMemory({});
      await this.memory.initialize();

      // Initialize TTS
      const { DASHSpeechSynthesis } = await import('./SpeechSynthesis');
      this.tts = new DASHSpeechSynthesis({});
      await this.tts.initialize();

      // Initialize interruption controller for voice interruption handling
      const { InterruptController } = await import('./InterruptController');
      this.interruptController = new InterruptController({});
      await this.interruptController.initialize();
      
      // Handle user interruptions - immediately stop TTS when user speaks
      this.interruptController.on('interrupt', async () => {
        if (this.isSpeaking && this.tts) {
          console.log('[ConversationEngine] User interrupted speech - stopping TTS immediately');
          await this.tts.stop();
          this.isSpeaking = false;
          this.emit('interrupted');
          // Resume listening naturally without robotic pauses
          this.emit('resumeListening');
        }
      });

      // Start monitoring for interruptions
      await this.interruptController.startMonitoring();

      // Track TTS speaking state
      this.tts.on('speaking', (speaking: boolean) => {
        this.isSpeaking = speaking;
      });

      this.isInitialized = true;
      console.log('[ConversationEngine] Initialized successfully with interruption handling');

    } catch (error) {
      console.error('[ConversationEngine] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async processUserInput(input: string): Promise<string> {
    if (!this.isInitialized) {
      throw new Error('ConversationEngine not initialized');
    }

    try {
      console.log('[ConversationEngine] Processing input:', input);

      // Add to conversation history
      this.addToHistory('user', input);

      // Analyze input
      const analysis = this.analyzeInput(input);

      // Update context
      this.updateContext(analysis);

      // Resolve references
      const resolvedInput = this.resolveReferences(input);

      // Generate response
      const response = await this.generateResponse(resolvedInput, analysis);

      // Add to conversation history
      this.addToHistory('assistant', response);

      // Update context with response
      this.context.lastSystemResponse = response;

      // Store in memory
      await this.storeInMemory(input, response);

      this.emit('responseGenerated', response);
      return response;

    } catch (error) {
      console.error('[ConversationEngine] Failed to process input:', error);
      this.emit('error', error);
      throw error;
    }
  }

  private analyzeInput(input: string): any {
    const analysis = {
      intent: this.detectIntent(input),
      entities: this.extractEntities(input),
      sentiment: this.detectSentiment(input),
      language: this.detectLanguage(input),
      isFollowUp: this.isFollowUpQuestion(input),
      hasReferences: this.hasReferences(input),
    };

    console.log('[ConversationEngine] Input analysis:', analysis);
    return analysis;
  }

  private detectIntent(input: string): string {
    const lowerInput = input.toLowerCase();

    // Desktop commands
    if (lowerInput.includes('open') || lowerInput.includes('launch') || lowerInput.includes('start')) {
      return 'open_application';
    }
    if (lowerInput.includes('close') || lowerInput.includes('quit') || lowerInput.includes('exit')) {
      return 'close_application';
    }
    if (lowerInput.includes('search') || lowerInput.includes('find') || lowerInput.includes('look for')) {
      return 'search';
    }
    if (lowerInput.includes('create') || lowerInput.includes('make') || lowerInput.includes('new')) {
      return 'create';
    }
    if (lowerInput.includes('delete') || lowerInput.includes('remove')) {
      return 'delete';
    }

    // Information queries
    if (lowerInput.includes('what') || lowerInput.includes('how') || lowerInput.includes('why') || lowerInput.includes('when')) {
      return 'information_query';
    }
    if (lowerInput.includes('can you') || lowerInput.includes('could you') || lowerInput.includes('would you')) {
      return 'capability_query';
    }

    // Greetings
    if (lowerInput.includes('hello') || lowerInput.includes('hi') || lowerInput.includes('hey')) {
      return 'greeting';
    }
    if (lowerInput.includes('goodbye') || lowerInput.includes('bye') || lowerInput.includes('see you')) {
      return 'farewell';
    }

    // Default
    return 'general_query';
  }

  private extractEntities(input: string): Map<string, any> {
    const entities = new Map();
    const lowerInput = input.toLowerCase();

    // Application names
    const applications = ['chrome', 'firefox', 'vs code', 'visual studio', 'spotify', 'notepad', 'terminal', 'cmd'];
    applications.forEach(app => {
      if (lowerInput.includes(app)) {
        entities.set('application', app);
      }
    });

    // File types
    const fileTypes = ['file', 'folder', 'document', 'image', 'video', 'audio'];
    fileTypes.forEach(type => {
      if (lowerInput.includes(type)) {
        entities.set('file_type', type);
      }
    });

    // Websites
    if (lowerInput.includes('http://') || lowerInput.includes('https://') || lowerInput.includes('.com')) {
      const urlMatch = input.match(/https?:\/\/[^\s]+/);
      if (urlMatch) {
        entities.set('url', urlMatch[0]);
      }
    }

    return entities;
  }

  private detectSentiment(input: string): 'positive' | 'negative' | 'neutral' {
    const positiveWords = ['good', 'great', 'awesome', 'thanks', 'thank you', 'excellent', 'perfect'];
    const negativeWords = ['bad', 'terrible', 'awful', 'hate', 'worst', 'error', 'wrong', 'fail'];
    
    const lowerInput = input.toLowerCase();
    const positiveCount = positiveWords.filter(word => lowerInput.includes(word)).length;
    const negativeCount = negativeWords.filter(word => lowerInput.includes(word)).length;

    if (positiveCount > negativeCount) return 'positive';
    if (negativeCount > positiveCount) return 'negative';
    return 'neutral';
  }

  private detectLanguage(input: string): string {
    // Simple language detection
    const hindiPattern = /[\u0900-\u097F]/;
    if (hindiPattern.test(input)) {
      return 'hi-IN';
    }
    return 'en-US';
  }

  private isFollowUpQuestion(input: string): boolean {
    const followUpIndicators = ['it', 'that', 'this', 'the', 'they', 'them', 'he', 'she', 'again'];
    const lowerInput = input.toLowerCase();
    return followUpIndicators.some(indicator => lowerInput.startsWith(indicator + ' '));
  }

  private hasReferences(input: string): boolean {
    const referenceWords = ['it', 'that', 'this', 'the', 'they', 'them', 'he', 'she', 'there'];
    const lowerInput = input.toLowerCase();
    return referenceWords.some(word => lowerInput.includes(' ' + word + ' '));
  }

  private resolveReferences(input: string): string {
    if (!this.hasReferences(input)) {
      return input;
    }

    let resolvedInput = input;
    const lowerInput = input.toLowerCase();

    // Resolve "it"
    if (lowerInput.includes(' it ')) {
      const lastEntity = this.context.entities.get('last_entity');
      if (lastEntity) {
        resolvedInput = resolvedInput.replace(/\bit\b/gi, lastEntity);
      }
    }

    // Resolve "that"
    if (lowerInput.includes(' that ')) {
      const lastTopic = this.context.currentTopic;
      if (lastTopic) {
        resolvedInput = resolvedInput.replace(/\bthat\b/gi, lastTopic);
      }
    }

    console.log('[ConversationEngine] Resolved input:', resolvedInput);
    return resolvedInput;
  }

  private updateContext(analysis: any): void {
    // Update topic
    if (analysis.entities.has('application')) {
      this.context.currentTopic = analysis.entities.get('application');
      this.context.entities.set('last_entity', analysis.entities.get('application'));
    }

    // Update intent
    this.context.lastUserIntent = analysis.intent;

    // Update language
    if (analysis.language !== this.config.language) {
      this.config.language = analysis.language;
    }
  }

  private async generateResponse(input: string, analysis: any): Promise<string> {
    // This would connect to the AI backend for actual response generation
    // For now, we'll use a simple rule-based system
    
    switch (analysis.intent) {
      case 'greeting':
        return this.getGreetingResponse();
      
      case 'farewell':
        return 'Goodbye. I\'ll be here when you need me.';
      
      case 'open_application':
        const app = analysis.entities.get('application');
        if (app) {
          return `Opening ${app}.`;
        }
        return 'What would you like me to open?';
      
      case 'close_application':
        if (this.context.currentTopic) {
          return `Closing ${this.context.currentTopic}.`;
        }
        return 'What would you like me to close?';
      
      case 'search':
        return 'What would you like me to search for?';
      
      case 'information_query':
        return this.handleInformationQuery(input);
      
      default:
        return this.handleGeneralQuery(input);
    }
  }

  private getGreetingResponse(): string {
    const greetings = [
      'Hello. How can I help you today?',
      'Hi there. What can I do for you?',
      'Hello. I\'m ready to assist.',
    ];
    return greetings[Math.floor(Math.random() * greetings.length)];
  }

  private handleInformationQuery(input: string): string {
    // This would connect to the AI backend
    return 'I understand you\'re asking about that. Let me help you.';
  }

  private handleGeneralQuery(input: string): string {
    // This would connect to the AI backend
    return 'I understand. Let me process that for you.';
  }

  private addToHistory(role: 'user' | 'assistant', content: string): void {
    this.context.conversationHistory.push({
      role,
      content,
      timestamp: Date.now(),
    });

    // Trim history if too long
    if (this.context.conversationHistory.length > this.config.maxHistoryLength) {
      this.context.conversationHistory.shift();
    }
  }

  private async initializeMemory(): Promise<any> {
    // Initialize conversation memory integration
    // This would connect to the memory system
    return null;
  }

  private async storeInMemory(userInput: string, response: string): Promise<void> {
    // Store conversation in memory
    if (this.memory) {
      // Store the conversation
    }
  }

  getContext(): ConversationContext {
    return {
      ...this.context,
      entities: new Map(this.context.entities),
      references: new Map(this.context.references),
    };
  }

  clearContext(): void {
    this.context = {
      currentTopic: null,
      previousTopics: [],
      entities: new Map(),
      references: new Map(),
      lastUserIntent: null,
      lastSystemResponse: null,
      conversationHistory: [],
    };
    this.emit('contextCleared');
  }

  updateConfig(config: Partial<ConversationConfig>): void {
    this.config = { ...this.config, ...config };
  }

  async shutdown(): Promise<void> {
    this.clearContext();
    this.isInitialized = false;
    console.log('[ConversationEngine] Shutdown complete');
  }
}