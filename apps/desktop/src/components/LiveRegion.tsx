import React, { useEffect, useRef } from "react";

interface LiveRegionProps {
  /** The text content to announce */
  children: React.ReactNode;
  /** aria-live policy: "polite" (wait for idle) or "assertive" (interrupt) */
  politeness?: "polite" | "assertive";
  /** aria-atomic — announce the entire region or just changes */
  atomic?: boolean;
  /** Optional CSS class */
  className?: string;
  /** Visually hidden (screen readers only) */
  hidden?: boolean;
}

/**
 * ARIA live region for dynamic content updates.
 * Screen readers announce changes to this element's text content.
 *
 * Usage:
 *   <LiveRegion>{`CPU: ${cpu}%`}</LiveRegion>
 */
export function LiveRegion({
  children,
  politeness = "polite",
  atomic = true,
  className,
  hidden = true,
}: LiveRegionProps) {
  const ref = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={ref}
      role="status"
      aria-live={politeness}
      aria-atomic={atomic}
      className={className}
      style={
        hidden
          ? {
              position: "absolute",
              width: 1,
              height: 1,
              padding: 0,
              margin: -1,
              overflow: "hidden",
              clip: "rect(0, 0, 0, 0)",
              whiteSpace: "nowrap",
              border: 0,
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}

/**
 * Assertive live region for urgent announcements (errors, critical alerts).
 */
export function AlertRegion({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <LiveRegion politeness="assertive" className={className}>
      {children}
    </LiveRegion>
  );
}
