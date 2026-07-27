import { useState, useEffect, useCallback } from 'react';

export interface Update {
  version: string;
  date: string;
  body: string;
}

export interface Progress {
  percent: number;
  transferred: number;
  total: number;
  bytesPerSecond: number;
}

type UpdateState =
  | 'idle'
  | 'checking'
  | 'no-update'
  | 'available'
  | 'downloading'
  | 'downloaded'
  | 'error';

export function useUpdater() {
  const [updateState, setUpdateState] = useState<UpdateState>('idle');
  const [progress, setProgress] = useState<Progress | null>(null);
  const [update, setUpdate] = useState<Update | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUpdateAvailable, setIsUpdateAvailable] = useState(false);

  useEffect(() => {
    const updater = window.dash?.updater || (window as any).electronAPI?.updater;
    if (!updater || typeof updater.on !== 'function') {
      return;
    }

    const handleUpdateAvailable = (info: any) => {
      setUpdate({
        version: info?.version || '1.0.0',
        date: info?.releaseDate || new Date().toISOString(),
        body: info?.releaseNotes || 'New updates available.',
      });
      setUpdateState('available');
      setIsUpdateAvailable(true);
    };

    const handleUpdateNotAvailable = () => {
      setUpdateState('no-update');
      setIsUpdateAvailable(false);
    };

    const handleDownloadProgress = (progressInfo: Progress) => {
      setProgress(progressInfo);
      setUpdateState('downloading');
    };

    const handleUpdateDownloaded = () => {
      setUpdateState('downloaded');
    };

    const handleError = (err: Error) => {
      setError(err.message || 'Update error');
      setUpdateState('error');
    };

    const cleanupUpdateAvailable = updater.on('update-available', handleUpdateAvailable);
    const cleanupUpdateNotAvailable = updater.on('update-not-available', handleUpdateNotAvailable);
    const cleanupDownloadProgress = updater.on('download-progress', handleDownloadProgress);
    const cleanupUpdateDownloaded = updater.on('update-downloaded', handleUpdateDownloaded);
    const cleanupError = updater.on('error', handleError);

    return () => {
      if (typeof cleanupUpdateAvailable === 'function') cleanupUpdateAvailable();
      if (typeof cleanupUpdateNotAvailable === 'function') cleanupUpdateNotAvailable();
      if (typeof cleanupDownloadProgress === 'function') cleanupDownloadProgress();
      if (typeof cleanupUpdateDownloaded === 'function') cleanupUpdateDownloaded();
      if (typeof cleanupError === 'function') cleanupError();
    };
  }, []);

  const checkForUpdates = useCallback(() => {
    setUpdateState('checking');
    setError(null);
    const updater = window.dash?.updater || (window as any).electronAPI?.updater;
    if (updater) {
      if (typeof (updater as any).checkForUpdates === 'function') {
        (updater as any).checkForUpdates();
      } else if (typeof (updater as any).check === 'function') {
        (updater as any).check();
      }
    }
  }, []);

  const downloadUpdate = useCallback(() => {
    setUpdateState('downloading');
    const updater = window.dash?.updater || (window as any).electronAPI?.updater;
    if (updater) {
      if (typeof (updater as any).startDownload === 'function') {
        (updater as any).startDownload();
      } else if (typeof (updater as any).download === 'function') {
        (updater as any).download();
      }
    }
  }, []);

  const installUpdate = useCallback(() => {
    const updater = window.dash?.updater || (window as any).electronAPI?.updater;
    if (updater) {
      if (typeof (updater as any).quitAndInstall === 'function') {
        (updater as any).quitAndInstall();
      } else if (typeof (updater as any).install === 'function') {
        (updater as any).install();
      }
    }
  }, []);

  return {
    updateState,
    checkForUpdates,
    downloadUpdate,
    installUpdate,
    progress,
    update,
    error,
    isUpdateAvailable,
  };
}