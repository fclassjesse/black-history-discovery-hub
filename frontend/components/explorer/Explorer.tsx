"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef } from "react";
import { Stage } from "@/components/explorer/Stage";
import { CharacterDock } from "@/components/explorer/CharacterDock";
import { SearchView } from "@/components/results/SearchView";
import { HowItWorks, PartnerCall, Places, SourceStrip, Statement, Stories } from "@/components/home/HomeSections";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { PageSurface } from "@/components/layout/PageSurface";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";
import { character } from "@/lib/character";
import { useHref } from "@/lib/i18n";

const QUERY_KEYS = ["q", "mode", "types", "access", "institution", "lang", "verification", "rights", "date_from", "date_to", "identifier", "location", "source"];

/** Does the URL describe a search? Then the results drawer replaces the stage. */
export function isExploring(sp: URLSearchParams): boolean {
  return QUERY_KEYS.some((k) => (sp.get(k) ?? "").trim().length > 0);
}

/** Same-page URL change: Next picks native pushState up, so the world and Nova stay mounted. The caller passes a locale-prefixed URL. */
export function goTo(url: string) {
  window.history.pushState(null, "", url);
}

/**
 * The single page. Stage (Nova + ask) and results (drawer + filters) are two
 * states of one URL; the globe behind them never reloads.
 */
export function Explorer() {
  const sp = useSearchParams();
  const href = useHref();
  const active = isExploring(new URLSearchParams(sp.toString()));
  const rootRef = useRef<HTMLDivElement>(null);
  const busy = useRef(false);

  // scroll back to the top whenever the drawer takes over
  useEffect(() => { if (active) window.scrollTo({ top: 0, behavior: "auto" }); }, [active]);

  const ask = useCallback((question: string, input: "text" | "voice") => {
    if (busy.current) return;
    const url = href(`/?q=${encodeURIComponent(question)}&guide=1&input=${input}`);
    character.set("pointing", { text: question });
    if (prefersReducedMotion() || !rootRef.current) { goTo(url); return; }
    busy.current = true;
    const gsap = ensureGsap();
    gsap.timeline({ onComplete: () => { busy.current = false; goTo(url); } })
      .to("[data-stage-bubble]", { scale: 0.9, y: -24, opacity: 0, duration: 0.5, ease: "power2.in" }, 0)
      .to("[data-stage-fade], [data-stage-sections]", { opacity: 0, duration: 0.35 }, 0);
  }, [href]);

  return (
    <div ref={rootRef} className="relative">
      {active ? (
        <SearchView />
      ) : (
        <>
          <PageSurface tone="flame" />
          <Stage onAsk={ask} />
          <div data-stage-sections>
            <SourceStrip />
            <Statement />
            <Places />
            <Stories />
            <HowItWorks />
            <PartnerCall />
            <SiteFooter tone="flame" />
          </div>
        </>
      )}
      <CharacterDock layout={active ? "guide" : "stage"} />
    </div>
  );
}
