"use client";

import { useRef } from "react";
import { useInstitutions } from "@/lib/useInstitutions";
import { useParallax, useReveal, SplitWords } from "@/lib/motion";
import { Stamp, Shape } from "@/components/art/Stamps";
import { InstitutionTile } from "@/components/results/InstitutionTile";
import { Link, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

/* ------------------------------------------------------------------ strip */
export function SourceStrip() {
  const { t, tn } = useT();
  const L = useLabels();
  const { items } = useInstitutions();
  if (!items) return <div className="h-16" aria-hidden />;
  const list = [...items, ...items];
  return (
    <div className="marquee pointer-events-auto relative z-10 border-y-2 border-ink/80 bg-flame py-3" aria-label={t("home.stripAria")}>
      <div className="marquee-track items-center">
        {list.map((i, idx) => (
          <Link key={`${i.id}-${idx}`} href={`/institutions/${i.slug}`} className="flex shrink-0 items-center gap-3 no-underline" aria-hidden={idx >= items.length} tabIndex={idx >= items.length ? -1 : 0}>
            <span className="grid h-11 w-11 place-items-center rounded-full bg-chalk"><Stamp kind={i.kind} className="h-8 w-8" /></span>
            <span className="leading-tight">
              <span className="block font-semibold text-ink">{i.name}</span>
              <span className="block text-sm text-ink/70">{L.kind(i.kind)}{i.city ? ` · ${i.city}` : ""} · <span className="tnum">{tn("common.records", i.published_records ?? 0)}</span></span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- statement */
export function Statement() {
  const { t } = useT();
  const ref = useReveal<HTMLElement>({ variant: "words", stagger: 0.02 });
  return (
    <section ref={ref} className="pointer-events-auto relative z-10 bg-flame px-[var(--gutter)] py-[var(--space-section)]">
      <div className="mx-auto max-w-[1600px]">
        <p className="eyebrow"><span className="sq" /> {t("home.statementEyebrow")}<span className="accent">{t("home.statementAccent")}</span></p>
        <p className="mt-6 max-w-5xl text-[clamp(1.6rem,1rem+2.6vw,3.4rem)] font-medium leading-[1.1] tracking-[-0.02em] text-ink" style={{ perspective: 800 }}>
          <SplitWords text={t("home.statement")} />
        </p>
        <Link href="#how" className="btn btn-pill-chalk mt-8"><span className="display uppercase tracking-[0.06em]">{t("home.howItWorks")}</span></Link>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- places */
export function Places() {
  const { t } = useT();
  const { items, error } = useInstitutions();
  const revealRef = useReveal<HTMLDivElement>({ variant: "scale", stagger: 0.06, start: "top 80%" });
  const headRef = useReveal<HTMLDivElement>({ variant: "words", stagger: 0.05 });
  const scroller = useRef<HTMLDivElement>(null);
  const nudge = (dir: 1 | -1) => scroller.current?.scrollBy({ left: dir * 340, behavior: "smooth" });
  return (
    <section className="pointer-events-auto relative z-10 overflow-hidden bg-flame px-[var(--gutter)] pb-[var(--space-section)]" aria-labelledby="places-heading">
      <div className="mx-auto max-w-[1600px]">
        <div ref={headRef}>
          <p className="eyebrow"><span className="sq" /> {t("home.placesEyebrow")}<span className="accent">{t("home.placesAccent")}</span></p>
          <h2 id="places-heading" className="mt-4 text-[length:var(--text-h1)]" style={{ perspective: 800 }}><SplitWords text={t("home.placesTitle")} /></h2>
          <p className="mt-4 max-w-xl text-lg leading-snug text-ink/85">{t("home.placesLede")}</p>
        </div>
        <div ref={revealRef} className="relative mt-8">
          {error && <p role="alert" className="plate p-4 text-sm text-danger">{t("institutions.couldNotLoad", { error })}</p>}
          <div ref={scroller} className="scroller -mx-[var(--gutter)] px-[var(--gutter)]">
            {(items ?? []).map((i, idx) => <InstitutionTile key={i.id} inst={i} index={idx} />)}
            <Link href="/institutions" data-reveal-child className="plate-ink grid aspect-[4/5] w-[min(60vw,220px)] place-items-center p-5 text-center no-underline">
              <span><span className="display block text-2xl">{t("home.allInstitutions")}</span><span className="mt-2 block text-sm text-cream/70">{t("home.directory")}</span></span>
            </Link>
          </div>
          <div className="pointer-events-none absolute inset-y-0 -left-2 hidden items-center lg:flex">
            <button type="button" className="btn btn-pill-chalk btn-icon pointer-events-auto" aria-label={t("home.scrollLeft")} onClick={() => nudge(-1)}>←</button>
          </div>
          <div className="pointer-events-none absolute inset-y-0 -right-2 hidden items-center lg:flex">
            <button type="button" className="btn btn-pill-chalk btn-icon pointer-events-auto" aria-label={t("home.scrollRight")} onClick={() => nudge(1)}>→</button>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- stories */
interface Story { q: string; title: string; body: string; cta: string; href: string }
const STORY_TONES = ["bubble-white", "bubble-sun", "bubble-rose"];

export function Stories() {
  const { t, raw } = useT();
  const stories = raw<Story[]>("home.stories");
  const ref = useParallax<HTMLElement>();
  const revealRef = useReveal<HTMLDivElement>({ variant: "rise", stagger: 0.15 });
  return (
    <section ref={ref} className="pointer-events-auto relative z-10 overflow-hidden bg-chalk px-[var(--gutter)] py-[var(--space-section)]" aria-labelledby="stories-heading" style={{ borderRadius: "var(--radius-plate) var(--radius-plate) 0 0" }}>
      <Shape variant="quarter" color="var(--flame)" className="pointer-events-none absolute -left-16 top-10 w-56 opacity-90 lg:w-80" />
      <Shape variant="ring" color="var(--sun)" className="pointer-events-none absolute -right-10 bottom-20 w-44 lg:w-72" data-speed="0.5" />
      <div className="relative mx-auto max-w-[1600px]">
        <p className="eyebrow text-ink-muted"><span className="inline-block h-3 w-3 rounded-full bg-stone" /> {t("home.tryIt")}</p>
        <h2 id="stories-heading" className="mx-auto mt-4 max-w-4xl text-center text-[length:var(--text-h2)]">
          <span className="accent block text-flame-deep">{t("home.storiesAccent")}</span>
          {t("home.storiesTitle")}
        </h2>
        <div ref={revealRef} className="mt-14 grid gap-6 lg:grid-cols-3 lg:items-start lg:gap-8">
          {stories.map((s, i) => (
            <article key={s.q} data-reveal-child className={`bubble ${STORY_TONES[i % STORY_TONES.length]} p-6 sm:p-8 ${i === 1 ? "lg:mt-16" : i === 2 ? "lg:-mt-6" : ""}`} data-speed={i === 1 ? "0.15" : i === 2 ? "-0.1" : "0"}>
              <p className="kicker text-ink-muted">{t("home.youAsk")}</p>
              <p className="display mt-2 text-[clamp(1.4rem,1rem+1.6vw,2.6rem)] leading-tight">“{s.q}”</p>
              <p className="mt-6 text-lg font-medium leading-snug">{s.title}</p>
              <p className="mt-1 text-ink-2">{s.body}</p>
              <Link href={s.href} className="btn mt-6">{s.cta} →</Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- how it works */
interface Step { t: string; d: string }

export function HowItWorks() {
  const { t, raw } = useT();
  const steps = raw<Step[]>("home.steps");
  const ref = useReveal<HTMLOListElement>({ variant: "rise", stagger: 0.12 });
  return (
    <section id="how" className="pointer-events-auto relative z-10 bg-flame px-[var(--gutter)] py-[var(--space-section)]" aria-labelledby="how-heading">
      <div className="mx-auto max-w-[1600px]">
        <p className="eyebrow"><span className="sq" /> {t("home.fourEyebrow")}<span className="accent">{t("home.fourAccent")}</span></p>
        <h2 id="how-heading" className="mt-4 text-[length:var(--text-h1)]">{t("home.howTitle")}</h2>
        <ol ref={ref} className="mt-12 grid gap-y-10 lg:grid-cols-2 lg:gap-x-16">
          {steps.map((s, i) => (
            <li key={s.t} data-reveal-child className={`grid grid-cols-[auto_1fr] items-start gap-5 ${i % 2 === 1 ? "lg:mt-16" : ""}`}>
              <span className={`big-number ${i % 2 === 1 ? "outline-text" : ""} text-ink`}>{String(i + 1).padStart(2, "0")}</span>
              <div className="pt-2">
                <h3 className="text-[length:var(--text-h3)]">{s.t}</h3>
                <p className="mt-2 max-w-md text-ink/85">{s.d}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- partner call */
export function PartnerCall() {
  const { t } = useT();
  const ref = useReveal<HTMLDivElement>({ variant: "scale" });
  return (
    <section className="pointer-events-auto relative z-10 bg-flame px-[var(--gutter)] pb-[var(--space-section)]" aria-labelledby="partner-heading">
      <div ref={ref} className="plate-ochre halftone relative mx-auto grid max-w-[1600px] gap-8 overflow-hidden p-7 sm:p-10 lg:grid-cols-[1fr_auto] lg:items-end lg:p-14">
        <Shape variant="star" color="var(--sun)" className="pointer-events-none absolute -right-10 -top-10 w-40 rotate-12 lg:w-64" />
        <div>
          <p className="eyebrow"><span className="sq" /> {t("home.forInstitutions")}</p>
          <h2 id="partner-heading" className="mt-4 max-w-3xl text-[length:var(--text-h1)]">{t("home.partnerTitle")}</h2>
          <p className="mt-4 max-w-xl text-lg leading-snug text-ink/85">{t("home.partnerLede")}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link href="/app" className="btn btn-lg">{t("home.openApp")}</Link>
          <Link href="/partner/login" className="btn btn-secondary btn-lg">{t("home.desktopPortal")}</Link>
        </div>
      </div>
    </section>
  );
}
