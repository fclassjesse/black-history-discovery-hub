"use client";

import { useEffect, useState } from "react";
import type { CharacterMeta, CharacterState } from "@/lib/character";
import { useT } from "@/lib/i18n";

/** Idle chatter: first hello shortly after load, then a new line every so often. */
const FIRST_LINE_MS = 1200;
const LINE_SHOW_MS = 6000;
const LINE_GAP_MS = 7000;
const LEAVE_MS = 280;
/** Typewriter speed. */
const CHAR_MS = 26;
const MAX_QUOTE = 48;

interface NovaSpeechProps {
  state: CharacterState;
  meta?: CharacterMeta;
  typing: boolean;
}

function reducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** What she says for what she is doing right now; null = nothing to say, fall back to idle chatter. */
function useStateLine({ state, meta, typing }: NovaSpeechProps): { text: string; dots?: boolean } | null {
  const { t } = useT();
  if (typing) return { text: t("nova.say.typing") };
  switch (state) {
    case "listening": return { text: t("nova.say.listening") };
    case "thinking": return { text: t("nova.say.thinking"), dots: true };
    case "abstain": return { text: t("nova.say.abstain") };
    case "speaking": return { text: t("nova.say.speaking") };
    case "pointing": {
      const q = meta?.text?.trim();
      if (!q) return { text: t("nova.say.pin") };
      return { text: t("nova.say.searching", { q: q.length > MAX_QUOTE ? `${q.slice(0, MAX_QUOTE)}…` : q }) };
    }
    default: return null;
  }
}

/** Cycles through the idle lines while nothing else is going on. */
function useIdleLine(active: boolean): { text: string; leaving: boolean } | null {
  const { raw } = useT();
  const lines = raw<string[]>("nova.idle") ?? [];
  const [index, setIndex] = useState(-1);
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    if (!active || lines.length === 0) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let i = 0;
    const show = (delay: number) => {
      timers.push(setTimeout(() => {
        if (document.visibilityState === "visible") { setLeaving(false); setIndex(i % lines.length); i += 1; }
        timers.push(setTimeout(() => setLeaving(true), LINE_SHOW_MS));
        timers.push(setTimeout(() => { setIndex(-1); setLeaving(false); }, LINE_SHOW_MS + LEAVE_MS));
        show(LINE_SHOW_MS + LINE_GAP_MS);
      }, delay));
    };
    show(FIRST_LINE_MS);
    return () => { timers.forEach(clearTimeout); setIndex(-1); setLeaving(false); };
  }, [active, lines.length]);
  return active && index >= 0 ? { text: lines[index], leaving } : null;
}

/**
 * Types the line out letter by letter (all at once with reduced motion). Driven by elapsed
 * time, not tick count, so a busy page (the globe) can delay frames but never slow the line.
 * Remount per line via `key`.
 */
function Typewriter({ text }: { text: string }) {
  const [n, setN] = useState(() => (reducedMotion() ? text.length : 0));
  useEffect(() => {
    if (reducedMotion()) return;
    const start = performance.now();
    const id = setInterval(() => {
      const next = Math.min(text.length, Math.floor((performance.now() - start) / CHAR_MS));
      setN(next);
      if (next >= text.length) clearInterval(id);
    }, CHAR_MS);
    return () => clearInterval(id);
  }, [text]);
  const done = n >= text.length;
  return (
    <>
      <span aria-hidden>{text.slice(0, n)}</span>
      {!done && <span className="nv-say-caret" aria-hidden />}
      <span className="sr-only">{text}</span>
    </>
  );
}

/**
 * Nova's speech bubble, at her top right on the stage. She reacts to what the visitor
 * does (typing, voice, a pin hovered, a search running, nothing found) and, while idle,
 * says a friendly line now and then. Purely decorative for pointer input: it never
 * blocks clicks, and it stays inside the left column so the globe is never covered.
 */
export function NovaSpeech(props: NovaSpeechProps) {
  const stateLine = useStateLine(props);
  // her little hop (celebrate) does not interrupt the idle chatter
  const idleLine = useIdleLine(stateLine === null);
  const line = stateLine ?? idleLine;
  if (!line) return null;
  const leaving = "leaving" in line && line.leaving;
  const dots = "dots" in line && line.dots;
  return (
    <p className="nv-say" data-leaving={leaving} key={line.text} role="status" aria-live="polite">
      <Typewriter key={line.text} text={line.text} />
      {dots && <span className="nv-say-dots" aria-hidden><i /><i /><i /></span>}
    </p>
  );
}
