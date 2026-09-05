import { useEffect, useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./BootScreen.css";

interface BootScreenProps {
  onComplete: () => void;
  duration?: number;
}

/* ── Particle generator ────────────────────────────────────────────
   Spec: 10 particles, 1-3px, opacity 30-80%, radii 120-200px
   Twinkle on 2-4s randomized cycles, drift a few px
   ──────────────────────────────────────────────────────────────── */
function makeParticles(n: number) {
  return Array.from({ length: n }, (_, i) => {
    const angle = (i / n) * Math.PI * 2 + Math.random() * 0.3;
    const r = 120 + Math.random() * 80; // 120-200px
    return {
      id: i,
      x: Math.cos(angle) * r,
      y: Math.sin(angle) * r,
      size: 1 + Math.random() * 2, // 1-3px
      base: 0.3 + Math.random() * 0.5, // 0.3-0.8 opacity
      dur: 2 + Math.random() * 2, // 2-4s twinkle
      delay: Math.random() * 3,
      dx: -3 + Math.random() * 6, // drift ±3px
      dy: -3 + Math.random() * 6,
    };
  });
}

/* ── Dock icons — minimal white outlines ──────────────────────────
   Spec: power/status, chat, play/media, grid/apps, music, doc/notes
   ──────────────────────────────────────────────────────────────── */
const DOCK_ICONS = [
  /* power / status ring */
  <svg key="power" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="6" x2="12" y2="12" />
  </svg>,
  /* chat bubble */
  <svg key="chat" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
  </svg>,
  /* play / media */
  <svg key="play" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>,
  /* grid / apps */
  <svg key="grid" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
  </svg>,
  /* music note */
  <svg key="music" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
    <path d="M9 18V5l12-2v13" />
    <circle cx="6" cy="18" r="3" />
    <circle cx="18" cy="16" r="3" />
  </svg>,
  /* document / notes */
  <svg key="doc" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
  </svg>,
];

export default function BootScreen({ onComplete, duration = 5000 }: BootScreenProps) {
  const [visible, setVisible] = useState(true);
  const particles = useMemo(() => makeParticles(10), []);

  const finish = useCallback(() => {
    setVisible(false);
    setTimeout(onComplete, 400); // 300-400ms exit fade
  }, [onComplete]);

  useEffect(() => {
    const t = setTimeout(finish, duration);
    return () => clearTimeout(t);
  }, [duration, finish]);

  /*
   * Spec sequence:
   * 1. Screen fades from black — 300ms (framer: initial→animate)
   * 2. Grid fades in — 200ms delay (CSS: 0.1s delay, 0.4s duration)
   * 3. Badge scales 90%→100% spring ~500ms + glow fades in (framer: 0.3s delay)
   * 4. Text flickers in ~400ms after ring appears (framer: 0.7s delay)
   * 5. All orbiting elements loop continuously (CSS: always on)
   * 6. Dock + pagination fade in last ~600ms after elements (CSS: 1.2s delay)
   * 7. Hold idle loop, then exit fade 300-400ms
   */

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="dash-boot"
          key="boot"
          /* Step 1: screen fades in from black over 300ms */
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 0.97 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          role="status"
          aria-label="DASH loading"
        >
          {/* Step 2: Grid fades in with slight delay */}
          <div className="dash-boot__grid" />

          {/* Badge anchor at 38% from top */}
          <div className="dash-boot__badge">
            {/* Layer A: Outer glow halo — 280px, pulses 35-55% */}
            <motion.div
              className="dash-boot__glow"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            />

            {/* Layer B: Main ring — 190px, conic-gradient, 4s spin */}
            <motion.div
              className="dash-boot__ring"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              /* Spring overshoot per spec: slight bounce */
              transition={{ duration: 0.5, delay: 0.3, ease: [0.34, 1.56, 0.64, 1] }}
            >
              <div className="dash-boot__ring-glow" />
              <div className="dash-boot__ring-stroke" />
              <div className="dash-boot__ring-center" />
            </motion.div>

            {/* Layer C: "DASH" text — flickers in ~400ms after ring */}
            <motion.div
              className="dash-boot__text"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.7 }}
            >
              DASH
            </motion.div>

            {/* Layer D: Orbiting accent arc — 250px diameter, 9s orbit, breathing */}
            <div className="dash-boot__accent-orbit">
              <div className="dash-boot__accent-arc" />
              <div className="dash-boot__accent-arc-2" />
            </div>

            {/* Layer E: Tick marks // — orbit 12s reverse */}
            <div className="dash-boot__ticks-orbit">
              <span className="dash-boot__tick dash-boot__tick--left">//</span>
              <span className="dash-boot__tick dash-boot__tick--right">//</span>
            </div>

            {/* Layer F: Particles — 10 dots, 1-3px, twinkle 2-4s */}
            {particles.map((p) => (
              <div
                key={p.id}
                className={
                  "dash-boot__particle" +
                  /* One particle is the shooting star — id 3 */
                  (p.id === 3 ? " dash-boot__particle--shooter" : "")
                }
                style={{
                  width: p.size,
                  height: p.size,
                  left: `calc(50% + ${p.x}px)`,
                  top: `calc(50% + ${p.y}px)`,
                  "--p-base": p.base,
                  "--p-dx": `${p.dx}px`,
                  "--p-dy": `${p.dy}px`,
                  animationDelay: `${p.delay}s`,
                  animationDuration: `${p.dur}s`,
                } as React.CSSProperties}
              />
            ))}
          </div>

          {/* Layer G: Bottom dock — 6 icons, 20px, ~14px spacing */}
          <div className="dash-boot__dock">
            {DOCK_ICONS.map((icon, i) => (
              <span key={i} className="dash-boot__dock-item">
                {i > 0 && <span className="dash-boot__dock-sep" />}
                <span className="dash-boot__dock-icon">{icon}</span>
              </span>
            ))}
          </div>

          {/* Layer H: Pagination dots — decorative */}
          <div className="dash-boot__pagination">
            <span className="dash-boot__dot dash-boot__dot--active" />
            <span className="dash-boot__dot dash-boot__dot--inactive" />
            <span className="dash-boot__dot dash-boot__dot--inactive" />
            <span className="dash-boot__dot dash-boot__dot--inactive" />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
