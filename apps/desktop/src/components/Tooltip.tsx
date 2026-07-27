import React, { useState } from "react";

interface TooltipContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const TooltipContext = React.createContext<TooltipContextType>({
  open: false,
  setOpen: () => {},
});

export function Tooltip({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <TooltipContext.Provider value={{ open, setOpen }}>
      <div
        className="relative inline-block"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {children}
      </div>
    </TooltipContext.Provider>
  );
}

export function TooltipTrigger({
  children,
  asChild,
}: {
  children: React.ReactNode;
  asChild?: boolean;
}) {
  return <>{children}</>;
}

export function TooltipContent({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { open } = React.useContext(TooltipContext);
  if (!open) return null;

  return (
    <div
      className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 px-2 py-1 text-xs text-white bg-zinc-900 border border-zinc-800 rounded shadow-lg whitespace-nowrap ${className}`}
    >
      {children}
    </div>
  );
}
