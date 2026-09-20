// DASH fx — micro-interaction components adapted from open-source animation
// libraries (React Bits' ShinyText/CountUp, KokonutUI's spotlight cards,
// Bklit's staggered reveals). Implemented with the project's existing
// framer-motion dependency — no new packages.

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

/* ── ShinyText ─────────────────────────────────────────────────────
 * React Bits technique: a shimmering light sweep across clipped text.
 * Pure CSS animation on a gradient background-clip: text element.
 * ──────────────────────────────────────────────────────────────── */
interface ShinyTextProps {
  children: ReactNode;
  /** Base (dim) color of the text. */
  color?: string;
  /** Color of the light sweep. */
  shineColor?: string;
  /** Seconds per sweep (0 disables the animation). */
  speed?: number;
  disabled?: boolean;
  style?: CSSProperties;
  className?: string;
}

const shinyKeyframes = `
@keyframes dash-shiny-sweep {
  0% { background-position: 200% center; }
  100% { background-position: -200% center; }
}
`;

// Inject once per app — idempotent.
let shinyStylesInjected = false;
function ensureShinyStyles() {
  if (shinyStylesInjected || typeof document === "undefined") return;
  const style = document.createElement("style");
  style.id = "dash-fx-shiny";
  style.textContent = shinyKeyframes;
  document.head.appendChild(style);
  shinyStylesInjected = true;
}

export function ShinyText({
  children,
  color = "rgba(224, 240, 255, 0.55)",
  shineColor = "#7dd3fc",
  speed = 3,
  disabled = false,
  style,
  className,
}: ShinyTextProps) {
  ensureShinyStyles();
  return (
    <span
      className={className}
      style={{
        color: "transparent",
        backgroundImage: `linear-gradient(120deg, ${color} 40%, ${shineColor} 50%, ${color} 60%)`,
        backgroundSize: "200% 100%",
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        animation: disabled ? "none" : `dash-shiny-sweep ${Math.max(0.5, speed)}s linear infinite`,
        ...style,
      }}
    >
      {children}
    </span>
  );
}

/* ── CountUp ───────────────────────────────────────────────────────
 * React Bits technique: animated number counting with easing and a
 * thousand-groups separator, driven by a spring for natural motion.
 * ──────────────────────────────────────────────────────────────── */
interface CountUpProps {
  to: number;
  /** Animate from zero on mount (default true). */
  fromZero?: boolean;
  durationMs?: number;
  decimals?: number;
  separator?: string;
  suffix?: string;
  prefix?: string;
  style?: CSSProperties;
  className?: string;
}

export function CountUp({
  to,
  fromZero = true,
  durationMs = 1200,
  decimals = 0,
  separator = ",",
  suffix = "",
  prefix = "",
  style,
  className,
}: CountUpProps) {
  const from = fromZero ? 0 : to;
  const mv = useMotionValue(from);
  const spring = useSpring(mv, {
    duration: durationMs,
    bounce: 0,
  });
  const text = useTransform(spring, (v) =>
    prefix +
    Number(v.toFixed(decimals)).toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
      useGrouping: !!separator,
    }) +
    suffix,
  );

  useEffect(() => {
    mv.set(to);
  }, [to, mv]);

  return <motion.span className={className} style={style}>{text}</motion.span>;
}

/* ── SpotlightCard ─────────────────────────────────────────────────
 * KokonutUI/Aceternity technique: a radial spotlight that follows the
 * cursor across a card's border and surface via CSS custom properties.
 * ──────────────────────────────────────────────────────────────── */
interface SpotlightCardProps {
  children: ReactNode;
  /** Accent color of the spotlight (any CSS color). */
  spotlightColor?: string;
  /** Spotlight radius in px. */
  radius?: number;
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
}

