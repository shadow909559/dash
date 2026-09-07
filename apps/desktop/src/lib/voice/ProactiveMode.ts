/**
 * ProactiveMode - Handles proactive notifications and suggestions
 * 
 * Features:
 * - Battery low notifications
 * - Internet disconnected notifications
 * - Meeting reminders
 * - Download completion notifications
 * - Suggest actions
 * - Smart suggestions based on context
 */

import { EventEmitter } from '../EventEmitter';

export interface ProactiveNotification {
  id: string;
  type: 'battery' | 'network' | 'meeting' | 'download' | 'reminder' | 'suggestion';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  title: string;
  message: string;
  timestamp: number;
  actionSuggested?: string;
  dismissed: boolean;
}

export interface ProactiveConfig {
  enabled: boolean;
  batteryThreshold: number;
  enableBatteryAlerts: boolean;
  enableNetworkAlerts: boolean;
  enableMeetingReminders: boolean;
  enableDownloadAlerts: boolean;
  enableSuggestions: boolean;
  quietHours: { start: number; end: number };
}

export class ProactiveMode extends EventEmitter {
  private config: ProactiveConfig;
  private notifications: ProactiveNotification[] = [];
  private isInitialized: boolean = false;
  private monitoringInterval: number | null = null;
  private systemState: any = {};

  constructor(config: any) {
    super();
    this.config = {
      enabled: config.enabled !== false,
      batteryThreshold: config.batteryThreshold || 20,
      enableBatteryAlerts: config.enableBatteryAlerts !== false,
      enableNetworkAlerts: config.enableNetworkAlerts !== false,
      enableMeetingReminders: config.enableMeetingReminders !== false,
      enableDownloadAlerts: config.enableDownloadAlerts !== false,
      enableSuggestions: config.enableSuggestions !== false,
      quietHours: config.quietHours || { start: 22, end: 8 },
    };
  }

