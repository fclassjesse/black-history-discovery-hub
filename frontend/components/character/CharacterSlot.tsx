"use client";

import { useEffect, useRef, useState } from "react";
import { character, type CharacterMeta, type CharacterRig, type CharacterState } from "@/lib/character";
import { Nova, type NovaFraming } from "@/components/character/Nova";

type SlotSize = "hero" | "guide" | "mini";

/** How often Nova fidgets (a small wave) on the stage while nobody is talking to her. */
const FIDGET_MIN_MS = 16000;
const FIDGET_JITTER_MS = 12000;
/** Pointer within this many px of her slot counts as "near": she perks up, and waves once (throttled). */
const NEAR_PX = 40;
const NEAR_WAVE_COOLDOWN_MS = 9000;
/** With the pointer resting, her eyes wander every few seconds. */
const SACCADE_AFTER_MS = 3200;
const SACCADE_MIN_MS = 1800;
const SACCADE_JITTER_MS = 2600;

/**
 * The stage where the guide lives. Nova (components/character/Nova.tsx) is the
 * default rig; an external rig registered through lib/character.ts replaces her.
 * On the stage she is shown head to toe; the small docks (results drawer, app
 * header) frame her as a bust rising from the bottom edge.
 */
export function CharacterSlot({ size = "hero", framing: framingProp, className = "" }: { size?: SlotSize; framing?: NovaFraming; className?: string }) {
  const framing: NovaFraming = framingProp ?? (size === "hero" ? "full" : "bust");
  const mountRef = useRef<HTMLDivElement>(null);
  const [rig, setRig] = useState<CharacterRig | null>(null);
  const [state, setState] = useState<CharacterState>("idle");
  const [meta, setMeta] = useState<CharacterMeta | undefined>(undefined);
  const [gaze, setGaze] = useState({ x: 0, y: 0 });
  const [near, setNear] = useState(false);
  const stateRef = useRef<CharacterState>("idle");
  const lastMoveRef = useRef(0);
  const lastWaveRef = useRef(0);

  useEffect(() => character.onRig(setRig), []);
  useEffect(() => character.subscribe((s, m) => { stateRef.current = s; setState(s); setMeta(m); }), []);

  // mount the external rig
  useEffect(() => {
    const el = mountRef.current;
    if (!rig || !el) return;
    const cleanup = rig.mount(el, { size });
    return () => { if (typeof cleanup === "function") cleanup(); el.replaceChildren(); };
  }, [rig, size]);

  // gaze follows the cursor (normalised to the slot centre)
  useEffect(() => {
    const el = mountRef.current?.parentElement;
    if (!el || window.matchMedia("(pointer: coarse)").matches) return;
    let raf = 0;
    const onMove = (e: PointerEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const nx = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (window.innerWidth / 2)));
        const ny = Math.max(-1, Math.min(1, (e.clientY - (r.top + r.height / 2)) / (window.innerHeight / 2)));
        lastMoveRef.current = performance.now();
        setGaze({ x: nx, y: ny });
        character.lookAt(nx, ny);
        const isNear = e.clientX > r.left - NEAR_PX && e.clientX < r.right + NEAR_PX && e.clientY > r.top - NEAR_PX && e.clientY < r.bottom + NEAR_PX;
        setNear(isNear);
        if (isNear && stateRef.current === "idle" && performance.now() - lastWaveRef.current > NEAR_WAVE_COOLDOWN_MS) {
          lastWaveRef.current = performance.now();
          character.set("celebrate", undefined, 1300);
        }
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => { window.removeEventListener("pointermove", onMove); cancelAnimationFrame(raf); };
  }, []);

  // when the pointer rests, her eyes wander a little
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      timer = setTimeout(() => {
        if (document.visibilityState === "visible" && performance.now() - lastMoveRef.current > SACCADE_AFTER_MS && (stateRef.current === "idle" || stateRef.current === "listening")) {
          setGaze({ x: (Math.random() - 0.5) * 1.2, y: (Math.random() - 0.5) * 0.8 });
        }
        schedule();
      }, SACCADE_MIN_MS + Math.random() * SACCADE_JITTER_MS);
    };
    schedule();
    return () => clearTimeout(timer);
  }, []);

  // on the stage she fidgets now and then, only when idle and the tab is visible
  useEffect(() => {
    if (size !== "hero" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      timer = setTimeout(() => {
        if (document.visibilityState === "visible" && stateRef.current === "idle") character.set("celebrate", undefined, 1400);
        schedule();
      }, FIDGET_MIN_MS + Math.random() * FIDGET_JITTER_MS);
    };
    schedule();
    return () => clearTimeout(timer);
  }, [size]);

  return (
    <div className={`character-slot h-full w-full ${className}`} data-character-slot data-character-state={state} data-size={size} data-framing={framing} data-near={near} aria-hidden>
      <div ref={mountRef} className="absolute inset-0" data-character-mount />
      {!rig && <Nova state={state} meta={meta} gaze={gaze} framing={framing} near={near} />}
    </div>
  );
}
