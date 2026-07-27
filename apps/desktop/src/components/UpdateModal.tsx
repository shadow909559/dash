import { AnimatePresence, motion } from "framer-motion";
import {
  CheckCircle,
  Download,
  Github,
  Power,
  PowerOff,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Progress, Update, useUpdater } from "../hooks/useUpdater";
import { Button } from "./Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./Dialog";
import { useNetwork } from "../hooks/useNetwork";
import { Tooltip, TooltipContent, TooltipTrigger } from "./Tooltip";
import { Badge } from "./Badge";
import { Separator } from "./Separator";

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return "0 Bytes";

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function formatSpeed(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B/s`;
  } else if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(2)} KB/s`;
  } else {
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB/s`;
  }
}

function estimateETA(
  downloaded: number,
  total: number,
  speed: number
): string | null {
  if (speed === 0) {
    return null;
  }

  const remainingBytes = total - downloaded;
  const remainingSeconds = remainingBytes / speed;

  if (remainingSeconds < 60) {
    return `${Math.round(remainingSeconds)}s`;
  } else if (remainingSeconds < 3600) {
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = Math.round(remainingSeconds % 60);
    return `${minutes}m ${seconds}s`;
  } else {
    const hours = Math.floor(remainingSeconds / 3600);
    const minutes = Math.round((remainingSeconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  }
}

interface UpdateModalProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function UpdateModal({ isOpen: controlledIsOpen, onClose }: UpdateModalProps = {}) {
  const {
    updateState,
    checkForUpdates,
    downloadUpdate,
    installUpdate,
    progress,
    update,
    error,
    isUpdateAvailable,
  } = useUpdater();
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const { isOnline } = useNetwork();

  const isOpen = controlledIsOpen !== undefined ? controlledIsOpen : internalIsOpen;
  const setIsOpen = (open: boolean) => {
    setInternalIsOpen(open);
    if (!open && onClose) {
      onClose();
    }
  };

  useEffect(() => {
    if (isUpdateAvailable) {
      setIsOpen(true);
    }
  }, [isUpdateAvailable]);

  const handleCheckForUpdates = () => {
    if (!isOnline) return;
    checkForUpdates();
    setIsOpen(true);
  };

  const handleInstall = () => {
    if (updateState !== "downloaded") return;
    installUpdate();
  };

  const handleDownload = () => {
    if (updateState !== "available" || !isOnline) return;
    downloadUpdate();
  };

  const renderUpdateDetails = (update: Update) => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge
            variant="default"
            className="text-sm font-mono rounded-md"
          >
            {update.version}
          </Badge>
          <span className="text-zinc-400">
            {new Date(update.date).toLocaleDateString()}
          </span>
        </div>
        <a
          href={`https://github.com/im-lonely/dash/releases/tag/v${update.version}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-zinc-400 hover:text-white transition-colors"
        >
          <Github size={18} />
        </a>
      </div>
      <Separator />
      <div
        className="prose prose-sm prose-invert max-h-60 overflow-y-auto"
        dangerouslySetInnerHTML={{ __html: update.body }}
      />
    </div>
  );

  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleCheckForUpdates}
            className="relative"
          >
            <Download size={18} />
            {isUpdateAvailable && (
              <div className="absolute top-1 right-1 w-2 h-2 bg-blue-500 rounded-full" />
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {isUpdateAvailable ? "Update available" : "Check for updates"}
        </TooltipContent>
      </Tooltip>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Download size={18} />
              Software Update
            </DialogTitle>
            <DialogDescription>
              {isOnline
                ? "Check for new updates, review release notes, and install them."
                : "You are offline. Please connect to the internet to check for updates."}
            </DialogDescription>
          </DialogHeader>

          <AnimatePresence mode="wait">
            <motion.div
              key={updateState}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              {/* Checking for updates */}
              {updateState === "checking" && (
                <div className="flex items-center justify-center p-8">
                  <div className="flex items-center gap-2 text-zinc-400">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{
                        repeat: Infinity,
                        duration: 1,
                        ease: "linear",
                      }}
                    >
                      <Download size={18} />
                    </motion.div>
                    <span>Checking for updates...</span>
                  </div>
                </div>
              )}

              {/* No update available */}
              {updateState === "no-update" && (
                <div className="flex flex-col items-center justify-center p-8 text-center">
                  <CheckCircle size={32} className="text-green-500 mb-4" />
                  <h3 className="font-semibold">You're up to date!</h3>
                  <p className="text-sm text-zinc-400">
                    You are running the latest version of the software.
                  </p>
                </div>
              )}

              {/* Update available */}
              {updateState === "available" && update && (
                <div className="space-y-4">
                  {renderUpdateDetails(update)}
                  <Button
                    onClick={handleDownload}
                    className="w-full"
                    disabled={!isOnline}
                  >
                    <Download size={16} className="mr-2" />
                    Download Update
                  </Button>
                </div>
              )}

              {/* Downloading */}
              {updateState === "downloading" && progress && (
                <div className="space-y-3">
                  <div className="w-full bg-zinc-800 rounded-full h-3 overflow-hidden">
                    <motion.div
                      className="h-full bg-blue-500 rounded-full"
                      initial={{ width: 0 }}
                      animate={{
                        width: `${Math.min(progress.percent, 100)}%`,
                      }}
                      transition={{ duration: 0.3 }}
                    />
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-400">
                      {progress.percent.toFixed(1)}%
                    </span>
                    <span className="text-zinc-400">
                      {formatBytes(progress.transferred)} /{" "}
                      {formatBytes(progress.total)}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-zinc-500">
                    <span>{formatSpeed(progress.bytesPerSecond)}</span>
                    <span>
                      {estimateETA(
                        progress.transferred,
                        progress.total,
                        progress.bytesPerSecond
                      ) &&
                        `ETA: ${estimateETA(
                          progress.transferred,
                          progress.total,
                          progress.bytesPerSecond
                        )}`}
                    </span>
                  </div>
                </div>
              )}

              {/* Downloaded */}
              {updateState === "downloaded" && update && (
                <div className="space-y-4">
                  {renderUpdateDetails(update)}
                  <Button onClick={handleInstall} className="w-full">
                    <Power size={16} className="mr-2" />
                    Install and Relaunch
                  </Button>
                </div>
              )}

              {/* Error */}
              {updateState === "error" && (
                <div className="flex flex-col items-center justify-center p-8 text-center">
                  <XCircle size={32} className="text-red-500 mb-4" />
                  <h3 className="font-semibold">Update Failed</h3>
                  <p className="text-sm text-zinc-400 max-w-xs">
                    {error ||
                      "An unknown error occurred while updating. Please try again later."}
                  </p>
                </div>
              )}

              {/* Offline */}
              {!isOnline && updateState !== "downloading" && (
                <div className="flex flex-col items-center justify-center p-8 text-center">
                  <PowerOff size={32} className="text-zinc-500 mb-4" />
                  <h3 className="font-semibold">You are offline</h3>
                  <p className="text-sm text-zinc-400">
                    Please connect to the internet to check for updates.
                  </p>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default UpdateModal;
