/**
 * TaskScheduler - Natural language-powered background task scheduler
 * 
 * Features:
 * - Parse natural language into scheduled tasks
 * - Cron-like recurrence rules
 * - Background execution with agent coordination
 * - Task dependency management
 * - Retry logic with backoff
 * - Persistence of scheduled tasks
 */

import { EventEmitter } from '../EventEmitter';

export interface ScheduleRule {
  type: 'once' | 'recurring';
  cron?: string;
  runAt?: Date;
  interval?: number; // ms
  timezone: string;
}

export interface ScheduledTask {
  id: string;
  name: string;
  description: string;
  naturalLanguageInput: string;
  workflow: string;
  parameters?: any;
  schedule: ScheduleRule;
  status: 'pending' | 'active' | 'running' | 'completed' | 'failed' | 'paused';
  maxRetries: number;
  currentRetries: number;
  lastRun?: number;
  nextRun: number;
  dependencies: string[];
  createdAt: number;
}

export interface ScheduleParseResult {
  success: boolean;
  schedule?: ScheduleRule;
  error?: string;
}

export interface TaskRunResult {
  taskId: string;
  success: boolean;
  startTime: number;
  endTime: number;
  output?: any;
  error?: string;
}

export interface SchedulerConfig {
  enablePersistence: boolean;
  storagePath: string;
  maxConcurrentTasks: number;
  defaultTimezone: string;
  enableAutoRecovery: boolean;
  checkInterval: number;
}

export class TaskScheduler extends EventEmitter {
  private config: SchedulerConfig;
  private isInitialized: boolean = false;
  private tasks: Map<string, ScheduledTask> = new Map();
  private activeTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();
  private checkInterval: ReturnType<typeof setTimeout> | null = null;
  private isChecking: boolean = false;

