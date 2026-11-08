"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { CharacterMeta, CharacterState } from "@/lib/character";
import type { NovaFraming } from "@/components/character/Nova";
import { NovaSpeech } from "@/components/character/NovaSpeech";
import { NOVA_RIG_CSS } from "@/components/character/novaRigCss";

/**
 * Layers cut from the designer's painting by frontend/scripts/build_nova_layers.py.
 * Nothing is repainted: the body and head are the painting split at the neck, and the
 * eyes are split into iris / lid-frame / blink-lid so they can move.
 */
const LAYERS = {
  body: "/nova/body.webp",
  head: "/nova/head.webp",
  iris: "/nova/eyes-iris.webp",
  frame: "/nova/eyes-frame.webp",
  lids: "/nova/eyes-lids.webp",
} as const;
/** Every layer is the full canvas, so they all line up with the original by construction. */
const CANVAS = { w: 1039, h: 1200 };
/** From the build script's printout, in % of the canvas: the neck pivot and the top line of the eyes. */
const HEAD_PIVOT = "48.175% 74.102%";
const LID_ORIGIN = "50% 41.326%";

/**
 * Layout and pose transforms are inline, and the keyframe animations ship with the
 * component (novaRigCss.ts): nothing about her depends on globals.css, which the owner's
 * browser has cached stale before.
 */
const FILL: CSSProperties = { position: "absolute", inset: 0, width: "100%", height: "100%", display: "block" };
/**
 * The figure is the largest box with the painting's exact proportions that fits the slot
 * (container units of the root), so the painting can never be squashed or stretched.
 */
const FIGURE: CSSProperties = {
  position: "relative",
  flex: "none",
  height: `min(100cqh, calc(100cqw * ${CANVAS.h} / ${CANVAS.w}))`,
  width: `min(100cqw, calc(100cqh * ${CANVAS.w} / ${CANVAS.h}))`,
};
const HEAD: CSSProperties = { ...FILL, transformOrigin: HEAD_PIVOT };
/** Lids are shut on a blink, half-lowered while thinking or unsure, open otherwise. */
const LID_SCALE: Partial<Record<CharacterState, number>> = { thinking: 0.18, abstain: 0.3 };
const ROOT: CSSProperties = { position: "relative", height: "100%", width: "100%", display: "flex", alignItems: "flex-end", justifyContent: "center", boxSizing: "border-box", containerType: "size" };
/** On the stage the dock measures the ask bubble and lifts her so it only covers the bottom of her top (--nova-lift). */
const STAGE_ROOT: CSSProperties = { ...ROOT, paddingBottom: "max(0px, var(--nova-lift, 0px))" };
/** When the bubble sits below her slot (phones), a negative lift lowers her to meet it. */
const STAGE_DROP: CSSProperties = { marginBottom: "min(0px, var(--nova-lift, 0px))" };

/** How far things move. Iris travel is in % of the canvas (about 18 px / 5.5 px of the painting, as far as her eyes allow); head turn in degrees. */
const IRIS_X_PCT = 1.43;
const IRIS_Y_PCT = 0.37;
/** Eyes chase the cursor quickly; set inline so they move even if a stale stylesheet is cached. */
const IRIS_TRANSITION = "transform 140ms cubic-bezier(0.2, 0.9, 0.3, 1)";
const HEAD_TURN_DEG = 4.5;
/** The cursor rarely reaches the screen edge, so its pull on her eyes is amplified (then clamped to the eye's range). */
const GAZE_GAIN = 1.8;
const LEAN_PX = 5;
const LEAN_TRANSITION = "transform 900ms cubic-bezier(0.22, 1, 0.36, 1)";
const HEAD_TRANSITION = "transform 750ms cubic-bezier(0.34, 1.3, 0.64, 1)";
const LID_TRANSITION = "transform 70ms ease-in";

const BLINK_MS = 150;
const BLINK_MIN_MS = 2400;
const BLINK_JITTER_MS = 3600;
const DOUBLE_BLINK_CHANCE = 0.2;
/** While idle she now and then glances somewhere on her own (at the globe, up in thought, at the visitor). */
const GLANCE_MIN_MS = 3500;
const GLANCE_JITTER_MS = 4000;
const GLANCE_HOLD_MS = 1500;

type Glance = { x: number; y: number; tilt: number } | null;
const GLANCES: NonNullable<Glance>[] = [
  { x: 1, y: -0.2, tilt: 2.5 }, // over at the globe
  { x: 0.5, y: -0.9, tilt: -2 }, // remembering something
  { x: -0.6, y: 0.3, tilt: -1.5 }, // a look to the side
  { x: 0, y: 0, tilt: 3 }, // head tilt at the visitor
  { x: -0.1, y: 1, tilt: 0 }, // down at the ask box, inviting a question
  { x: 0.9, y: 0.4, tilt: 1.5 }, // over at the pins on the globe
];

/** Where she looks and how her head sits for each state; null = follow the cursor. */
const STATE_POSE: Partial<Record<CharacterState, { x: number; y: number; tilt: number }>> = {
  thinking: { x: 0.6, y: -0.9, tilt: -3 },
  pointing: { x: 1, y: -0.15, tilt: 3 },
  abstain: { x: -0.2, y: 0.8, tilt: -2.5 },
};
/** While the visitor types she watches the ask box under her. */
const TYPING_POSE = { x: 0, y: 1, tilt: 1.5 };

const clamp1 = (v: number) => Math.max(-1, Math.min(1, v));

