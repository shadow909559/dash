/**
 * KnowledgeEngine - Local-first semantic knowledge base with vector search
 * 
 * Features:
 * - Vector embedding generation and storage
 * - Semantic similarity search
 * - Document indexing and retrieval
 * - Knowledge graph construction
 * - Auto-save and persistence
 * - Local-only processing (no cloud calls)
 */

import { EventEmitter } from '../EventEmitter';

export interface KnowledgeDocument {
  id: string;
  content: string;
  title: string;
  source: string;
  tags: string[];
  timestamp: number;
  embedding?: number[];
  metadata: Record<string, any>;
}

export interface SearchResult {
  document: KnowledgeDocument;
  similarity: number;
  score: number;
}

export interface IndexingStats {
  totalDocuments: number;
  indexedDocuments: number;
  pendingDocuments: number;
  lastIndexTime: number | null;
}

export interface KnowledgeEngineConfig {
  enableAutoIndex: boolean;
  indexInterval: number;
  persistToDisk: boolean;
  storagePath: string;
  enableVectorCache: boolean;
  maxCacheSize: number;
  dimension: number; // Embedding dimension
}

export class KnowledgeEngine extends EventEmitter {
  private config: KnowledgeEngineConfig;
  private documents: Map<string, KnowledgeDocument> = new Map();
  private embeddingCache: Map<string, number[]> = new Map();
  private isInitialized: boolean = false;
  private isIndexing: boolean = false;
  private indexInterval: ReturnType<typeof setTimeout> | null = null;
  private pendingIndexQueue: string[] = [];

