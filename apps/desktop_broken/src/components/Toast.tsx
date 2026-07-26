import React, { useState, useEffect } from "react";

interface ToastProps {
  id: string;
  title: string;
  message?: string;
  type: "success" | "error" | "info";
  onClose: (id: string) => void;
}

const Toast: React.FC<ToastProps> = ({ id, title, message, type, onClose }) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setTimeout(() => setIsVisible(true), 10);
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => onClose(id), 300);
    }, 5000);
    return () => clearTimeout(timer);
  }, [id, onClose]);

  const colors = {
    success: "bg-green-500",
    error: "bg-red-500",
    info: "bg-blue-500",
  };

  const icons = {
    success: "✓",
    error: "✕",
    info: "ℹ",
  };

  return (
    <div
      className={`glass-card p-4 mb-2 transition-all duration-300 ${isVisible ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"}`}
      style={{ minWidth: 300 }}
    >
      <div className="flex items-start gap-3">
        <div className={`${colors[type]} w-6 h-6 rounded-full flex items-center justify-center text-white text-sm`}>
          {icons[type]}
        </div>
        <div className="flex-1">
          <div className="font-medium text-sm text-white">{title}</div>
          {message && <div className="text-xs text-gray-300 mt-1">{message}</div>}
        </div>
        <button onClick={() => { setIsVisible(false); setTimeout(() => onClose(id), 300); }} className="text-gray-400 hover:text-white">
          ✕
        </button>
      </div>
    </div>
  );
};

interface ToastItem {
  id: string;
  title: string;
  message?: string;
  type: "success" | "error" | "info";
}

const ToastContainer: React.FC<{ toasts: ToastItem[]; removeToast: (id: string) => void }> = ({ toasts, removeToast }) => {
  return (
    <div className="fixed top-4 right-4 z-5000">
      {toasts.map((toast) => (
        <Toast key={toast.id} {...toast} onClose={removeToast} />
      ))}
    </div>
  );
};

// Toast manager
let toastsState: ToastItem[] = [];
let listeners: ((toasts: ToastItem[]) => void)[] = [];

function notify(toast: Omit<ToastItem, "id">) {
  const id = Math.random().toString(36).substr(2, 9);
  toastsState = [...toastsState, { ...toast, id }];
  listeners.forEach((l) => l(toastsState));
  return id;
}

function removeToast(id: string) {
  toastsState = toastsState.filter((t) => t.id !== id);
  listeners.forEach((l) => l(toastsState));
}

function subscribe(listener: (toasts: ToastItem[]) => void) {
  listeners.push(listener);
  return () => {
    listeners = listeners.filter((l) => l !== listener);
  };
}

export { ToastContainer, notify, subscribe };