export function SpotlightCard({
  children,
  spotlightColor = "rgba(63, 169, 245, 0.16)",
  radius = 240,
  style,
  className,
  onClick,
}: SpotlightCardProps) {
  const ref = useRef<HTMLDivElement>(null);

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--spot-x", `${e.clientX - rect.left}px`);
    el.style.setProperty("--spot-y", `${e.clientY - rect.top}px`);
    el.style.setProperty("--spot-active", "1");
  };
  const onLeave = () => {
    ref.current?.style.setProperty("--spot-active", "0");
  };

  return (
    <div
      ref={ref}
      className={className}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      onClick={onClick}
      style={{
        position: "relative",
        isolation: "isolate",
        ...style,
      }}
    >
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "inherit",
          pointerEvents: "none",
          opacity: "var(--spot-active, 0)",
          transition: "opacity 300ms ease",
          background: `radial-gradient(${radius}px circle at var(--spot-x, 50%) var(--spot-y, 50%), ${spotlightColor}, transparent 70%)`,
          zIndex: 0,
        }}
      />
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  );
}

/* ── StaggerReveal ─────────────────────────────────────────────────
 * Bklit-style staggered entrance: children fade/slide up in sequence.
 * ──────────────────────────────────────────────────────────────── */
interface StaggerRevealProps {
  children: ReactNode;
  /** Seconds between each child. */
  stagger?: number;
  delay?: number;
  distance?: number;
  style?: CSSProperties;
  className?: string;
}

export function StaggerReveal({
  children,
  stagger = 0.08,
  delay = 0,
  distance = 16,
  style,
  className,
}: StaggerRevealProps) {
  return (
    <motion.div
      className={className}
      style={style}
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: stagger, delayChildren: delay } },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  distance = 16,
  style,
  className,
}: {
  children: ReactNode;
  distance?: number;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      style={style}
      variants={{
        hidden: { opacity: 0, y: distance },
        show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
      }}
    >
      {children}
    </motion.div>
  );
}

/* ── GradientBorderCard ────────────────────────────────────────────
 * KokonutUI technique: an animated conic-gradient border (rotating
 * glow) around a card. Uses ::before under an inset mask.
 * ──────────────────────────────────────────────────────────────── */
const conicKeyframes = `
@keyframes dash-border-spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
`;
let conicStylesInjected = false;
function ensureConicStyles() {
  if (conicStylesInjected || typeof document === "undefined") return;
  const style = document.createElement("style");
  style.id = "dash-fx-conic";
  style.textContent = conicKeyframes;
  document.head.appendChild(style);
  conicStylesInjected = true;
}

interface GradientBorderCardProps {
  children: ReactNode;
  colors?: string[];
  /** Seconds per rotation (0 = static gradient). */
  speed?: number;
  padding?: number;
  style?: CSSProperties;
  className?: string;
}

export function GradientBorderCard({
  children,
  colors = ["#3fa9f5", "transparent", "#a855f7", "transparent", "#3fa9f5"],
  speed = 6,
  padding = 1,
  style,
  className,
}: GradientBorderCardProps) {
  ensureConicStyles();
  const [size, setSize] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize(Math.max(el.offsetWidth, el.offsetHeight) * 2);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        position: "relative",
        borderRadius: "var(--dash-radius-md)",
        overflow: "hidden",
        ...style,
      }}
    >
      {/* Rotating conic gradient, masked to a 1px ring */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          width: size || 400,
          height: size || 400,
          marginTop: -(size || 400) / 2,
          marginLeft: -(size || 400) / 2,
          background: `conic-gradient(${colors.join(", ")})`,
          animation: speed > 0 ? `dash-border-spin ${speed}s linear infinite` : "none",
          padding,
          borderRadius: "50%",
          WebkitMask:
            "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          WebkitMaskComposite: "xor",
          mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          maskComposite: "exclude",
          zIndex: 0,
        }}
      />
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  );
}

/* ── TiltCard ──────────────────────────────────────────────────────
 * React Bits / 21st.dev technique: pointer-tracked 3D tilt with a
 * light glare that follows the cursor. Spring-damped; degrades to a
 * flat card under prefers-reduced-motion.
 * ──────────────────────────────────────────────────────────────── */
