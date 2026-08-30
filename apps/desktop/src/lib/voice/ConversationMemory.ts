/**
 * ConversationMemory - Manages conversation and session memory
 * 
 * Features:
 * - Conversation memory
 * - Session memory
 * - Long-term memory
 * - Project memory
 * - Preference memory
 * - Context retention
 * - Memory retrieval
 */

import { EventEmitter } from '../EventEmitter';

export interface MemoryEntry {
  id: string;
  category: 'fact' | 'preference' | 'project' | 'code' | 'conversation' | 'idea' | 'file' | 'task' | 'goal';
  content: any;
  timestamp: number;
  importance: number;
  embedding: number[];
  summary: string;
  source: string;
  confidence: number;
  tags: string[];
}

export interface MemoryConfig {
  maxConversationMemory: number;
  maxSessionMemory: number;
  maxLongTermMemory: number;
  retentionDays: number;
  enableEmbeddings: boolean;
}

export class ConversationMemory extends EventEmitter {
  private config: MemoryConfig;
  private conversationMemory: MemoryEntry[] = [];
  private sessionMemory: MemoryEntry[] = [];
  private longTermMemory: MemoryEntry[] = [];
  private projectMemory: Map<string, MemoryEntry[]> = new Map();
  private preferenceMemory: Map<string, any> = new Map();
  private isInitialized: boolean = false;

