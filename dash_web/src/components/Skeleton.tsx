interface SkeletonProps {
  variant?: "text" | "heading" | "card";
  count?: number;
  style?: React.CSSProperties;
}

export function Skeleton({ variant = "text", count = 1, style }: SkeletonProps) {
  return (
    <div style={style}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={`skeleton skeleton--${variant}`} />
      ))}
    </div>
  );
}