interface NovaPortraitProps {
  state: CharacterState;
  meta?: CharacterMeta;
  gaze: { x: number; y: number };
  framing?: NovaFraming;
  near?: boolean;
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Random blinks, sometimes a double blink. */
function useBlink() {
  const [blink, setBlink] = useState(false);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const once = (delay: number) => {
      timers.push(setTimeout(() => setBlink(true), delay));
      timers.push(setTimeout(() => setBlink(false), delay + BLINK_MS));
    };
    const schedule = () => {
      timers.push(setTimeout(() => {
        if (document.visibilityState === "visible") {
          once(0);
          if (Math.random() < DOUBLE_BLINK_CHANCE) once(BLINK_MS + 140);
        }
        schedule();
      }, BLINK_MIN_MS + Math.random() * BLINK_JITTER_MS));
    };
    schedule();
    return () => timers.forEach(clearTimeout);
  }, []);
  return blink;
}

/** While idle, an occasional glance of her own; any cursor movement ends it at once, so she always follows the mouse. */
function useIdleGlance(active: boolean, gaze: { x: number; y: number }) {
  const [glance, setGlance] = useState<{ pose: NonNullable<Glance>; at: { x: number; y: number } } | null>(null);
  const gazeRef = useRef(gaze);
  useEffect(() => { gazeRef.current = gaze; }, [gaze]);
  useEffect(() => {
    if (!active || prefersReducedMotion()) return;
    let hold: ReturnType<typeof setTimeout>;
    let next: ReturnType<typeof setTimeout>;
    const schedule = () => {
      next = setTimeout(() => {
        if (document.visibilityState === "visible") {
          setGlance({ pose: GLANCES[Math.floor(Math.random() * GLANCES.length)], at: gazeRef.current });
          hold = setTimeout(() => setGlance(null), GLANCE_HOLD_MS);
        }
        schedule();
      }, GLANCE_MIN_MS + Math.random() * GLANCE_JITTER_MS);
    };
    schedule();
    return () => { clearTimeout(next); clearTimeout(hold); setGlance(null); };
  }, [active]);
  // the glance only holds while the cursor stays where it was when she looked away
  return glance && glance.at.x === gaze.x && glance.at.y === gaze.y ? glance.pose : null;
}

/**
 * Nova, the designer's painted portrait, rigged: her eyes follow the cursor, she
 * blinks, her head turns on her neck, she breathes, glances around when idle,
 * looks at the globe when a pin is hovered, nods while answering, looks up in
 * thought, and hops when she waves. Same props as the SVG rig.
 */
export function NovaPortrait({ state, meta, gaze, framing = "full", near = false }: NovaPortraitProps) {
  const typing = state === "listening" && meta?.text === "typing";
  const blink = useBlink();
  const glance = useIdleGlance(state === "idle" && !near, gaze);
  const follow = { x: clamp1(gaze.x * GAZE_GAIN), y: clamp1(gaze.y * GAZE_GAIN), tilt: near ? 2 : 0 };
  const pose = (typing ? TYPING_POSE : STATE_POSE[state]) ?? glance ?? follow;

  const headTurn = pose.x * HEAD_TURN_DEG + pose.tilt;
  const figureStyle: CSSProperties = {
    ...FIGURE,
    ...(framing === "full" ? STAGE_DROP : {}),
    transform: `translate(${pose.x * LEAN_PX}px, ${pose.y}px)`,
    transition: LEAN_TRANSITION,
  };
  const headStyle: CSSProperties = { ...HEAD, transform: `rotate(${headTurn}deg)`, transition: HEAD_TRANSITION };
  const irisStyle: CSSProperties = { transform: `translate(${pose.x * IRIS_X_PCT}%, ${pose.y * IRIS_Y_PCT}%)`, transition: IRIS_TRANSITION };
  const lidStyle: CSSProperties = { transformOrigin: LID_ORIGIN, transform: `scaleY(${blink ? 1 : LID_SCALE[state] ?? 0})`, transition: LID_TRANSITION };

  return (
    <div className="nova-portrait nv-root" data-state={typing ? "attentive" : state} data-framing={framing} data-near={near} data-blink={blink} style={framing === "full" ? STAGE_ROOT : ROOT} aria-hidden>
      {/* React 19 hoists and de-duplicates this, so every slot shares one copy */}
      <style href="nova-rig" precedence="default">{NOVA_RIG_CSS}</style>
      <div className="nv-figure" style={figureStyle}>
        <div className="nv-breathe" style={FILL}>
          <Layer src={LAYERS.body} w={CANVAS.w} h={CANVAS.h} />
          <div className="nv-head" style={headStyle}>
            <div className="nv-sway" style={HEAD}>
              <Layer src={LAYERS.head} w={CANVAS.w} h={CANVAS.h} />
              <div style={FILL}>
                <Layer src={LAYERS.iris} w={CANVAS.w} h={CANVAS.h} style={irisStyle} />
                <Layer src={LAYERS.frame} w={CANVAS.w} h={CANVAS.h} />
                <Layer src={LAYERS.lids} w={CANVAS.w} h={CANVAS.h} style={lidStyle} />
              </div>
            </div>
          </div>
        </div>
      </div>
      {framing === "full" && <NovaSpeech state={state} meta={meta} typing={typing} />}
    </div>
  );
}

function Layer({ src, w, h, style }: { src: string; w: number; h: number; style?: CSSProperties }) {
  // eslint-disable-next-line @next/next/no-img-element -- transparent painted layers, stacked and sized by CSS
  return <img src={src} width={w} height={h} alt="" draggable={false} decoding="async" style={{ ...FILL, ...style }} />;
}
