import React, { useState, useEffect } from "react";
import { X, Download, RotateCcw, Clock } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type UpdateState = "idle" | "checking" | "available" | "downloading" | "downloaded" | "error";

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
}

const UpdateModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
}> = ({ isOpen, onClose }) => {
  const [updateState, setUpdateState] = useState<UpdateState>("idle");
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dash = window.dash as any;
    if (!dash?.updater?.on) return;

    const removeCheck = dash.updater.on("checking", () => {
      setUpdateState("checking");
      setError(null);
    });

    const removeAvailable = dash.updater.on("available", (info: UpdateInfo) => {
      setUpdateState("available");
      setUpdateInfo(info);
    });

    const removeNotAvailable = dash.updater.on("not-available", () => {
      setUpdateState("idle");
      setError(null);
    });

    const removeProgress = dash.updater.on("progress", (data: ProgressData) => {
      setUpdateState("downloading");
      setProgress(data);
    });

    const removeDownloaded = dash.updater.on("downloaded", (info: UpdateInfo) => {
      setUpdateState("downloaded");
      setUpdateInfo(info);
    });

    const removeError = dash.updater.on("error", (err: string) => {
      setUpdateState("error");
      setError(err);
    });

    return () => {
      removeCheck();
      removeAvailable();
      removeNotAvailable();
      removeProgress();
      removeDownloaded();
      removeError();
    };
  }, []);

  const handleCheckForUpdates = () => {
    const dash = window.dash as any;
    dash?.updater?.checkForUpdates();
  };

  const handleStartDownload = () => {
    const dash = window.dash as any;
    dash?.updater?.startDownload();
  };

  const handleRestartAndInstall = () => {
    const dash = window.dash as any;
    dash?.updater?.quitAndInstall();
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative w-full max-w-md bg-zinc-900 rounded-2xl border border-zinc-800 shadow-2xl p-6 m-4"
        >
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-zinc-400" />
          </button>

          <div className="mb-6">
            <h2 className="text-xl font-semibold text-white">Software Update</h2>
            <p className="text-sm text-zinc-400 mt-1">
              {updateState === "idle" && "Check for updates to get the latest features and fixes."}
              {updateState === "checking" && "Checking for updates..."}
              {updateState === "available" && "A new version is available!"}
              {updateState === "downloading" && "Downloading update..."}
              {updateState === "downloaded" && "Update is ready to install!"}
              {updateState === "error" && "Something went wrong while checking for updates."}
            </p>
          </div>

          {updateState === "idle" && (
            <div className="space-y-4">
              <button
                onClick={handleCheckForUpdates}
                className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                <Clock className="w-5 h-5" />
                Check for Updates
              </button>
            </div>
          )}

          {updateState === "checking" && (
            <div className="flex items-center justify-center py-8">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <span className="ml-3 text-zinc-400">Checking GitHub for updates...</span>
            </div>
          )}

          {updateState === "available" && (
            <div className="space-y-4">
              {updateInfo?.version && (
                <div className="bg-zinc-800/50 rounded-xl p-4">
                  <p className="text-sm text-zinc-400">New Version</p>
                  <p className="text-lg font-semibold text-white">{updateInfo.version}</p>
                </div>
              )}
              <div className="flex gap-3">
                <button
                  onClick={onClose}
                  className="flex-1 py-3 bg-zinc-800 hover:bg-zinc-700 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  <Clock className="w-5 h-5" />
                  Later
                </button>
                <button
                  onClick={handleStartDownload}
                  className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  <Download className="w-5 h-5" />
                  Update
                </button>
              </div>
            </div>
          )}

          {updateState === "downloading" && progress && (
            <div className="space-y-4">
              <div className="w-full bg-zinc-800 rounded-full h-3 overflow-hidden">
                <motion.div
                  className="h-full bg-blue-500 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress.percent}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">{progress.percent.toFixed(1)}%</span>
                <span className="text-zinc-400">
                  {formatBytes(progress.transferred)} / {formatBytes(progress.total)}
                </span>
              </div>
              <p className="text-xs text-zinc-500 text-center">
                {formatBytes(progress.bytesPerSecond)}/s
              </p>
            </div>
          )}

          {updateState === "downloaded" && (
            <div className="space-y-4">
              <div className="bg-emerald-900/30 border border-emerald-700/50 rounded-xl p-4">
                <p className="text-emerald-400 text-center font-medium">
                  Update downloaded successfully!
                </p>
              </div>
              <button
                onClick={handleRestartAndInstall}
                className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                <RotateCcw className="w-5 h-5" />
                Restart to Update
              </button>
            </div>
          )}

          {updateState === "error" && (
            <div className="space-y-4">
              <div className="bg-red-900/30 border border-red-700/50 rounded-xl p-4">
                <p className="text-red-400 text-center text-sm">{error || "Failed to check for updates"}</p>
              </div>
              <button
                onClick={onClose}
                className="w-full py-3 bg-zinc-800 hover:bg-zinc-700 text-white font-medium rounded-xl transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default UpdateModal;