/**
 * DesktopSpeechCommands - Handles desktop automation through voice commands
 * 
 * Features:
 * - Open/close applications
 * - File/folder operations
 * - Window management
 * - System controls
 * - Browser commands
 * - Search functionality
 * - Natural language understanding
 */

import { EventEmitter } from '../EventEmitter';
import { getAutomationEngine } from '../automation/DesktopAutomationEngine';

export interface CommandResult {
  success: boolean;
  action: string;
  result: any;
  error?: string;
}

export interface CommandPattern {
  intent: string;
  patterns: RegExp[];
  action: (matches: string[]) => Promise<CommandResult>;
  examples: string[];
}

export class DesktopSpeechCommands extends EventEmitter {
  private commands: Map<string, CommandPattern> = new Map();
  private isInitialized: boolean = false;
  private automationEngine = getAutomationEngine();

  constructor() {
    super();
  }

  async initialize(): Promise<void> {
    try {
      console.log('[DesktopSpeechCommands] Initializing...');

      // Register all command patterns
      this.registerCommands();

      this.isInitialized = true;
      console.log('[DesktopSpeechCommands] Initialized successfully');

    } catch (error) {
      console.error('[DesktopSpeechCommands] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async processCommand(text: string): Promise<CommandResult> {
    if (!this.isInitialized) {
      throw new Error('DesktopSpeechCommands not initialized');
    }

    try {
      console.log('[DesktopSpeechCommands] Processing command:', text);

      const lowerText = text.toLowerCase();

      // Match against all command patterns
      for (const [intent, command] of this.commands) {
        for (const pattern of command.patterns) {
          const match = lowerText.match(pattern);
          if (match) {
            console.log('[DesktopSpeechCommands] Matched intent:', intent);
            const result = await command.action(match);
            this.emit('commandExecuted', { intent, result });
            return result;
          }
        }
      }

      // No match found
      return {
        success: false,
        action: 'unknown',
        result: null,
        error: 'Command not recognized',
      };

    } catch (error) {
      console.error('[DesktopSpeechCommands] Failed to process command:', error);
      this.emit('error', error);
      return {
        success: false,
        action: 'error',
        result: null,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  private registerCommands(): void {
    // Open application commands
    this.registerCommand({
      intent: 'open_application',
      patterns: [
        /open\s+(.+)/,
        /launch\s+(.+)/,
        /start\s+(.+)/,
      ],
      action: async (matches) => {
        const appName = matches[1].trim();
        return await this.openApplication(appName);
      },
      examples: ['Open Chrome', 'Launch VS Code', 'Start Spotify'],
    });

    // Close application commands
    this.registerCommand({
      intent: 'close_application',
      patterns: [
        /close\s+(.+)/,
        /quit\s+(.+)/,
        /exit\s+(.+)/,
      ],
      action: async (matches) => {
        const appName = matches[1].trim();
        return await this.closeApplication(appName);
      },
      examples: ['Close Chrome', 'Quit VS Code', 'Exit Spotify'],
    });

    // Search commands
    this.registerCommand({
      intent: 'search',
      patterns: [
        /search\s+(?:for\s+)?(.+)/,
        /find\s+(?:for\s+)?(.+)/,
        /look\s+(?:for\s+)?(.+)/,
      ],
      action: async (matches) => {
        const query = matches[1].trim();
        return await this.search(query);
      },
      examples: ['Search for weather', 'Find restaurants nearby', 'Look for Python tutorial'],
    });

    // File commands
    this.registerCommand({
      intent: 'open_file',
      patterns: [
        /open\s+(?:file\s+)?(.+)/,
        /show\s+(?:file\s+)?(.+)/,
      ],
      action: async (matches) => {
        const filePath = matches[1].trim();
        return await this.openFile(filePath);
      },
      examples: ['Open file document.txt', 'Show file README.md'],
    });

    // Folder commands
    this.registerCommand({
      intent: 'open_folder',
      patterns: [
        /open\s+(?:folder\s+)?(.+)/,
        /show\s+(?:folder\s+)?(.+)/,
      ],
      action: async (matches) => {
        const folderPath = matches[1].trim();
        return await this.openFolder(folderPath);
      },
      examples: ['Open folder Documents', 'Show folder Downloads'],
    });

    // Browser commands
    this.registerCommand({
      intent: 'open_website',
      patterns: [
        /open\s+(?:website\s+)?(.+)/,
        /go\s+to\s+(.+)/,
        /navigate\s+to\s+(.+)/,
      ],
      action: async (matches) => {
        const url = matches[1].trim();
        return await this.openWebsite(url);
      },
      examples: ['Open website google.com', 'Go to github.com', 'Navigate to stackoverflow.com'],
    });

    // Window commands
    this.registerCommand({
      intent: 'maximize_window',
      patterns: [
        /maximize/,
        /fullscreen/,
      ],
      action: async () => {
        return await this.maximizeWindow();
      },
      examples: ['Maximize', 'Fullscreen'],
    });

    this.registerCommand({
      intent: 'minimize_window',
      patterns: [
        /minimize/,
      ],
      action: async () => {
        return await this.minimizeWindow();
      },
      examples: ['Minimize'],
    });

    // System commands
    this.registerCommand({
      intent: 'shutdown',
      patterns: [
        /shutdown/,
        /turn\s+off/,
      ],
      action: async () => {
        return await this.shutdownSystem();
      },
      examples: ['Shutdown', 'Turn off'],
    });

    this.registerCommand({
      intent: 'restart',
      patterns: [
        /restart/,
        /reboot/,
      ],
      action: async () => {
        return await this.restart();
      },
      examples: ['Restart', 'Reboot'],
    });
  }

  private registerCommand(command: CommandPattern): void {
    this.commands.set(command.intent, command);
  }

  // Command implementations - fully integrated with DesktopAutomationEngine
  private async openApplication(appName: string): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Opening application:', appName);
    
    try {
      // Map common app names to what the automation engine understands
      const appMapping: Record<string, string> = {
        'chrome': 'chrome',
        'google chrome': 'chrome',
        'vscode': 'code',
        'vs code': 'code',
        'visual studio code': 'code',
        'steam': 'steam',
        'discord': 'discord',
        'blender': 'blender',
        'spotify': 'spotify',
      };
      
      const mappedApp = appMapping[appName.toLowerCase()] || appName;
      const command = await this.automationEngine.executeCommand(
        'application', 
        'open', 
        { app: mappedApp },
        { safetyLevel: 'safe', requireConfirmation: false }
      );
      
      this.emit('openApplication', { appName, command });
      return {
        success: command.status === 'completed',
        action: 'open_application',
        result: { appName, command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'open_application',
        result: { appName },
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async closeApplication(appName: string): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Closing application:', appName);
    
    try {
      const appMapping: Record<string, string> = {
        'chrome': 'chrome',
        'google chrome': 'chrome',
        'vscode': 'code',
        'vs code': 'code',
        'visual studio code': 'code',
        'steam': 'steam',
        'discord': 'discord',
        'blender': 'blender',
        'spotify': 'spotify',
      };
      
      const mappedApp = appMapping[appName.toLowerCase()] || appName;
      const command = await this.automationEngine.executeCommand(
        'application', 
        'close', 
        { app: mappedApp },
        { safetyLevel: 'safe', requireConfirmation: false }
      );
      
      this.emit('closeApplication', { appName, command });
      return {
        success: command.status === 'completed',
        action: 'close_application',
        result: { appName, command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'close_application',
        result: { appName },
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async search(query: string): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Searching for:', query);
    
    try {
      const command = await this.automationEngine.executeCommand(
        'browser', 
        'search', 
        { engine: 'google', query },
        { safetyLevel: 'safe', requireConfirmation: false }
      );
      
      this.emit('search', { query, command });
      return {
        success: command.status === 'completed',
        action: 'search',
        result: { query, command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'search',
        result: { query },
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async openFile(filePath: string): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Opening file:', filePath);
    
    try {
      // For files, we use application open with the file path
      const command = await this.automationEngine.executeCommand(
        'file',
        'open',
        { path: filePath },
        { safetyLevel: 'safe', requireConfirmation: false }
      );
      
      this.emit('openFile', { filePath, command });
      return {
        success: command.status === 'completed',
        action: 'open_file',
        result: { filePath, command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'open_file',
        result: { filePath },
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async openFolder(folderPath: string): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Opening folder:', folderPath);
    
    try {
      const command = await this.automationEngine.executeCommand(
        'file',
        'openFolder',
        { path: folderPath },
        { safetyLevel: 'safe', requireConfirmation: false }
      );
      
      this.emit('openFolder', { folderPath, command });
      return {
        success: command.status === 'completed',
        action: 'open_folder',
        result: { folderPath, command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'open_folder',
        result: { folderPath },
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async openWebsite(url: string): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Opening website:', url);
    
    try {
      // Ensure URL has protocol
      let fullUrl = url;
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        fullUrl = `https://${url}`;
      }
      
      const command = await this.automationEngine.executeCommand(
        'browser',
        'open',
        { url: fullUrl },
        { safetyLevel: 'safe', requireConfirmation: false }
      );
      
      this.emit('openWebsite', { url: fullUrl, command });
      return {
        success: command.status === 'completed',
        action: 'open_website',
        result: { url: fullUrl, command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'open_website',
        result: { url },
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async maximizeWindow(): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Maximizing window');
    
    try {
      const command = await this.automationEngine.executeCommand(
        'window',
        'maximize',
        {},
        { safetyLevel: 'safe', requireConfirmation: false }
      );
      
      this.emit('maximizeWindow', { command });
      return {
        success: command.status === 'completed',
        action: 'maximize_window',
        result: { command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'maximize_window',
        result: {},
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async minimizeWindow(): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Minimizing window');
    
    try {
      const command = await this.automationEngine.executeCommand(
        'window',
        'minimize',
        {},
        { safetyLevel: 'safe', requireConfirmation: false }
      );
      
      this.emit('minimizeWindow', { command });
      return {
        success: command.status === 'completed',
        action: 'minimize_window',
        result: { command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'minimize_window',
        result: {},
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async shutdownSystem(): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Shutting down');
    
    try {
      const command = await this.automationEngine.executeWorkflow('shutdown pc');
      
      this.emit('shutdown', { command });
      return {
        success: command.status === 'completed',
        action: 'shutdown',
        result: { command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'shutdown',
        result: {},
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  private async restart(): Promise<CommandResult> {
    console.log('[DesktopSpeechCommands] Restarting');
    
    try {
      const command = await this.automationEngine.executeWorkflow('restart');
      
      this.emit('restart', { command });
      return {
        success: command.status === 'completed',
        action: 'restart',
        result: { command },
        error: command.error
      };
    } catch (error) {
      return {
        success: false,
        action: 'restart',
        result: {},
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  getCommandExamples(): string[] {
    const examples: string[] = [];
    this.commands.forEach(command => {
      examples.push(...command.examples);
    });
    return examples;
  }

  getAvailableIntents(): string[] {
    return Array.from(this.commands.keys());
  }

  async shutdown(): Promise<void> {
    this.commands.clear();
    this.isInitialized = false;
    console.log('[DesktopSpeechCommands] Shutdown complete');
  }
}