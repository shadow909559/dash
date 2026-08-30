import { useEffect, useState } from "react";
import { useAIStore, type AICoreStatus } from "@/stores/aiStore";
import { DASH_COLORS, DASH_ANIMATIONS } from "@/stores/dashState";
import "./JarvisHUD.css";

// Helper to ensure numbers are finite and valid for SVG
const safeNumber = (value: number, fallback: number = 0): number => {
  return Number.isFinite(value) ? value : fallback;
};

// Helper to generate valid SVG rotate transform
const svgRotate = (angle: number, cx: number, cy: number): string => {
  const safeAngle = safeNumber(angle, 0);
  const safeCx = safeNumber(cx, 0);
  const safeCy = safeNumber(cy, 0);
  return `rotate(${safeAngle} ${safeCx} ${safeCy})`;
};

// Helper to generate valid SVG translate transform
const svgTranslate = (x: number, y: number): string => {
  const safeX = safeNumber(x, 0);
  const safeY = safeNumber(y, 0);
  return `translate(${safeX} ${safeY})`;
};

// Helper to generate valid SVG scale transform
const svgScale = (scale: number): string => {
  const safeScale = safeNumber(scale, 1);
  return `scale(${safeScale})`;
};

// Helper to generate circular path data
const describeArc = (x: number, y: number, radius: number, startAngle: number, endAngle: number) => {
  const safeX = safeNumber(x, 0);
  const safeY = safeNumber(y, 0);
  const safeRadius = safeNumber(radius, 0);
  const safeStartAngle = safeNumber(startAngle, 0);
  const safeEndAngle = safeNumber(endAngle, 0);
  
  const start = {
    x: safeX + safeRadius * Math.cos((safeStartAngle * Math.PI) / 180),
    y: safeY + safeRadius * Math.sin((safeStartAngle * Math.PI) / 180),
  };
  const end = {
    x: safeX + safeRadius * Math.cos((safeEndAngle * Math.PI) / 180),
    y: safeY + safeRadius * Math.sin((safeEndAngle * Math.PI) / 180),
  };
  const largeArcFlag = safeEndAngle - safeStartAngle <= 180 ? "0" : "1";
  return `M ${safeNumber(start.x)} ${safeNumber(start.y)} A ${safeRadius} ${safeRadius} 0 ${largeArcFlag} 1 ${safeNumber(end.x)} ${safeNumber(end.y)}`;
};

const coreStatusToText: Record<AICoreStatus, string> = {
  idle: "READY",
  listening: "LISTENING",
  thinking: "THINKING",
  speaking: "SPEAKING",
  executing: "EXECUTING",
  error: "ERROR",
  provider_checking: "CHECKING",
  provider_starting: "STARTING",
  provider_unavailable: "OFFLINE"
};

