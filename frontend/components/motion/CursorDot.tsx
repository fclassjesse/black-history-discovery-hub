"use client";

import { useEffect, useRef } from "react";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";

/** A playful trailing dot. The native cursor stays visible; this only adds personality. */
export function CursorDot() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || window.matchMedia("(pointer: coarse)").matches) return;
    const gsap = ensureGsap();
    const x = gsap.quickTo(el, "x", { duration: 0.35, ease: "power3.out" });
    const y = gsap.quickTo(el, "y", { duration: 0.35, ease: "power3.out" });
    const move = (e: PointerEvent) => {
      x(e.clientX); y(e.clientY);
      el.dataset.hidden = "false";
      const t = e.target as HTMLElement | null;
      el.dataset.hover = t?.closest("a, button, [role=button], input, select, textarea, label, [data-cursor]") ? "true" : "false";
    };
    const leave = () => { el.dataset.hidden = "true"; };
    window.addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    return () => { window.removeEventListener("pointermove", move); document.documentElement.removeEventListener("pointerleave", leave); };
  }, []);
  return <div ref={ref} className="cursor-dot" data-hidden="true" aria-hidden />;
}
