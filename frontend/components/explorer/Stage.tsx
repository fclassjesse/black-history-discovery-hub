"use client";

import { useEffect, useRef, useState } from "react";
import { PushToTalk } from "@/components/guide/PushToTalk";
import { WorldControls } from "@/components/world/WorldControls";
import { NOVA_NAME } from "@/components/character/Nova";
import { ensureGsap, prefersReducedMotion, useMagnetic } from "@/lib/motion";
import { useWorld } from "@/lib/worldStore";
import { institutionsToPins, useInstitutions } from "@/lib/useInstitutions";
import { character } from "@/lib/character";
import { Link, useT } from "@/lib/i18n";

/**
 * The opening screen. Nova, head to toe and as tall as the stage, owns the
 * left half; a short ask bar (one-line headline + pill + chips) sits under
 * her, over her feet; the world turns on the right. Phones stack the same.
 */
export function Stage({ onAsk }: { onAsk: (question: string, input: "text" | "voice") => void }) {
  const { t, raw } = useT();
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"text" | "voice">("text");
  const askRef = useMagnetic<HTMLButtonElement>(0.25);
  const rootRef = useRef<HTMLElement>(null);
  const { items } = useInstitutions();
  const { publish, setInset } = useWorld();
  const titleWords = raw<string[]>("stage.title");
  const suggestions = raw<string[]>("stage.suggestions");

  // the world shows the whole directory while idle
  useEffect(() => {
    setInset({ left: 0, top: 0, right: 0, bottom: 0 });
    publish(items ? institutionsToPins(items) : [], new Map(), "idle");
  }, [items, publish, setInset]);

  // Nova says hello, then settles
  useEffect(() => {
    const timer = setTimeout(() => character.set("celebrate", undefined, 1800), 700);
    return () => clearTimeout(timer);
  }, []);

  // entrance choreography
  useEffect(() => {
    const root = rootRef.current;
    if (!root || prefersReducedMotion()) return;
    const gsap = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.timeline({ defaults: { ease: "power3.out" } })
        .from("[data-stage-tag]", { y: -16, opacity: 0, duration: 0.5 }, 0.1)
        .from("[data-stage-bubble]", { scale: 0.86, y: 24, opacity: 0, duration: 0.8, ease: "back.out(1.5)" }, 0.55)
        .from("[data-stage-title] > span", { yPercent: 110, opacity: 0, duration: 0.6, stagger: 0.06 }, 0.75)
        .from("[data-stage-form], [data-stage-chips]", { y: 16, opacity: 0, duration: 0.5, stagger: 0.1 }, 1)
        .from("[data-stage-controls]", { y: 20, opacity: 0, duration: 0.6 }, 1.1);
    }, root);
    return () => ctx.revert();
  }, []);

  const submit = (e?: React.FormEvent, text?: string) => {
    e?.preventDefault();
    const question = (text ?? q).trim();
    if (!question) return;
    onAsk(question, text ? "text" : mode);
  };

  return (
    <section ref={rootRef} aria-labelledby="stage-heading" className="stage pointer-events-none relative flex flex-col px-[var(--gutter)] pt-2 on-flame lg:overflow-visible">
      <div className="stage-grid mx-auto grid w-full max-w-[1600px] flex-1 grid-cols-1 pt-12 lg:grid-cols-12 lg:grid-rows-[minmax(0,1fr)_auto] lg:gap-x-4 lg:pt-0">
        {/* Nova's spot: the dock positions her over this anchor. Head to toe, as tall as the stage, owning the left half;
            a short ask bar sits under her and may cover her feet; the world owns the right half. */}
        <div data-character-anchor data-stage-fade className="stage-anchor mx-auto w-[min(100%,clamp(280px,80vw,440px))] lg:col-span-7 lg:col-start-1 lg:row-start-1 lg:-mt-12 lg:mx-0 lg:h-[calc(100%+3rem)] lg:w-auto lg:max-w-full lg:justify-self-center" aria-hidden />

        <div data-stage-bubble className="bubble bubble-stage pointer-events-auto relative z-30 -mt-12 px-4 py-3 sm:px-5 lg:col-span-6 lg:col-start-1 lg:row-start-2 lg:-mt-24 lg:mb-4">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
            <h1 id="stage-heading" data-stage-title className="stage-title">
              {titleWords.map((w, i) => <span key={i} className={`inline-block ${i === titleWords.length - 1 ? "accent text-flame-deep" : ""}`}>{w}</span>)}
            </h1>
            <p data-stage-tag className="kicker text-ink-muted">{t("stage.tag", { name: NOVA_NAME })}</p>
          </div>
          <form data-stage-form onSubmit={submit} role="search" aria-label={t("stage.formAria")} className="mt-2 flex items-start gap-2">
            <PushToTalk size="md" onInterim={(tr) => { setMode("voice"); setQ(tr); }} onTranscript={(tr) => { setMode("voice"); setQ(tr); }} />
            <div className="min-w-0 flex-1">
              <label htmlFor="stage-q" className="sr-only">{t("stage.inputLabel")}</label>
              <div className="ask-pill ask-pill-sm">
                <input id="stage-q" value={q} onChange={(e) => { setMode("text"); setQ(e.target.value); }} onFocus={() => { if (character.current.state === "idle" || character.current.state === "celebrate") character.set("listening", { text: "typing" }); }} onBlur={() => { if (character.current.meta?.text === "typing") character.set("idle"); }} placeholder={t("stage.placeholder")} autoComplete="off" />
                <button ref={askRef} type="submit" className="btn btn-sm" disabled={!q.trim()}>{t("stage.ask")} <span aria-hidden>→</span></button>
              </div>
              {mode === "voice" && q && <p className="mt-1 text-xs text-ink-muted" aria-live="polite">{t("stage.editTranscript")}</p>}
            </div>
          </form>
          <div data-stage-chips className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-ink-muted">{t("stage.try")}</span>
            {suggestions.map((s) => <button key={s} type="button" className="btn btn-secondary btn-sm" onClick={() => submit(undefined, s)}>{s}</button>)}
            <Link href="/advanced" className="ml-auto underline">{t("stage.advanced")}</Link>
          </div>
        </div>
      </div>

      <div data-stage-controls className="pointer-events-auto absolute right-[var(--gutter)] top-2 hidden lg:block"><WorldControls /></div>
    </section>
  );
}
