export {};

interface UpdaterStatus {
  checkInProgress: boolean;
  updateAvailable: boolean;
  updateDownloaded: boolean;
  version: string;
}

interface UpdaterResult {
  ok: boolean;
  reason?: string;
}

interface UpdateInfo {
  version?: string;
  releaseDate?: string;
  releaseNotes?: string;
}

interface ProgressData {
  percent: number;
  transferred: number;
  total: number;
  bytesPerSecond: number;
  delta?: number;
}

interface UpdaterAPI {
  status: () => Promise<UpdaterStatus>;
  check: () => Promise<UpdaterResult>;
  download: () => Promise<UpdaterResult>;
  install: () => Promise<UpdaterResult>;
  on: (event: string, callback: (...args: any[]) => void) => () => void;
  off: (event: string, callback: (...args: any[]) => void) => void;
}

interface ElectronAPI {
  platform: string;
  updater: UpdaterAPI;
}

interface LegacyUpdaterAPI {
  checkForUpdates: () => Promise<UpdaterResult>;
  startDownload: () => Promise<UpdaterResult>;
  quitAndInstall: () => Promise<UpdaterResult>;
  setAutoDownload: () => Promise<void>;
  setAutoInstallOnQuit: () => Promise<void>;
  on: (event: string, callback: (...args: any[]) => void) => () => void;
  off: (event: string, callback: (...args: any[]) => void) => void;
}

interface DashAPI {
  version: string;
  platform: string;
  updater: LegacyUpdaterAPI;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
    dash: DashAPI;
  }
}