interface TiltCardProps {
  children: ReactNode;
  maxTilt?: number;
  glare?: boolean;
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
}

export function TiltCard({
  children,
  maxTilt = 8,
  glare = true,
  style,
  className,
  onClick,
}: TiltCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const rx = useSpring(useMotionValue(0), { stiffness: 260, damping: 24 });
  const ry = useSpring(useMotionValue(0), { stiffness: 260, damping: 24 });
  const gx = useMotionValue(50); // glare position, percent
  const gy = useMotionValue(50);
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  const onMove = (e: React.PointerEvent) => {
    if (reduced) return;
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width; // 0..1
    const py = (e.clientY - r.top) / r.height;
    ry.set((px - 0.5) * maxTilt * 2);
    rx.set(-(py - 0.5) * maxTilt * 2);
    gx.set(px * 100);
    gy.set(py * 100);
  };
  const onLeave = () => {
    rx.set(0);
    ry.set(0);
    gx.set(50);
    gy.set(50);
  };

  const glareBg = useTransform(
    [gx, gy],
    ([x, y]: number[]) =>
      `radial-gradient(420px circle at ${x}% ${y}%, rgba(140, 200, 255, 0.10), transparent 65%)`,
  );

  return (
    <motion.div
      ref={ref}
      className={className}
      onClick={onClick}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={{
        transformStyle: "preserve-3d",
        rotateX: reduced ? 0 : rx,
        rotateY: reduced ? 0 : ry,
        ...style,
      }}
    >
      {children}
      {glare && !reduced && (
        <motion.div
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "inherit",
            background: glareBg,
            pointerEvents: "none",
          }}
          initial={{ opacity: 0 }}
          whileHover={{ opacity: 1 }}
        />
      )}
    </motion.div>
  );
}

/* ── Magnetic ──────────────────────────────────────────────────────
 * 21st.dev technique: element leans toward the cursor within a small
 * radius — the "instrument responds to you" micro-feel.
 * ──────────────────────────────────────────────────────────────── */
export function Magnetic({
  children,
  strength = 0.25,
  style,
  className,
}: {
  children: ReactNode;
  strength?: number;
  style?: CSSProperties;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useSpring(useMotionValue(0), { stiffness: 300, damping: 26 });
  const y = useSpring(useMotionValue(0), { stiffness: 300, damping: 26 });
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{ x: reduced ? 0 : x, y: reduced ? 0 : y, display: "inline-block", ...style }}
      onPointerMove={(e) => {
        if (reduced) return;
        const el = ref.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        x.set((e.clientX - (r.left + r.width / 2)) * strength);
        y.set((e.clientY - (r.top + r.height / 2)) * strength);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.div>
  );
}

/* ── Aurora ────────────────────────────────────────────────────────
 * Slow drifting ambient light field — blurred radial fields on
 * independent loops. Absolutely positioned by the consumer.
 * ──────────────────────────────────────────────────────────────── */
const auroraKeyframes = `
@keyframes dash-aurora-a {
  0% { transform: translate(-8%, -4%) scale(1); }
  50% { transform: translate(6%, 5%) scale(1.12); }
  100% { transform: translate(-8%, -4%) scale(1); }
}
@keyframes dash-aurora-b {
  0% { transform: translate(5%, 6%) scale(1.05); }
  50% { transform: translate(-6%, -3%) scale(1); }
  100% { transform: translate(5%, 6%) scale(1.05); }
}
`;
let auroraStylesInjected = false;
function ensureAuroraStyles() {
  if (auroraStylesInjected || typeof document === "undefined") return;
  const style = document.createElement("style");
  style.id = "dash-fx-aurora";
  style.textContent = auroraKeyframes;
  document.head.appendChild(style);
  auroraStylesInjected = true;
}

export function Aurora({
  intensity = 1,
  style,
  className,
}: {
  intensity?: number;
  style?: CSSProperties;
  className?: string;
}) {
  ensureAuroraStyles();
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const a = `rgba(63, 169, 245, ${0.07 * intensity})`;
  const b = `rgba(78, 205, 196, ${0.05 * intensity})`;
  const c = `rgba(139, 92, 246, ${0.05 * intensity})`;
  return (
    <div
      aria-hidden
      className={className}
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
        zIndex: 0,
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: "-20%",
          background: `radial-gradient(42% 38% at 26% 24%, ${a}, transparent 70%), radial-gradient(36% 34% at 74% 62%, ${b}, transparent 70%)`,
          filter: "blur(24px)",
          animation: reduced ? "none" : "dash-aurora-a 26s ease-in-out infinite",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "-20%",
          background: `radial-gradient(40% 36% at 62% 20%, ${c}, transparent 70%)`,
          filter: "blur(28px)",
          animation: reduced ? "none" : "dash-aurora-b 34s ease-in-out infinite",
        }}
      />
    </div>
  );
}

