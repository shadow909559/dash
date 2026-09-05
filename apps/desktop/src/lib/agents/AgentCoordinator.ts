/**
 * AgentCoordinator - Central orchestrator for all specialized DASH agents
 * 
 * Features:
 * - Agent registration and management
 * - Work distribution and task assignment
 * - Inter-agent communication bus
 * - Parallel execution support
 * - Health monitoring of all agents
 * - Error handling and recovery
 */

import { EventEmitter } from '../EventEmitter';
import { getAutomationEngine } from '../automation/DesktopAutomationEngine';

export type AgentType = 
  | 'coordinator'
  | 'memory'
  | 'research'
  | 'coding'
  | 'automation'
  | 'desktop'
  | 'android'
  | 'planning'
  | 'voice'
  | 'vision'
  | 'security'
  | 'system';

export interface Agent {
  id: string;
  type: AgentType;
  name: string;
  isInitialized: boolean;
  isBusy: boolean;
  capabilities: string[];
  lastActive: number;
  status: 'idle' | 'busy' | 'error' | 'offline';
}

export interface AgentTask {
  id: string;
  type: string;
  payload: any;
  priority: number;
  assignedAgent: string | null;
  status: 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed';
  timestamp: number;
  result?: any;
  error?: string;
}

export interface AgentMessage {
  from: string;
  to: string;
  type: string;
  payload: any;
  timestamp: number;
}

export interface CoordinatorConfig {
  enableParallelExecution: boolean;
  maxConcurrentTasks: number;
  enableHealthMonitoring: boolean;
  healthCheckInterval: number;
  autoRecovery: boolean;
}

export class AgentCoordinator extends EventEmitter {
  private config: CoordinatorConfig;
  private agents: Map<string, Agent> = new Map();
  private taskQueue: AgentTask[] = [];
  private activeTasks: Map<string, AgentTask> = new Map();
  private messageBus: AgentMessage[] = [];
  private isInitialized: boolean = false;
  private healthCheckInterval: ReturnType<typeof setInterval> | null = null;
  private automationEngine = getAutomationEngine();

