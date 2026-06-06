import { useEffect, useRef, useState } from "react";

/**
 * Smoothly animates progress toward server-reported values so the bar
 * never appears frozen during long Firecrawl / Groq API calls.
 */
export function useSmoothProgress(target: number, active: boolean): number {
  const [display, setDisplay] = useState(target);
  const targetRef = useRef(target);
  targetRef.current = target;

  // Jump up immediately when server sends a higher value
  useEffect(() => {
    setDisplay((d) => (target > d ? target : d));
  }, [target]);

  // Creep forward slowly while waiting for next server update
  useEffect(() => {
    if (!active) {
      setDisplay(target);
      return;
    }
    const id = window.setInterval(() => {
      setDisplay((d) => {
        const t = targetRef.current;
        // Catch up to server
        if (d < t - 0.3) return Math.min(d + 1.2, t);
        // Gentle creep during long API waits (step 2 range 20–71)
        if (d >= 20 && d < 71 && d <= t + 2) {
          return Math.min(d + 0.25, 71, t + 2);
        }
        return d;
      });
    }, 900);
    return () => window.clearInterval(id);
  }, [active, target]);

  return Math.min(99, Math.round(display * 10) / 10);
}
