import React from "react";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
  circle?: boolean;
}

const Skeleton: React.FC<SkeletonProps> = ({
  width,
  height,
  circle = false,
  className = "",
  style = {},
  ...props
}) => {
  const styles: React.CSSProperties = {
    ...style,
    width: width ?? "100%",
    height: height ?? "1rem",
    borderRadius: circle ? "50%" : "0.25rem",
    backgroundColor: "var(--bg-glass-hover)",
    animation: "pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
  };

  return <div className={`skeleton ${className}`} style={styles} {...props} />;
};

export default Skeleton;