import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsState {
  theme: 'dark' | 'light';
  fontSize: number;
  windowSize: { width: number; height: number };
  sidebarState: boolean;
  startupPage: string;
  notificationPreferences: {
    enabled: boolean;
    sound: boolean;
  };
  autoLaunch: boolean;
  startMinimized: boolean;
  minimizeToTray: boolean;
  apiUrl: string;
  
  updateSettings: (settings: Partial<SettingsState>) => void;
  resetSettings: () => void;
}

const defaultSettings: SettingsState = {
  theme: 'dark',
  fontSize: 14,
  windowSize: { width: 1200, height: 800 },
  sidebarState: false, // expanded
  startupPage: '/',
  notificationPreferences: {
    enabled: true,
    sound: true,
  },
  autoLaunch: false,
  startMinimized: false,
  minimizeToTray: true,
  apiUrl: 'http://127.0.0.1:8000/api/v1',
  
  updateSettings: () => {},
  resetSettings: () => {},
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      ...defaultSettings,
      updateSettings: (newSettings) => set((state) => ({ ...state, ...newSettings })),
      resetSettings: () => set(defaultSettings),
    }),
    {
      name: 'app-settings',
    }
  )
);