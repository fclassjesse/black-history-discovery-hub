"use client";

import { useLayoutEffect, useRef } from "react";
import { CharacterSlot } from "@/components/character/CharacterSlot";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";

export type DockLayout = "stage" | "guide";

/** How far the ask bubble may overlap her portrait: just the patterned hem of her top. */
const BUBBLE_OVERLAP_PX = 28;
/** Stage ⇄ dock flight duration. */
const FLIGHT_MS = 1000;

/**
 * One persistent home for Nova. On the stage she stands over an anchor element
 * (`[data-character-anchor]`, absolute within the explorer); in results mode she
 * docks beside the drawer (fixed). Layout changes are FLIP-animated so she
 * visibly walks from one to the other instead of popping.
 */
export function CharacterDock({ layout }: { layout: DockLayout }) {
  const ref = useRef<HTMLDivElement>(null);
  const lastRect = useRef<DOMRect | null>(null);
  const prevLayoutRef = useRef<DockLayout | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const root = el.parentElement as HTMLElement;

    const place = () => {
      if (layout !== "stage") {
        // only the stage placement is cleared; a flight's inline transform/transition must survive re-runs
        for (const prop of ["left", "top", "width", "height"]) el.style.removeProperty(prop);
        el.style.removeProperty("--nova-lift");
        el.style.removeProperty("--nova-col-right");
        return;
      }
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
    // Only a real layout change flies. React may re-run this effect for the same layout (StrictMode in development,
    // a parent re-render); that must neither restart nor cancel a flight in progress.
    const changed = prevLayoutRef.current !== layout;
    prevLayoutRef.current = layout;
    const last = lastRect.current;
    let next = last;
    if (changed) {
      el.style.transition = "none";
      el.style.transform = "";
      next = el.getBoundingClientRect();
      lastRect.current = next;
    }

    let endFlight = () => {};
    if (changed && last && next && next.width > 0 && !prefersReducedMotion()) {
      // The flight is a CSS transition, not a GSAP tween: it runs on the compositor thread, so the main-thread work
      // that lands at the same moment (results drawer mounting, pins, the search response) cannot freeze her
      // mid-air. The scale is uniform, anchored at her feet: the old box and the new one have different proportions
      // (full figure vs bust), and a per-axis FLIP stretched her face ~30% at take-off.
      ensureGsap().killTweensOf(el);
      const scale = last.width / next.width;
      const dx = last.left + last.width / 2 - (next.left + next.width / 2);
      const dy = last.bottom - next.bottom;
      el.style.transition = "none";
      el.style.transformOrigin = "50% 100%";
      el.style.willChange = "transform";
      el.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`;
      void el.getBoundingClientRect(); // commit the start pose before the transition is armed
      el.style.transition = `transform ${FLIGHT_MS}ms cubic-bezier(0.65, 0, 0.35, 1)`;
      el.style.transform = "translate(0px, 0px) scale(1)";
      const done = () => { el.style.transition = ""; el.style.transform = ""; el.style.willChange = ""; el.style.transformOrigin = ""; };
      // her eyes and head transition too and those events bubble up here: only the dock's own transform counts
      const onEnd = (e: TransitionEvent) => { if (e.target === el && e.propertyName === "transform") { el.removeEventListener("transitionend", onEnd); done(); } };
      el.addEventListener("transitionend", onEnd);
      const fallback = window.setTimeout(() => { el.removeEventListener("transitionend", onEnd); done(); }, FLIGHT_MS + 100);
      // the cleanup only drops the timer and listener: the flight itself keeps running on the compositor
      endFlight = () => { window.clearTimeout(fallback); el.removeEventListener("transitionend", onEnd); };
    } else if (changed) {
      el.style.transition = "";
    }

    const ro = new ResizeObserver(() => { place(); if (!el.style.transform) lastRect.current = el.getBoundingClientRect(); });
    ro.observe(document.documentElement);
    const anchor = document.querySelector<HTMLElement>("[data-character-anchor]");
    if (anchor) ro.observe(anchor);
    return () => { ro.disconnect(); endFlight(); };
  }, [layout]);

  return (
    <div ref={ref} className="character-dock" data-layout={layout} aria-hidden>
      <CharacterSlot size={layout === "stage" ? "hero" : "guide"} />
    </div>
  );
}