/* ── RevealOnScroll ───────────────────────────────────────────────
 * IntersectionObserver-based mount reveal for long scroll pages.
 * ──────────────────────────────────────────────────────────────── */
export function RevealOnScroll({
  children,
  distance = 18,
  threshold = 0.12,
  style,
  className,
}: {
  children: ReactNode;
  distance?: number;
  threshold?: number;
  style?: CSSProperties;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const en of entries) {
          if (en.isIntersecting) {
            setSeen(true);
            io.disconnect();
          }
        }
      },
      { threshold },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);

  return (
    <motion.div
      ref={ref}
      className={className}
      style={style}
      initial={false}
      animate={seen ? { opacity: 1, y: 0 } : { opacity: 0, y: distance }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

/* ── TypingIndicator ───────────────────────────────────────────────
 * React Bits / Kokonut technique: three spring-animated dots with an
 * optional shimmer label — the "assistant is thinking" cue.
 * ──────────────────────────────────────────────────────────────── */
export function TypingIndicator({
  color = "var(--dash-accent)",
  label,
  style,
  className,
}: {
  color?: string;
  label?: string;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <div
      className={className}
      style={{ display: "flex", alignItems: "center", gap: 10, ...style }}
    >
      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: color,
              display: "block",
            }}
            animate={{ y: [0, -4, 0], opacity: [0.35, 1, 0.35], scale: [0.85, 1, 0.85] }}
            transition={{
              duration: 1.1,
              repeat: Infinity,
              ease: "easeInOut",
              delay: i * 0.15,
            }}
          />
        ))}
      </div>
      {label && (
        <ShinyText color="rgba(143, 178, 212, 0.6)" shineColor={color} speed={2.2}>
          <span style={{ fontSize: 11, letterSpacing: "0.08em" }}>{label}</span>
        </ShinyText>
      )}
    </div>
  );
}

/* ── StreamingCaret ────────────────────────────────────────────────
 * Blinking block caret appended to streaming assistant text.
 * ──────────────────────────────────────────────────────────────── */
let caretStylesInjected = false;
function ensureCaretStyles() {
  if (caretStylesInjected || typeof document === "undefined") return;
  const style = document.createElement("style");
  style.id = "dash-fx-caret";
  style.textContent = `@keyframes dash-caret-blink { 0%, 45% { opacity: 1; } 50%, 95% { opacity: 0.15; } 100% { opacity: 1; } }`;
  document.head.appendChild(style);
  caretStylesInjected = true;
}

export function StreamingCaret({ color = "var(--dash-accent)" }: { color?: string }) {
  ensureCaretStyles();
  return (
    <span
      aria-hidden
      style={{
        display: "inline-block",
        width: 7,
        height: "1em",
        marginLeft: 2,
        verticalAlign: "text-bottom",
        borderRadius: 1,
        background: color,
        animation: "dash-caret-blink 1s ease-in-out infinite",
      }}
    />
  );
}
