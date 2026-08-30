import { useEffect, useRef, useState } from "react";

export function usePerformanceMonitor() {
  const [fps, setFps] = useState(60);
  const frameCount = useRef(0);
  const lastTime = useRef(performance.now());
  const fpsInterval = useRef(1000);
  const animationFrameId = useRef<number>(0);

  useEffect(() => {
    const loop = (timestamp: number) => {
      frameCount.current++;
      const elapsed = timestamp - lastTime.current;

      if (elapsed >= fpsInterval.current) {
        const currentFps = Math.round((frameCount.current * 1000) / elapsed);
        setFps(currentFps);
        frameCount.current = 0;
        lastTime.current = timestamp;
      }

      animationFrameId.current = requestAnimationFrame(loop);
    };

    animationFrameId.current = requestAnimationFrame(loop);

    return () => {
      if (animationFrameId.current) {
        cancelAnimationFrame(animationFrameId.current);
      }
    };
  }, []);

  return fps;
}

export function useGPUAcceleration() {
  useEffect(() => {
    // Enable GPU hints for animations
    const style = document.createElement("style");
    style.textContent = `
      * {
        will-change: transform, opacity;
        backface-visibility: hidden;
        -webkit-backface-visibility: hidden;
        perspective: 1000px;
        -webkit-perspective: 1000px;
      }
    `;
    document.head.appendChild(style);

    return () => {
      document.head.removeChild(style);
    };
  }, []);
}

export function useThrottle(callback: (...args: any[]) => void, delay: number) {
  const lastCall = useRef(0);

  return (...args: any[]) => {
    const now = Date.now();
    if (now - lastCall.current >= delay) {
      lastCall.current = now;
      callback(...args);
    }
  };
}

export function useDebounce(callback: (...args: any[]) => void, delay: number) {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  return (...args: any[]) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      callback(...args);
    }, delay);
  };
}