  async initialize(): Promise<void> {
    try {
      console.log('[ProactiveMode] Initializing...');

      // Initialize system monitoring
      await this.initializeSystemMonitoring();

      this.isInitialized = true;
      console.log('[ProactiveMode] Initialized successfully');

    } catch (error) {
      console.error('[ProactiveMode] Initialization failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  async startMonitoring(): Promise<void> {
    if (!this.isInitialized) {
      throw new Error('ProactiveMode not initialized');
    }

    if (!this.config.enabled) {
      console.log('[ProactiveMode] Proactive mode disabled');
      return;
    }

    try {
      // Monitor system state every 30 seconds
      this.monitoringInterval = window.setInterval(() => {
        this.checkSystemState();
      }, 30000);

      this.emit('monitoringStarted');
      console.log('[ProactiveMode] Started monitoring');

    } catch (error) {
      console.error('[ProactiveMode] Failed to start monitoring:', error);
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
    console.log('[ProactiveMode] Stopped monitoring');
  }

  private async initializeSystemMonitoring(): Promise<void> {
    // Initialize battery monitoring
    if (this.config.enableBatteryAlerts && 'getBattery' in navigator) {
      try {
        const battery = await (navigator as any).getBattery();
        this.systemState.battery = {
          level: battery.level * 100,
          charging: battery.charging,
        };
      } catch (error) {
        console.log('[ProactiveMode] Battery API not available');
      }
    }

    // Initialize network monitoring
    if (this.config.enableNetworkAlerts) {
      this.systemState.online = navigator.onLine;
      window.addEventListener('online', () => this.handleNetworkChange(true));
      window.addEventListener('offline', () => this.handleNetworkChange(false));
    }
  }

  private checkSystemState(): void {
    // Check battery
    if (this.config.enableBatteryAlerts && this.systemState.battery) {
      this.checkBattery();
    }

    // Check network
    if (this.config.enableNetworkAlerts) {
      this.checkNetwork();
    }

    // Check for upcoming meetings
    if (this.config.enableMeetingReminders) {
      this.checkMeetings();
    }
  }

  private checkBattery(): void {
    const battery = this.systemState.battery;
    
    if (!battery.charging && battery.level <= this.config.batteryThreshold) {
      this.addNotification({
        id: this.generateId(),
        type: 'battery',
        priority: battery.level <= 10 ? 'urgent' : 'high',
        title: 'Battery Low',
        message: `Battery at ${battery.level}%. Consider charging.`,
        timestamp: Date.now(),
        actionSuggested: 'Connect charger',
        dismissed: false,
      });
    }
  }

  private checkNetwork(): void {
    const wasOnline = this.systemState.online;
    const isOnline = navigator.onLine;

    if (wasOnline && !isOnline) {
      this.addNotification({
        id: this.generateId(),
        type: 'network',
        priority: 'high',
        title: 'Internet Disconnected',
        message: 'You appear to be offline.',
        timestamp: Date.now(),
        actionSuggested: 'Check connection',
        dismissed: false,
      });
    } else if (!wasOnline && isOnline) {
      this.addNotification({
        id: this.generateId(),
        type: 'network',
        priority: 'low',
        title: 'Internet Connected',
        message: 'You are back online.',
        timestamp: Date.now(),
        dismissed: false,
      });
    }

    this.systemState.online = isOnline;
  }

  private handleNetworkChange(online: boolean): void {
    this.systemState.online = online;
    this.checkNetwork();
  }

  private checkMeetings(): void {
    // This would integrate with calendar API
    // For now, it's a placeholder
    const now = new Date();
    const hour = now.getHours();

    // Check if within quiet hours
    if (this.isQuietHours()) {
      return;
    }

    // Example: Check for meetings in next 30 minutes
    // This would be implemented with actual calendar integration
  }

  private isQuietHours(): boolean {
    const now = new Date();
    const hour = now.getHours();
    const { start, end } = this.config.quietHours;

    if (start < end) {
      return hour >= start && hour < end;
    } else {
      // Overnight quiet hours (e.g., 22:00 to 08:00)
      return hour >= start || hour < end;
    }
  }

  addNotification(notification: ProactiveNotification): void {
    // Check for duplicates
    const existing = this.notifications.find(n => 
      n.type === notification.type && 
      !n.dismissed && 
      (Date.now() - n.timestamp) < 60000 // Within last minute
    );

    if (existing) {
      return; // Don't add duplicate notification
    }

    this.notifications.push(notification);
    this.emit('notification', notification);
    console.log('[ProactiveMode] Notification added:', notification.title);
  }

  dismissNotification(id: string): void {
    const notification = this.notifications.find(n => n.id === id);
    if (notification) {
      notification.dismissed = true;
      this.emit('notificationDismissed', notification);
    }
  }

  getNotifications(dismissed: boolean = false): ProactiveNotification[] {
    return this.notifications.filter(n => n.dismissed === dismissed);
  }

  getPendingNotifications(): ProactiveNotification[] {
    return this.notifications.filter(n => !n.dismissed);
  }

  clearDismissedNotifications(): void {
    this.notifications = this.notifications.filter(n => !n.dismissed);
    this.emit('notificationsCleared');
  }

  /**
   * Generate context-aware suggestions
   */
  generateSuggestion(context: any): string | null {
    if (!this.config.enableSuggestions) {
      return null;
    }

    // Analyze context and generate suggestions
    if (context.currentApplication === 'code_editor' && context.unsavedChanges) {
      return 'You have unsaved changes. Would you like to save them?';
    }

    if (context.currentApplication === 'browser' && context.manyTabs) {
      return 'You have many tabs open. Would you like to close some?';
    }

    if (context.timeOfDay === 'morning' && context.noMeetings) {
      return 'You have no meetings this morning. Would you like to focus on deep work?';
    }

    return null;
  }

  /**
   * Suggest action based on notification
   */
  async executeSuggestedAction(notificationId: string): Promise<void> {
    const notification = this.notifications.find(n => n.id === notificationId);
    if (!notification || !notification.actionSuggested) {
      return;
    }

    this.emit('actionExecuted', {
      notificationId,
      action: notification.actionSuggested,
    });

    this.dismissNotification(notificationId);
  }

  private generateId(): string {
    return `notif_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  updateConfig(config: Partial<ProactiveConfig>): void {
    this.config = { ...this.config, ...config };
  }

  async shutdown(): Promise<void> {
    await this.stopMonitoring();
    this.isInitialized = false;
    console.log('[ProactiveMode] Shutdown complete');
  }
}
