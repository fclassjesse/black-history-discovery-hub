"use client";

import { useEffect, useRef, type RefObject } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

let registered = false;
export function ensureGsap() {
  if (registered || typeof window === "undefined") return gsap;
  gsap.registerPlugin(ScrollTrigger);
  registered = true;
  return gsap;
}

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export type RevealVariant = "rise" | "words" | "scale" | "wipe" | "chars";

interface RevealOptions {
  variant?: RevealVariant;
  delay?: number;
  stagger?: number;
  start?: string;
  once?: boolean;
}

/** Scroll-triggered reveal. `data-reveal-child` elements inside the ref are staggered. */
export function useReveal<T extends HTMLElement>(options: RevealOptions = {}): RefObject<T | null> {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;
    const g = ensureGsap();
    const { variant = "rise", delay = 0, stagger = 0.08, start = "top 85%", once = true } = options;
    const children = Array.from(el.querySelectorAll<HTMLElement>("[data-reveal-child]"));
    const targets = children.length > 0 ? children : [el];
    const ctx = g.context(() => {
      const from: gsap.TweenVars =
        variant === "scale" ? { scale: 0.85, opacity: 0, rotate: -3 }
        : variant === "wipe" ? { clipPath: "inset(0 100% 0 0)" }
        : variant === "words" || variant === "chars" ? { yPercent: 110, rotateX: -40, opacity: 0 }
        : { y: 36, opacity: 0 };
      g.from(targets, {
        ...from,
        duration: variant === "wipe" ? 1 : 0.9,
        ease: variant === "scale" ? "back.out(1.6)" : "power3.out",
        stagger,
        delay,
        scrollTrigger: { trigger: el, start, once, toggleActions: once ? "play none none none" : "play none none reverse" },
      });
    }, el);
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return ref;
}

/** Parallax: elements with data-speed move relative to scroll. speed 0.5 = half speed (lags), -0.3 = moves up faster. */
export function useParallax<T extends HTMLElement>(): RefObject<T | null> {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;
    const g = ensureGsap();
    const items = Array.from(el.querySelectorAll<HTMLElement>("[data-speed]"));
    const ctx = g.context(() => {
      items.forEach((item) => {
        const speed = Number(item.dataset.speed ?? "0.3");
        g.to(item, { y: () => speed * -220, ease: "none", scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: 0.6 } });
      });
    }, el);
    return () => ctx.revert();
  }, []);
  return ref;
}

/** Cursor tilt in 3D. maxDeg controls the rotation; the element should have `.tilt`. */
export function useTilt<T extends HTMLElement>(maxDeg = 6, perspective = 1200): RefObject<T | null> {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || window.matchMedia("(pointer: coarse)").matches) return;
    const g = ensureGsap();
    g.set(el, { transformPerspective: perspective });
    const rx = g.quickTo(el, "rotationX", { duration: 0.6, ease: "power3.out" });
    const ry = g.quickTo(el, "rotationY", { duration: 0.6, ease: "power3.out" });
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      ry(px * maxDeg * 2);
      rx(-py * maxDeg * 2);
    };
    const onLeave = () => { rx(0); ry(0); };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerleave", onLeave);
    return () => { el.removeEventListener("pointermove", onMove); el.removeEventListener("pointerleave", onLeave); };
  }, [maxDeg, perspective]);
  return ref;
}

/** Magnetic button: the element drifts toward the cursor within its bounds. */
export function useMagnetic<T extends HTMLElement>(strength = 0.35): RefObject<T | null> {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || window.matchMedia("(pointer: coarse)").matches) return;
    const g = ensureGsap();
    const x = g.quickTo(el, "x", { duration: 0.5, ease: "power3.out" });
    const y = g.quickTo(el, "y", { duration: 0.5, ease: "power3.out" });
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      x((e.clientX - (r.left + r.width / 2)) * strength);
      y((e.clientY - (r.top + r.height / 2)) * strength);
    };
    const onLeave = () => { x(0); y(0); };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerleave", onLeave);
    return () => { el.removeEventListener("pointermove", onMove); el.removeEventListener("pointerleave", onLeave); };
  }, [strength]);
  return ref;
}

/** Split a string into word spans for staggered reveals (keeps the text accessible as a whole). */
export function SplitWords({ text, className }: { text: string; className?: string }) {
  return (
    <span aria-label={text} role="text" className={className}>
      {text.split(" ").map((w, i) => (
        <span key={i} aria-hidden className="inline-block overflow-hidden align-bottom pb-[0.08em] -mb-[0.08em]">
          <span data-reveal-child className="inline-block will-change-transform">{w}&nbsp;</span>
        </span>
      ))}
    </span>
  );
}
