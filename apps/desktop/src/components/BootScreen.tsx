import { useEffect, useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./BootScreen.css";

interface BootScreenProps {
  onComplete: () => void;
  duration?: number;
}

/** Generate particle positions once */
function makeParticles(n: number) {
  return Array.from({ length: n }, (_, i) => {
    const angle = (i / n) * Math.PI * 2 + Math.random() * 0.4;
    const r = 120 + Math.random() * 80;
    return {
      id: i,
      x: Math.cos(angle) * r,
      y: Math.sin(angle) * r,
      size: 1 + Math.random() * 2.5,
      base: 0.3 + Math.random() * 0.5,
      dur: 2 + Math.random() * 2,
      delay: Math.random() * 3,
    };
  });
}

/** Dock icon SVGs — minimal outlines */
const ICONS = [
  /* power */ <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="6" x2="12" y2="12"/></svg>,
  /* chat  */ <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>,
  /* play  */ <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  /* grid  */ <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>,
  /* music */ <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>,
  /* doc   */ <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>,
];

export default function BootScreen({ onComplete, duration = 4000 }: BootScreenProps) {
  const [visible, setVisible] = useState(true);
  const particles = useMemo(() => makeParticles(10), []);

  const finish = useCallback(() => {
    setVisible(false);
    setTimeout(onComplete, 450);
  }, [onComplete]);

  useEffect(() => {
    const t = setTimeout(finish, duration);
    return () => clearTimeout(t);
  }, [duration, finish]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="dash-boot"
          key="boot"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        >
          {/* Grid */}
          <div className="dash-boot__grid" />

          {/* Badge anchor */}
          <div className="dash-boot__badge">
            {/* Glow halo */}
            <motion.div
              className="dash-boot__glow"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            />

            {/* Main ring */}
            <motion.div
              className="dash-boot__ring"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.3, ease: [0.34, 1.56, 0.64, 1] }}
            />

            {/* DASH text */}
            <motion.div
              className="dash-boot__text"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.7 }}
            >
              DASH
            </motion.div>

            {/* Accent arc */}
            <div className="dash-boot__accent-orbit">
              <div className="dash-boot__accent-arc" />
            </div>

            {/* Tick marks */}
            <div className="dash-boot__ticks-orbit">
              <span className="dash-boot__tick dash-boot__tick--left">//</span>
              <span className="dash-boot__tick dash-boot__tick--right">//</span>
            </div>

            {/* Particles */}
            {particles.map((p) => (
              <div
                key={p.id}
                className="dash-boot__particle"
                style={
                  {
                    width: p.size,
                    height: p.size,
                    left: `calc(50% + ${p.x}px)`,
                    top: `calc(50% + ${p.y}px)`,
                    "--p-base": p.base,
                    animationDelay: `${p.delay}s`,
                    animationDuration: `${p.dur}s`,
                  } as React.CSSProperties
                }
              />
            ))}
          </div>

          {/* Dock */}
          <motion.div
            className="dash-boot__dock"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 1.0 }}
          >
            {ICONS.map((icon, i) => (
              <span key={i} className="dash-boot__dock-icon-wrap">
                {i > 0 && <span className="dash-boot__dock-divider" />}
                <span className="dash-boot__dock-icon">{icon}</span>
              </span>
            ))}
          </motion.div>

          {/* Pagination */}
          <motion.div
            className="dash-boot__pagination"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 1.1 }}
          >
            <span className="dash-boot__dot dash-boot__dot--active" />
            <span className="dash-boot__dot dash-boot__dot--inactive" />
            <span className="dash-boot__dot dash-boot__dot--inactive" />
            <span className="dash-boot__dot dash-boot__dot--inactive" />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
