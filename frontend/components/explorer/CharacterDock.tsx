"use client";

import { useLayoutEffect, useRef } from "react";
import { CharacterSlot } from "@/components/character/CharacterSlot";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";

export type DockLayout = "stage" | "guide";

/** How far the ask bubble may overlap her portrait: just the patterned hem of her top. */
const BUBBLE_OVERLAP_PX = 28;

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
      // place her so the ask bubble only covers the bottom of her top, whatever the screen size.
      // offsetTop (not getBoundingClientRect) so the bubble's entrance animation doesn't skew it.
      const bubble = document.querySelector<HTMLElement>("[data-stage-bubble]");
      if (bubble && bubble.offsetParent === anchor.offsetParent) {
        const lift = anchor.offsetTop + anchor.offsetHeight - bubble.offsetTop - BUBBLE_OVERLAP_PX;
        el.style.setProperty("--nova-lift", `${lift}px`); // negative = the bubble sits lower: she drops to meet it
        // her speech bubble may extend right only as far as the ask bubble does (the left column), never over the globe
        el.style.setProperty("--nova-col-right", `${bubble.offsetLeft + bubble.offsetWidth - anchor.offsetLeft}px`);
      }
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
