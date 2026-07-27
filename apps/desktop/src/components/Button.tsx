import * as React from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
  size?: "default" | "sm" | "lg" | "icon";
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = "", variant = "default", size = "default", children, ...props }, ref) => {
    const baseStyle =
      "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50";

    const variantStyles = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      destructive: "bg-red-600 text-white hover:bg-red-700",
      outline: "border border-zinc-700 bg-transparent hover:bg-zinc-800 text-zinc-100",
      secondary: "bg-zinc-800 text-zinc-100 hover:bg-zinc-700",
      ghost: "hover:bg-zinc-800 text-zinc-300 hover:text-white",
      link: "text-blue-500 underline-offset-4 hover:underline",
    };

    const sizeStyles = {
      default: "h-10 px-4 py-2",
      sm: "h-9 rounded-md px-3 text-xs",
      lg: "h-11 rounded-md px-8",
      icon: "h-10 w-10",
    };

    const combinedClassName = `${baseStyle} ${variantStyles[variant] || variantStyles.default} ${
      sizeStyles[size] || sizeStyles.default
    } ${className}`.trim();

    return (
      <button className={combinedClassName} ref={ref} {...props}>
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";

export { Button };