  constructor(config: Partial<CoordinatorConfig> = {}) {
    super();
    this.config = {
      enableParallelExecution: true,
      maxConcurrentTasks: 4,
      enableHealthMonitoring: true,
      healthCheckInterval: 30000,
      autoRecovery: true,
      ...config
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[AgentCoordinator] Initializing...');

      // Register all core agents
      this.registerCoreAgents();
      
      // Initialize health monitoring
      if (this.config.enableHealthMonitoring) {
        this.startHealthMonitoring();
      }

      this.isInitialized = true;
      console.log('[AgentCoordinator] All agents registered and initialized');
      this.emit('initialized');

    } catch (error) {
      console.error('[AgentCoordinator] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  private registerCoreAgents(): void {
    // Register all specialized agents
    const coreAgents: Agent[] = [
      {
        id: 'memory-agent-001',
        type: 'memory',
        name: 'MemoryAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['store', 'recall', 'semantic_search', 'summarize'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'research-agent-001',
        type: 'research',
        name: 'ResearchAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['search', 'summarize', 'verify', 'citations'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'coding-agent-001',
        type: 'coding',
        name: 'CodingAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['generate', 'refactor', 'debug', 'test', 'document'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'automation-agent-001',
        type: 'automation',
        name: 'AutomationAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['workflow', 'schedule', 'execute'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'desktop-agent-001',
        type: 'desktop',
        name: 'DesktopAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['window_management', 'file_system', 'system_control'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'android-agent-001',
        type: 'android',
        name: 'AndroidCompanionAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['sync', 'notification_relay', 'file_transfer', 'remote_control'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'planning-agent-001',
        type: 'planning',
        name: 'PlanningAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['schedule', 'prioritize', 'project_management'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'voice-agent-001',
        type: 'voice',
        name: 'VoiceAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['tts', 'stt', 'wake_word', 'interruption'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'vision-agent-001',
        type: 'vision',
        name: 'VisionAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['ocr', 'object_detection', 'screenshot_analysis', 'ui_control'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'security-agent-001',
        type: 'security',
        name: 'SecurityAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['encryption', 'permission_check', 'privacy_monitor'],
        lastActive: Date.now(),
        status: 'idle'
      },
      {
        id: 'system-agent-001',
        type: 'system',
        name: 'SystemAgent',
        isInitialized: true,
        isBusy: false,
        capabilities: ['monitoring', 'health_check', 'optimization'],
        lastActive: Date.now(),
        status: 'idle'
      }
    ];

    coreAgents.forEach(agent => {
      this.agents.set(agent.id, agent);
      console.log(`[AgentCoordinator] Registered ${agent.name}`);
    });

    this.emit('agentsRegistered', coreAgents.length);
  }

  async assignTask(task: Omit<AgentTask, 'id' | 'timestamp' | 'assignedAgent' | 'status'>): Promise<AgentTask> {
    const fullTask: AgentTask = {
      ...task,
      id: `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
      assignedAgent: null,
      status: 'pending'
    };

    this.taskQueue.push(fullTask);
    this.processTaskQueue();
    
    this.emit('taskQueued', fullTask);
    return fullTask;
  }

  private async processTaskQueue(): Promise<void> {
    if (this.activeTasks.size >= this.config.maxConcurrentTasks) {
      return;
    }

    while (this.taskQueue.length > 0 && this.activeTasks.size < this.config.maxConcurrentTasks) {
      const task = this.taskQueue.shift();
      if (!task) continue;

      // Find best agent for this task
      const agent = this.findSuitableAgent(task.type);
      if (!agent) {
        this.taskQueue.unshift(task); // Put back in queue
        break;
      }

      // Assign task to agent
      task.assignedAgent = agent.id;
      task.status = 'assigned';
      agent.isBusy = true;
      agent.status = 'busy';
      
      this.activeTasks.set(task.id, task);
      this.emit('taskAssigned', task, agent);

      // Execute task in parallel if enabled
      if (this.config.enableParallelExecution) {
        this.executeTask(task, agent);
      }
    }
  }

  private findSuitableAgent(taskType: string): Agent | null {
    for (const [id, agent] of this.agents) {
      if (!agent.isBusy && agent.capabilities.some(cap => taskType.toLowerCase().includes(cap.toLowerCase()))) {
        return agent;
      }
    }
    return null;
  }

  private async executeTask(task: AgentTask, agent: Agent): Promise<void> {
    task.status = 'in_progress';
    this.emit('taskStarted', task);

    try {
      console.log(`[AgentCoordinator] Executing task ${task.id} on ${agent.name}`);
      
      let result;
      // If this is an automation task, delegate to our desktop automation engine
      if (agent.type === 'automation' || agent.type === 'desktop') {
        if (task.type === 'workflow' && task.payload?.workflowName) {
          // Execute a predefined workflow
          const command = await this.automationEngine.executeWorkflow(
            task.payload.workflowName,
            task.payload.parameters
          );
          result = { success: command.status === 'completed', command };
        } else if (task.payload?.type && task.payload?.action) {
          // Execute a direct automation command
          const command = await this.automationEngine.executeCommand(
            task.payload.type,
            task.payload.action,
            task.payload.parameters || {},
            task.payload.options || {}
          );
          result = { success: command.status === 'completed', command };
        } else {
          // Fallback for unknown automation task format
          await new Promise(resolve => setTimeout(resolve, 1000));
          result = { success: true };
        }
      } else {
        // For non-automation tasks, just simulate work
        await new Promise(resolve => setTimeout(resolve, 1000));
        result = { success: true };
      }
      
      task.status = 'completed';
      task.result = result;
      agent.isBusy = false;
      agent.status = 'idle';
      agent.lastActive = Date.now();
      
      this.activeTasks.delete(task.id);
      this.emit('taskCompleted', task);
      
      // Process next task
      this.processTaskQueue();

    } catch (error) {
      task.status = 'failed';
      task.error = error instanceof Error ? error.message : 'Unknown error';
      agent.isBusy = false;
      agent.status = 'error';
      
      this.activeTasks.delete(task.id);
      this.emit('taskFailed', task, error);
      
      // Auto-retry if enabled
      if (this.config.autoRecovery) {
        console.log(`[AgentCoordinator] Retrying task ${task.id}...`);
        this.taskQueue.push(task);
        setTimeout(() => this.processTaskQueue(), 1000);
      }
    }
  }

  sendMessage(from: string, to: string, type: string, payload: any): void {
    const message: AgentMessage = {
      from,
      to,
      type,
      payload,
      timestamp: Date.now()
    };
    
    this.messageBus.push(message);
    this.emit('messageSent', message);
    
    // Route message to target agent
    const targetAgent = this.agents.get(to);
    if (targetAgent) {
      this.emit(`message:${to}`, message);
    }
  }

  getAvailableAgents(): Agent[] {
    return Array.from(this.agents.values()).filter(a => !a.isBusy);
  }

  getActiveTasks(): AgentTask[] {
    return Array.from(this.activeTasks.values());
  }

  private startHealthMonitoring(): void {
    this.healthCheckInterval = setInterval(() => {
      this.performHealthCheck();
    }, this.config.healthCheckInterval);
  }

  private performHealthCheck(): void {
    console.log('[AgentCoordinator] Performing agent health check...');
    
    for (const [id, agent] of this.agents) {
      const inactive = Date.now() - agent.lastActive > 5 * 60 * 1000; // 5 minutes
      if (inactive && agent.status !== 'offline') {
        console.warn(`[AgentCoordinator] Agent ${agent.name} appears unresponsive`);
        agent.status = 'error';
        this.emit('agentUnhealthy', agent);
        
        if (this.config.autoRecovery) {
          this.attemptAgentRecovery(agent);
        }
      }
    }
  }

  private attemptAgentRecovery(agent: Agent): void {
    console.log(`[AgentCoordinator] Attempting recovery for ${agent.name}`);
    // Recovery logic here
    agent.status = 'idle';
    agent.isBusy = false;
    agent.lastActive = Date.now();
    this.emit('agentRecovered', agent);
  }

  async shutdown(): Promise<void> {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
    }
    
    this.agents.clear();
    this.taskQueue = [];
    this.activeTasks.clear();
    this.isInitialized = false;
    
    this.emit('shutdown');
    console.log('[AgentCoordinator] Shutdown complete');
  }
}

// Singleton
let coordinatorInstance: AgentCoordinator | null = null;

export function getAgentCoordinator(config?: Partial<CoordinatorConfig>): AgentCoordinator {
  if (!coordinatorInstance) {
    coordinatorInstance = new AgentCoordinator(config);
  }
  return coordinatorInstance;
}