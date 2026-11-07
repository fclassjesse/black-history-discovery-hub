"use client";

import { useEffect, type ReactNode } from "react";
import Lenis from "lenis";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/** Lenis smooth scrolling synced with GSAP ScrollTrigger. Disabled for reduced motion. */
export function SmoothScroll({ children }: { children: ReactNode }) {
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const gsap = ensureGsap();
    const lenis = new Lenis({ lerp: 0.11, wheelMultiplier: 0.95, smoothWheel: true });
    const onScroll = () => ScrollTrigger.update();
    lenis.on("scroll", onScroll);
    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return () => { lenis.off("scroll", onScroll); gsap.ticker.remove(tick); lenis.destroy(); };
  }, []);
  return <>{children}</>;
}
