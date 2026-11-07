"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";

/** Page transition: a vermilion wipe peels upward to reveal each new page. Re-mounts per navigation. */
export default function Template({ children }: { children: ReactNode }) {
  const wipeRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const wipe = wipeRef.current;
    const content = contentRef.current;
    if (!wipe || !content) return;
    if (prefersReducedMotion()) { wipe.style.display = "none"; return; }
    const gsap = ensureGsap();
    const tl = gsap.timeline({ onComplete: () => { wipe.style.display = "none"; gsap.set(content, { clearProps: "transform,opacity" }); } });
    tl.set(wipe, { display: "block", scaleY: 1, transformOrigin: "50% 0%" })
      .fromTo(content, { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7, ease: "power3.out" }, 0.05)
      .to(wipe, { scaleY: 0, duration: 0.75, ease: "power4.inOut" }, 0);
    return () => { tl.kill(); };
  }, []);
  return (
    <>
      <div ref={wipeRef} className="wipe" style={{ display: "none" }} aria-hidden />
      <div ref={contentRef}>{children}</div>
    </>
  );
}