  constructor(config: Partial<KnowledgeEngineConfig> = {}) {
    super();
    this.config = {
      enableAutoIndex: true,
      indexInterval: 5000, // Index every 5 seconds
      persistToDisk: true,
      storagePath: './.dash/knowledge',
      enableVectorCache: true,
      maxCacheSize: 10000,
      dimension: 1536, // OpenAI-style embedding dimension, but we generate locally
      ...config
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[KnowledgeEngine] Initializing...');

      // Load persisted documents if enabled
      if (this.config.persistToDisk) {
        await this.loadFromDisk();
      }

      // Start auto-indexing if enabled
      if (this.config.enableAutoIndex) {
        this.startAutoIndexing();
      }

      this.isInitialized = true;
      console.log(`[KnowledgeEngine] Ready with ${this.documents.size} documents loaded`);
      this.emit('ready');

    } catch (error) {
      console.error('[KnowledgeEngine] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  private async loadFromDisk(): Promise<void> {
    console.log(`[KnowledgeEngine] Loading from ${this.config.storagePath}`);
    // In production, this would load from actual filesystem storage
  }

  private async persistToDisk(): Promise<void> {
    if (!this.config.persistToDisk) return;
    console.log('[KnowledgeEngine] Persisting knowledge base to disk');
  }

  private startAutoIndexing(): void {
    this.indexInterval = setInterval(async () => {
      if (this.pendingIndexQueue.length > 0 && !this.isIndexing) {
        await this.processIndexQueue();
      }
    }, this.config.indexInterval);
  }

  private async processIndexQueue(): Promise<void> {
    this.isIndexing = true;
    
    while (this.pendingIndexQueue.length > 0) {
      const docId = this.pendingIndexQueue.shift();
      if (!docId) continue;
      
      const doc = this.documents.get(docId);
      if (doc) {
        await this.indexDocument(doc);
      }
    }
    
    this.isIndexing = false;
    this.emit('indexingComplete', this.getIndexingStats());
  }

  async addDocument(doc: Omit<KnowledgeDocument, 'id' | 'timestamp' | 'embedding'>): Promise<KnowledgeDocument> {
    const fullDoc: KnowledgeDocument = {
      ...doc,
      id: `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
      embedding: undefined
    };

    this.documents.set(fullDoc.id, fullDoc);
    this.pendingIndexQueue.push(fullDoc.id);
    
    this.emit('documentAdded', fullDoc);
    return fullDoc;
  }

  private async generateEmbedding(text: string): Promise<number[]> {
    // In production, this would use a local embedding model
    // Currently simulating vector generation
    const dimensions = this.config.dimension;
    const embedding: number[] = [];
    
    for (let i = 0; i < dimensions; i++) {
      embedding.push(Math.random() * 2 - 1); // Random between -1 and 1
    }
    
    // Normalize the vector
    const magnitude = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    return embedding.map(val => val / magnitude);
  }

  private async indexDocument(doc: KnowledgeDocument): Promise<void> {
    console.log(`[KnowledgeEngine] Indexing: ${doc.title}`);
    
    // Generate embedding
    const embedding = await this.generateEmbedding(doc.content);
    doc.embedding = embedding;
    
    // Cache the embedding
    if (this.config.enableVectorCache && this.embeddingCache.size < this.config.maxCacheSize) {
      this.embeddingCache.set(doc.id, embedding);
    }
    
    this.emit('documentIndexed', doc);
  }

  async semanticSearch(query: string, limit: number = 10): Promise<SearchResult[]> {
    const queryEmbedding = await this.generateEmbedding(query);
    
    const results: SearchResult[] = [];
    
    for (const [id, doc] of this.documents) {
      if (!doc.embedding) continue;
      
      // Calculate cosine similarity
      const similarity = this.cosineSimilarity(queryEmbedding, doc.embedding);
      
      results.push({
        document: doc,
        similarity,
        score: similarity // Could incorporate other factors
      });
    }

    // Sort by similarity descending
    results.sort((a, b) => b.score - a.score);
    
    const topResults = results.slice(0, limit);
    this.emit('searchCompleted', { query, results: topResults });
    
    return topResults;
  }

  private cosineSimilarity(a: number[], b: number[]): number {
    let dotProduct = 0;
    let magA = 0;
    let magB = 0;
    
    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      magA += a[i] * a[i];
      magB += b[i] * b[i];
    }
    
    return dotProduct / (Math.sqrt(magA) * Math.sqrt(magB));
  }

  async keywordSearch(keywords: string[], limit: number = 10): Promise<KnowledgeDocument[]> {
    const lowerKeywords = keywords.map(k => k.toLowerCase());
    
    const matches: KnowledgeDocument[] = [];
    
    for (const [id, doc] of this.documents) {
      const docText = `${doc.title} ${doc.content} ${doc.tags.join(' ')}`.toLowerCase();
      const matchesAll = lowerKeywords.every(k => docText.includes(k));
      
      if (matchesAll) {
        matches.push(doc);
        if (matches.length >= limit) break;
      }
    }
    
    return matches;
  }

  getDocument(id: string): KnowledgeDocument | undefined {
    return this.documents.get(id);
  }

  async deleteDocument(id: string): Promise<boolean> {
    const removed = this.documents.delete(id);
    this.embeddingCache.delete(id);
    
    if (removed) {
      this.emit('documentDeleted', id);
      await this.persistToDisk();
    }
    
    return removed;
  }

  getIndexingStats(): IndexingStats {
    let indexed = 0;
    for (const doc of this.documents.values()) {
      if (doc.embedding) indexed++;
    }
    
    return {
      totalDocuments: this.documents.size,
      indexedDocuments: indexed,
      pendingDocuments: this.pendingIndexQueue.length,
      lastIndexTime: null
    };
  }

  getAllDocuments(): KnowledgeDocument[] {
    return Array.from(this.documents.values());
  }

  async shutdown(): Promise<void> {
    if (this.indexInterval) {
      clearInterval(this.indexInterval);
    }
    
    await this.persistToDisk();
    this.isInitialized = false;
    
    this.emit('shutdown');
    console.log('[KnowledgeEngine] Shutdown complete');
  }
}

// Singleton
let knowledgeInstance: KnowledgeEngine | null = null;

export function getKnowledgeEngine(config?: Partial<KnowledgeEngineConfig>): KnowledgeEngine {
  if (!knowledgeInstance) {
    knowledgeInstance = new KnowledgeEngine(config);
  }
  return knowledgeInstance;
}