export default function JarvisHUD() {
  const { coreStatus, dashState, chatStatus, aiProviderStatus, voiceStatus } = useAIStore();
  const [amplitude, setAmplitude] = useState(0);
  const [pulsePhase, setPulsePhase] = useState(0);

  useEffect(() => {
    const handleMicAmplitude = (e: any) => setAmplitude(e.detail);
    window.addEventListener('micamplitude', handleMicAmplitude);
    return () => window.removeEventListener('micamplitude', handleMicAmplitude);
  }, []);

  // Performance: Use requestAnimationFrame for smooth animations
  useEffect(() => {
    let animationFrameId: number;
    let lastTime = performance.now();

    const animate = (currentTime: number) => {
      const deltaTime = currentTime - lastTime;
      
      // Throttle updates to 60fps max
      if (deltaTime >= 16.67) {
        setPulsePhase(prev => (prev + 0.05) % (Math.PI * 2));
        lastTime = currentTime;
      }
      
      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);
    
    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  const stateClass = `hud--${coreStatus}`;
  const dashColor = DASH_COLORS[dashState];
  const dashAnim = DASH_ANIMATIONS[dashState];
  const coreScale = 1 + amplitude * 0.3 + Math.sin(pulsePhase) * 0.05 * dashAnim.intensity;
  const statusColor = coreStatus === "error" ? "#ff4444" : dashColor.primary;
  const accentColor = dashColor.accent;
  const glowIntensity = dashColor.glow;

  return (
    <div className={`hud-container ${stateClass}`}>
      <svg className="hud-svg" viewBox="0 0 400 400">
        <defs>
          <filter id="hud-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation={2 + glowIntensity * 3} result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="core-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation={4 + glowIntensity * 5} result="coreBlur" />
            <feMerge>
              <feMergeNode in="coreBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <radialGradient id="core-gradient">
            <stop offset="0%" stopColor={statusColor} stopOpacity={0.3} />
            <stop offset="40%" stopColor="rgba(0, 20, 40, 0.9)" />
            <stop offset="70%" stopColor="rgba(0, 10, 30, 0.8)" />
            <stop offset="100%" stopColor="rgba(0, 5, 20, 0.6)" />
          </radialGradient>
          <radialGradient id="ring-gradient">
            <stop offset="0%" stopColor={accentColor} stopOpacity={0.4} />
            <stop offset="100%" stopColor={statusColor} stopOpacity={0.1} />
          </radialGradient>
        </defs>

        {/* Animated Background Pulse */}
        <circle cx="200" cy="200" r="190" fill="none" stroke={statusColor} strokeWidth="0.5" opacity={0.1 + Math.sin(pulsePhase) * 0.05} />

        {/* Rotating Rings - Sci-Fi HUD */}
        <g className="hud-ring-group" filter="url(#hud-glow)">
          {/* Ring 1 (Outer) - Dynamic Ticks */}
          <g className="hud-ring" style={{ animationDuration: `${60 / dashAnim.speed}s` }}>
            <circle cx="200" cy="200" r="185" fill="none" stroke={statusColor} strokeWidth="0.5" opacity={0.15} />
            {Array.from({ length: 72 }).map((_, i) => (
              <line 
                key={i} 
                x1="200" y1="15" x2="200" y2="18" 
                stroke={accentColor} 
                strokeWidth="0.5" 
                opacity={i % 6 === 0 ? 0.6 : 0.3}
                transform={svgRotate(i * 5, 200, 200)} 
              />
            ))}
          </g>

          {/* Ring 2 - Segmented Arc with Status Color */}
          <g className="hud-ring" style={{ animationDuration: `${45 / dashAnim.speed}s`, animationDirection: "reverse" }}>
            <path d={describeArc(200, 200, 170, 0, 180)} fill="none" stroke={statusColor} strokeWidth="2" opacity={0.3} />
            <path d={describeArc(200, 200, 170, 185, 195)} fill="none" stroke={accentColor} strokeWidth="3" />
            <path d={describeArc(200, 200, 170, 200, 360)} fill="none" stroke={statusColor} strokeWidth="2" opacity={0.3} />
          </g>

          {/* Ring 3 - Inner Segments - Dynamic */}
          <g className="hud-ring" style={{ animationDuration: `${30 / dashAnim.speed}s` }}>
            <circle cx="200" cy="200" r="145" fill="none" stroke={statusColor} strokeWidth="0.5" opacity={0.1} />
            {Array.from({ length: 12 }).map((_, i) => (
              <path 
                key={i} 
                d={describeArc(200, 200, 145, i * 30 + 2, i * 30 + 18)} 
                fill="none" 
                stroke={accentColor} 
                strokeWidth="1" 
                opacity={0.5 + Math.sin(pulsePhase + i) * 0.2}
              />
            ))}
          </g>

          {/* Ring 4 - Status Indicator Ring - Animated Dash */}
          <g className="hud-ring" style={{ animationDuration: `${25 / dashAnim.speed}s`, animationDirection: "reverse" }}>
             <circle 
               cx="200" cy="200" r="115" 
               fill="none" 
               stroke={statusColor} 
               strokeWidth="2" 
               opacity={0.6} 
               strokeDasharray="10 5"
               style={{ animation: `dashRotate ${10 / dashAnim.speed}s linear infinite` }}
             />
          </g>

          {/* Ring 5 - Micro-ticks - Gold Accent */}
          <g className="hud-ring" style={{ animationDuration: `${80 / dashAnim.speed}s` }}>
             {Array.from({ length: 180 }).map((_, i) => (
              <line
                key={i}
                x1="200" y1="80" x2="200" y2="82"
                stroke={i % 10 === 0 ? accentColor : statusColor}
                strokeWidth="0.3"
                opacity={i % 10 === 0 ? 0.4 : 0.2}
                transform={svgRotate(i * 2, 200, 200)}
              />
            ))}
          </g>
        </g>

        {/* Static Core Elements - Stable Center */}
        <g className="hud-core" style={{ transform: svgScale(coreScale), transformOrigin: 'center' }} filter="url(#core-glow)">
          <circle cx="200" cy="200" r="55" fill="url(#core-gradient)" />
          <circle cx="200" cy="200" r="58" fill="none" stroke={statusColor} strokeWidth="1.5" opacity={0.6} />
          <circle cx="200" cy="200" r="52" fill="none" stroke={accentColor} strokeWidth="0.5" opacity={0.3} />
          
          {/* Inner pulsing ring */}
          <circle 
            cx="200" cy="200" r="45" 
            fill="none" 
            stroke={statusColor} 
            strokeWidth="1" 
            opacity={0.4 + Math.sin(pulsePhase * 2) * 0.2}
          />
          
          <text x="200" y="205" className="hud-center-text" style={{ fill: statusColor }}>DASH</text>
          <text x="200" y="225" className="hud-center-subtext" style={{ fill: accentColor }}>{coreStatus.toUpperCase()}</text>
        </g>

        {/* Animation styles */}
        <style>{`
          @keyframes dashRotate {
            from { stroke-dashoffset: 0; }
            to { stroke-dashoffset: -30; }
          }
        `}</style>
      </svg>
    </div>
  );
}