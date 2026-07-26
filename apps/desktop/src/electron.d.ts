export {};

declare global {
  interface Window {
    dash: {
      version: string;
      platform: string;
      updater: {
        checkForUpdates: () => Promise<void>;
        startDownload: () => Promise<void>;
        quitAndInstall: () => Promise<void>;
        setAutoDownload: (value: boolean) => Promise<void>;
        setAutoInstallOnQuit: (value: boolean) => Promise<void>;
        on: (event: string, callback: (...args: any[]) => void) => () => void;
        off: (event: string, callback: (...args: any[]) => void) => void;
      };
    };
  }
}