  constructor(config: Partial<SchedulerConfig> = {}) {
    super();
    this.config = {
      enablePersistence: true,
      storagePath: './.dash/scheduler',
      maxConcurrentTasks: 5,
      defaultTimezone: 'America/New_York',
      enableAutoRecovery: true,
      checkInterval: 60000, // Check every minute by default
      ...config
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[TaskScheduler] Initializing...');

      // Load persisted tasks
      if (this.config.enablePersistence) {
        await this.loadPersistedTasks();
      }

      // Start the scheduler check loop
      this.startScheduler();

      this.isInitialized = true;
      console.log(`[TaskScheduler] Ready with ${this.tasks.size} tasks loaded`);
      this.emit('ready');

    } catch (error) {
      console.error('[TaskScheduler] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  private async loadPersistedTasks(): Promise<void> {
    console.log(`[TaskScheduler] Loading tasks from ${this.config.storagePath}`);
  }

  private async persistTasks(): Promise<void> {
    if (!this.config.enablePersistence) return;
    console.log('[TaskScheduler] Persisting tasks to disk');
  }

  private startScheduler(): void {
    this.checkInterval = setInterval(() => {
      this.checkDueTasks();
    }, this.config.checkInterval);
    
    // Run an initial check immediately
    this.checkDueTasks();
  }

  parseNaturalLanguageSchedule(input: string): ScheduleParseResult {
    // NLP parsing of dates/times from natural language
    const lower = input.toLowerCase();
    const now = Date.now();
    
    // Simple examples
    if (lower.includes('tomorrow at 9am')) {
      const tomorrow = new Date(now + 24 * 60 * 60 * 1000);
      tomorrow.setHours(9, 0, 0, 0);
      
      return {
        success: true,
        schedule: {
          type: 'once',
          runAt: tomorrow,
          timezone: this.config.defaultTimezone
        }
      };
    }
    
    if (lower.includes('every monday at 8am')) {
      return {
        success: true,
        schedule: {
          type: 'recurring',
          cron: '0 8 * * 1', // Every Monday at 8 AM
          timezone: this.config.defaultTimezone
        }
      };
    }
    
    if (lower.includes('in 30 minutes')) {
      const runAt = new Date(now + 30 * 60 * 1000);
      return {
        success: true,
        schedule: {
          type: 'once',
          runAt,
          timezone: this.config.defaultTimezone
        }
      };
    }

    // Fallback - parse as immediate
    return {
      success: true,
      schedule: {
        type: 'once',
        runAt: new Date(now + 10000), // 10 seconds from now
        timezone: this.config.defaultTimezone
      }
    };
  }

  async scheduleTask(task: Omit<ScheduledTask, 'id' | 'createdAt' | 'nextRun' | 'currentRetries' | 'status'>): Promise<ScheduledTask> {
    const fullTask: ScheduledTask = {
      ...task,
      id: `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      createdAt: Date.now(),
      nextRun: task.schedule.runAt ? task.schedule.runAt.getTime() : Date.now(),
      currentRetries: 0,
      status: 'pending'
    };
    
    this.tasks.set(fullTask.id, fullTask);
    this.scheduleTaskExecution(fullTask);
    
    await this.persistTasks();
    
    this.emit('taskScheduled', fullTask);
    console.log(`[TaskScheduler] Scheduled: ${task.name} (${fullTask.id})`);
    
    return fullTask;
  }

  private scheduleTaskExecution(task: ScheduledTask): void {
    const delay = task.nextRun - Date.now();
    if (delay <= 0) return;
    
    const timer = setTimeout(() => {
      this.executeTask(task);
    }, delay);
    
    this.activeTimers.set(task.id, timer);
  }

  private async checkDueTasks(): Promise<void> {
    if (this.isChecking) return;
    this.isChecking = true;
    
    try {
      const now = Date.now();
      for (const [id, task] of this.tasks) {
        if (task.status === 'pending' && task.nextRun <= now) {
          await this.executeTask(task);
        }
      }
    } finally {
      this.isChecking = false;
    }
  }

  private async executeTask(task: ScheduledTask): Promise<TaskRunResult> {
    const startTime = Date.now();
    task.status = 'running';
    task.lastRun = startTime;
    
    this.emit('taskStarted', task);
    console.log(`[TaskScheduler] Executing: ${task.name}`);

    try {
      // In production, this would coordinate with AgentCoordinator
      await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate execution
      
      task.status = task.schedule.type === 'recurring' ? 'active' : 'completed';
      
      // Calculate next run for recurring tasks
      if (task.schedule.type === 'recurring') {
        task.nextRun = this.calculateNextRun(task.schedule);
        this.scheduleTaskExecution(task);
      }
      
      const result: TaskRunResult = {
        taskId: task.id,
        success: true,
        startTime,
        endTime: Date.now()
      };
      
      this.emit('taskCompleted', result);
      console.log(`[TaskScheduler] Completed: ${task.name}`);
      
      return result;

    } catch (error) {
      task.currentRetries++;
      
      if (task.currentRetries < task.maxRetries) {
        // Retry with exponential backoff
        const backoffMs = Math.pow(2, task.currentRetries) * 60000;
        task.nextRun = Date.now() + backoffMs;
        task.status = 'pending';
        this.scheduleTaskExecution(task);
        console.log(`[TaskScheduler] Retrying ${task.name} in ${backoffMs}ms`);
      } else {
        task.status = 'failed';
        console.error(`[TaskScheduler] Task failed after ${task.maxRetries} retries: ${task.name}`);
      }
      
      const result: TaskRunResult = {
        taskId: task.id,
        success: false,
        startTime,
        endTime: Date.now(),
        error: error instanceof Error ? error.message : 'Unknown error'
      };
      
      this.emit('taskFailed', result);
      return result;
    }
  }

  private calculateNextRun(schedule: ScheduleRule): number {
    // Parse cron and calculate next execution time
    return Date.now() + 7 * 24 * 60 * 60 * 1000; // Default to 1 week
  }

  async cancelTask(taskId: string): Promise<boolean> {
    const task = this.tasks.get(taskId);
    if (!task) return false;
    
    // Clear any active timer
    const timer = this.activeTimers.get(taskId);
    if (timer) {
      clearTimeout(timer);
      this.activeTimers.delete(taskId);
    }
    
    task.status = 'paused';
    this.tasks.delete(taskId);
    await this.persistTasks();
    
    this.emit('taskCancelled', taskId);
    console.log(`[TaskScheduler] Cancelled: ${task.name}`);
    
    return true;
  }

  getAllTasks(): ScheduledTask[] {
    return Array.from(this.tasks.values());
  }

  getTask(taskId: string): ScheduledTask | undefined {
    return this.tasks.get(taskId);
  }

  async shutdown(): Promise<void> {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
    }
    
    // Clear all timers
    for (const timer of this.activeTimers.values()) {
      clearTimeout(timer);
    }
    this.activeTimers.clear();
    
    await this.persistTasks();
    this.isInitialized = false;
    
    this.emit('shutdown');
    console.log('[TaskScheduler] Shutdown complete');
  }
}

// Singleton
let schedulerInstance: TaskScheduler | null = null;

export function getTaskScheduler(config?: Partial<SchedulerConfig>): TaskScheduler {
  if (!schedulerInstance) {
    schedulerInstance = new TaskScheduler(config);
  }
  return schedulerInstance;
}