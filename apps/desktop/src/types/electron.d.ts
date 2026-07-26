export interface UpdaterAPI {
  checkForUpdates: () => Promise<void>;
  startDownload: () => Promise<void>;
  quitAndInstall: () => Promise<void>;
  setAutoDownload: (value: boolean) => Promise<void>;
  setAutoInstallOnQuit: (value: boolean) => Promise<void>;
  on: (event: string, callback: (...args: any[]) => void) => () => void;
}

export interface DashAPI {
  version: string;
  platform: string;
  updater: UpdaterAPI;
}

declare global {
  interface Window {
    dash: DashAPI;
  }
}

export {};