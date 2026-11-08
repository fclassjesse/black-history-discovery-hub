"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import Lenis from "lenis";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/** Lenis smooth scrolling synced with GSAP ScrollTrigger. Disabled for reduced motion. */
export function SmoothScroll({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const lenisRef = useRef<Lenis | null>(null);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const gsap = ensureGsap();
    // <html> is height:100%, so its box never changes while a page loads its data. Lenis must watch <body>, which
    // grows with the content; otherwise it keeps the old scroll limit and the page refuses to scroll after a
    // client-side navigation (seen on institution pages opened from the results drawer).
    const lenis = new Lenis({ lerp: 0.11, wheelMultiplier: 0.95, smoothWheel: true, content: document.body });
    lenisRef.current = lenis;
    const onScroll = () => ScrollTrigger.update();
    lenis.on("scroll", onScroll);
    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return () => { lenis.off("scroll", onScroll); gsap.ticker.remove(tick); lenis.destroy(); lenisRef.current = null; };
  }, []);
  // a new route swaps the whole page: re-measure now instead of waiting for the debounced observer
  useEffect(() => { lenisRef.current?.resize(); }, [pathname]);
  return <>{children}</>;
}
