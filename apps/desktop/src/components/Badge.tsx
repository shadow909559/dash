import React from "react";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline";
}

export function Badge({
  className = "",
  variant = "default",
  children,
  ...props
}: BadgeProps) {
  const baseStyle =
    "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2";
  const variants = {
    default: "border-transparent bg-blue-600 text-white hover:bg-blue-700",
    secondary: "border-transparent bg-zinc-800 text-zinc-300 hover:bg-zinc-700",
    destructive: "border-transparent bg-red-600 text-white hover:bg-red-700",
    outline: "text-zinc-300 border border-zinc-700",
  };

  return (
    <div
      className={`${baseStyle} ${variants[variant] || variants.default} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
