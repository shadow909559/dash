import { useState, useCallback, useRef } from "react";

export interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "warning" | "info";
}

let toastId = 0;

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timeoutRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(
    new Map()
  );

  const removeToast = useCallback((id: string) => {
    const t = timeoutRef.current.get(id);
    if (t) clearTimeout(t);
    timeoutRef.current.delete(id);
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (message: string, type: Toast["type"] = "info", duration = 4000) => {
      const id = `toast-${++toastId}`;
      setToasts((prev) => [...prev, { id, message, type }]);
      const t = setTimeout(() => removeToast(id), duration);
      timeoutRef.current.set(id, t);
      return id;
    },
    [removeToast]
  );

  return { toasts, addToast, removeToast };
}
