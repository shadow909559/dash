/// <reference types="vite/client" />

export {};

declare global {
  interface Window {
    dash: {
      version: string;
      platform: string;
      window: {
        minimize: () => void;
        maximize: () => void;
        close: () => void;
        isMaximized: () => Promise<boolean>;
      };
      dialog: {
        openFile: (options?: any) => Promise<{ canceled: boolean; filePaths: string[] }>;
        saveFile: (options?: any) => Promise<{ canceled: boolean; filePath?: string }>;
      };
      clipboard: {
        readText: () => Promise<string>;
        writeText: (text: string) => Promise<void>;
      };
      notification: {
        show: (title: string, body: string) => Promise<void>;
      };
      tray: {
        minimizeToTray: () => void;
      };
      app: {
        getPath: (name: string) => Promise<string>;
        getVersion: () => Promise<string>;
      };
      settings: {
        getAutoLaunch: () => Promise<boolean>;
        setAutoLaunch: (enabled: boolean) => Promise<void>;
      };
      theme: {
        getNative: () => Promise<string>;
        onChange: (callback: (theme: string) => void) => void;
      };
    };
  }
}
