import { contextBridge } from 'electron';

/**
 * Expose a minimal, typed API surface to the renderer process.
 * Foundation milestone — no IPC handlers yet.
 */
contextBridge.exposeInMainWorld('dash', {
  version: '0.1.0',
  platform: process.platform,
});

export type DashPreloadApi = {
  version: string;
  platform: NodeJS.Platform;
};

declare global {
  interface Window {
    dash: DashPreloadApi;
  }
}