  constructor(config: any) {
    super();
    this.config = {
      maxConversationMemory: config.maxConversationMemory || 50,
      maxSessionMemory: config.maxSessionMemory || 100,
      maxLongTermMemory: config.maxLongTermMemory || 1000,
      retentionDays: config.retentionDays || 30,
      enableEmbeddings: config.enableEmbeddings || false,
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[ConversationMemory] Initializing...');
      await this.loadFromStorage();
      this.cleanupOldMemory();
      this.isInitialized = true;
      console.log('[ConversationMemory] Initialized successfully');
    } catch (error) {
      console.error('[ConversationMemory] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async storeConversation(role: 'user' | 'assistant', content: string, source: string = 'voice', metadata?: any): Promise<void> {
    const entry: MemoryEntry = {
      id: this.generateId(),
      category: 'conversation',
      content: { role, content, metadata },
      timestamp: Date.now(),
      importance: this.calculateImportance(content),
      embedding: await this.generateEmbedding(content),
      summary: this.generateSummary(content),
      source: source,
      confidence: 0.95,
      tags: this.extractTags(content),
    };

    this.conversationMemory.push(entry);
    await this.saveToStorage();
    if (this.conversationMemory.length > this.config.maxConversationMemory) {
      this.conversationMemory.shift();
    }
    await this.storeSession('conversation', entry);
    this.emit('conversationStored', entry);
  }

  private getAllMemory(): MemoryEntry[] {
    return [
      ...this.conversationMemory,
      ...this.longTermMemory,
      ...Array.from(this.projectMemory.values()).flat(),
      ...this.sessionMemory,
    ];
  }

  /**
   * Semantic search for memories - finds relevant memories based on query similarity
   */
  async semanticSearch(query: string, category?: MemoryEntry['category'], threshold: number = 0.5, limit: number = 10): Promise<MemoryEntry[]> {
    const queryEmbedding = await this.generateEmbedding(query);
    const allMemories = category
      ? this.getAllMemory().filter((entry) => entry.category === category)
      : this.getAllMemory();

    const scored = allMemories
      .map((memory) => ({
        memory,
        score: this.cosineSimilarity(queryEmbedding, memory.embedding || []),
      }))
      .filter((item) => item.score >= threshold)
      .sort((a, b) => b.score - a.score);

    return scored.slice(0, limit).map((item) => item.memory);
  }

  /**
   * Recollection methods for natural memory queries
   */
  async recall(query: string): Promise<MemoryEntry[]> {
    const lowerQuery = query.toLowerCase();
    const patterns: Record<string, () => Promise<MemoryEntry[]>> = {
      'continue yesterday': () => this.recallYesterday(),
      'remember what we built': () => this.recallProjects(),
      'find that code': () => this.recallCode(),
      'what were we discussing': () => this.recallRecentConversation(),
    };

    for (const [pattern, handler] of Object.entries(patterns)) {
      if (lowerQuery.includes(pattern)) {
        return handler();
      }
    }

    return this.semanticSearch(query, undefined, 0.1, 10);
  }

  private async recallYesterday(): Promise<MemoryEntry[]> {
    const yesterday = Date.now() - 24 * 60 * 60 * 1000;
    return this.getAllMemory().filter((entry) => entry.timestamp > yesterday);
  }

  private async recallProjects(): Promise<MemoryEntry[]> {
    return this.getAllMemory().filter((entry) => entry.category === 'project');
  }

  private async recallCode(): Promise<MemoryEntry[]> {
    return this.getAllMemory().filter((entry) => entry.category === 'code');
  }

  private async recallRecentConversation(): Promise<MemoryEntry[]> {
    const recent = Date.now() - 60 * 60 * 1000;
    return this.getAllMemory()
      .filter((entry) => entry.category === 'conversation' && entry.timestamp > recent)
      .slice(-20);
  }

  private cosineSimilarity(a: number[], b: number[]): number {
    if (a.length !== b.length || a.length === 0) return 0;
    const dotProduct = a.reduce((sum, val, i) => sum + val * b[i], 0);
    const magnitudeA = Math.sqrt(a.reduce((sum, val) => sum + val * val, 0));
    const magnitudeB = Math.sqrt(b.reduce((sum, val) => sum + val * val, 0));
    return dotProduct / (magnitudeA * magnitudeB);
  }

  async storeSession(key: string, value: any, source: string = 'session'): Promise<void> {
    const contentStr = JSON.stringify({ key, value });
    const entry: MemoryEntry = {
      id: this.generateId(),
      category: 'task',
      content: { key, value },
      timestamp: Date.now(),
      importance: 0.5,
      embedding: await this.generateEmbedding(contentStr),
      summary: this.generateSummary(contentStr),
      source: source,
      confidence: 0.9,
      tags: [key],
    };

    this.sessionMemory.push(entry);
    if (this.sessionMemory.length > this.config.maxSessionMemory) {
      this.sessionMemory.shift();
    }
    this.emit('sessionStored', entry);
  }

  async storeLongTerm(key: string, value: any, category: MemoryEntry['category'], importance: number = 0.7, source: string = 'user'): Promise<void> {
    const contentStr = JSON.stringify({ key, value });
    const entry: MemoryEntry = {
      id: this.generateId(),
      category: category,
      content: { key, value },
      timestamp: Date.now(),
      importance,
      embedding: await this.generateEmbedding(contentStr),
      summary: this.generateSummary(contentStr),
      source: source,
      confidence: 0.95,
      tags: [key],
    };

    this.longTermMemory.push(entry);
    if (this.longTermMemory.length > this.config.maxLongTermMemory) {
      this.longTermMemory.sort((a, b) => a.importance - b.importance);
      this.longTermMemory.shift();
    }
    await this.saveToStorage();
    this.emit('longTermStored', entry);
  }

  async storeProject(projectId: string, key: string, value: any, source: string = 'project'): Promise<void> {
    const contentStr = JSON.stringify({ projectId, key, value });
    const entry: MemoryEntry = {
      id: this.generateId(),
      category: 'project',
      content: { projectId, key, value },
      timestamp: Date.now(),
      importance: 0.8,
      embedding: await this.generateEmbedding(contentStr),
      summary: this.generateSummary(contentStr),
      source: source,
      confidence: 0.95,
      tags: [projectId, key],
    };

    if (!this.projectMemory.has(projectId)) {
      this.projectMemory.set(projectId, []);
    }
    this.projectMemory.get(projectId)!.push(entry);
    await this.saveToStorage();
    this.emit('projectStored', entry);
  }

  async storePreference(key: string, value: any): Promise<void> {
    this.preferenceMemory.set(key, value);
    this.emit('preferenceStored', { key, value });
  }

  getConversationHistory(limit?: number): MemoryEntry[] {
    const history = [...this.conversationMemory];
    return limit ? history.slice(-limit) : history;
  }

  getSessionMemory(key?: string): MemoryEntry[] {
    return key
      ? this.sessionMemory.filter((entry) => entry.content.key === key)
      : [...this.sessionMemory];
  }

  getLongTermMemory(key?: string): MemoryEntry[] {
    return key
      ? this.longTermMemory.filter((entry) => entry.content.key === key)
      : [...this.longTermMemory];
  }

  getProjectMemory(projectId: string, key?: string): MemoryEntry[] {
    const projectEntries = this.projectMemory.get(projectId) || [];
    return key ? projectEntries.filter((entry) => entry.content.key === key) : projectEntries;
  }

  getPreference(key: string): any {
    return this.preferenceMemory.get(key);
  }

  getAllPreferences(): Map<string, any> {
    return new Map(this.preferenceMemory);
  }

  async searchMemory(query: string, category?: MemoryEntry['category']): Promise<MemoryEntry[]> {
    return this.semanticSearch(query, category, 0.1, 10);
  }

  async clearConversationMemory(): Promise<void> {
    this.conversationMemory = [];
    this.emit('conversationCleared');
  }

  async clearSessionMemory(): Promise<void> {
    this.sessionMemory = [];
    this.emit('sessionCleared');
  }

  async clearProjectMemory(projectId: string): Promise<void> {
    this.projectMemory.delete(projectId);
    this.emit('projectCleared', projectId);
  }

  updateConfig(config: Partial<MemoryConfig>): void {
    this.config = { ...this.config, ...config };
  }

  async shutdown(): Promise<void> {
    await this.saveToStorage();
    this.isInitialized = false;
    console.log('[ConversationMemory] Shutdown complete');
  }

  private async generateEmbedding(text: string): Promise<number[]> {
    const embedding = new Array(128).fill(0);
    const textLower = text.toLowerCase();
    for (let i = 0; i < textLower.length; i++) {
      const charCode = textLower.charCodeAt(i);
      embedding[i % 128] += charCode / 255;
    }
    const magnitude = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    return embedding.map((val) => val / magnitude);
  }

  private generateSummary(text: string): string {
    if (text.length <= 100) return text;
    return text.substring(0, 97) + '...';
  }

  private calculateImportance(content: string): number {
    let importance = 0.5;
    const importantWords = ['important', 'remember', 'save', 'critical', 'urgent'];
    const lowerContent = content.toLowerCase();
    importantWords.forEach((word) => {
      if (lowerContent.includes(word)) importance += 0.1;
    });
    return Math.min(1, importance);
  }

  private extractTags(content: string): string[] {
    const tags: string[] = [];
    const lowerContent = content.toLowerCase();
    const topics = ['work', 'personal', 'project', 'meeting', 'deadline', 'reminder'];
    topics.forEach((topic) => {
      if (lowerContent.includes(topic)) tags.push(topic);
    });
    return tags;
  }

  private generateId(): string {
    return `mem_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private async loadFromStorage(): Promise<void> {
    try {
      const stored = localStorage.getItem('dash_memory');
      if (stored) {
        const data = JSON.parse(stored);
        this.conversationMemory = data.conversationMemory || [];
        this.sessionMemory = data.sessionMemory || [];
        this.longTermMemory = data.longTermMemory || [];
        this.preferenceMemory = new Map(data.preferenceMemory || []);
      }
    } catch (error) {
      console.error('[ConversationMemory] Failed to load from storage:', error);
    }
  }

  private async saveToStorage(): Promise<void> {
    try {
      const data = {
        conversationMemory: this.conversationMemory,
        sessionMemory: this.sessionMemory,
        longTermMemory: this.longTermMemory,
        preferenceMemory: Array.from(this.preferenceMemory),
      };
      localStorage.setItem('dash_memory', JSON.stringify(data));
    } catch (error) {
      console.error('[ConversationMemory] Failed to save to storage:', error);
    }
  }

  private cleanupOldMemory(): void {
    const cutoffTime = Date.now() - (this.config.retentionDays * 24 * 60 * 60 * 1000);
    this.conversationMemory = this.conversationMemory.filter((entry) => entry.timestamp > cutoffTime);
    this.sessionMemory = this.sessionMemory.filter((entry) => entry.timestamp > cutoffTime);
  }
}
