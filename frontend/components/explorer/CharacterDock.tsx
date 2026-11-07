"use client";

import { useLayoutEffect, useRef } from "react";
import { CharacterSlot } from "@/components/character/CharacterSlot";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";

export type DockLayout = "stage" | "guide";

/**
 * One persistent home for Nova. On the stage she stands over an anchor element
 * (`[data-character-anchor]`, absolute within the explorer); in results mode she
 * docks beside the drawer (fixed). Layout changes are FLIP-animated so she
 * visibly walks from one to the other instead of popping.
 */
export function CharacterDock({ layout }: { layout: DockLayout }) {
  const ref = useRef<HTMLDivElement>(null);
  const lastRect = useRef<DOMRect | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const root = el.parentElement as HTMLElement;

    const place = () => {
      if (layout !== "stage") { el.removeAttribute("style"); return; }
      const anchor = document.querySelector<HTMLElement>("[data-character-anchor]");
      if (!anchor) return;
      const a = anchor.getBoundingClientRect();
      const r = root.getBoundingClientRect();
      el.style.left = `${a.left - r.left}px`;
      el.style.top = `${a.top - r.top}px`;
      el.style.width = `${a.width}px`;
      el.style.height = `${a.height}px`;
    };

    el.dataset.layout = layout;
    place();
    const next = el.getBoundingClientRect();
    const last = lastRect.current;
    lastRect.current = next;

    if (last && next.width > 0 && !prefersReducedMotion()) {
      const gsap = ensureGsap();
      gsap.killTweensOf(el);
      gsap.fromTo(el,
        { x: last.left - next.left, y: last.top - next.top, scaleX: last.width / next.width, scaleY: last.height / next.height, transformOrigin: "0 0" },
        { x: 0, y: 0, scaleX: 1, scaleY: 1, duration: 1.05, ease: "power3.inOut", clearProps: "transform" });
    }

    const ro = new ResizeObserver(() => { place(); lastRect.current = el.getBoundingClientRect(); });
    ro.observe(document.documentElement);
    const anchor = document.querySelector<HTMLElement>("[data-character-anchor]");
    if (anchor) ro.observe(anchor);
    return () => ro.disconnect();
  }, [layout]);

  return (
    <div ref={ref} className="character-dock" data-layout={layout} aria-hidden>
      <CharacterSlot size={layout === "stage" ? "hero" : "guide"} />
    </div>
  );
}
