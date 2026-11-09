"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiGetShared, apiPostShared } from "@/lib/api";
import { searchPath } from "@/lib/searchRequest";
import { useSelection } from "@/lib/store";
import { useWorld } from "@/lib/worldStore";
import type { GuideResponse, RecordCard as RecordCardT, SearchResponse } from "@/lib/types";
import { countActive, FilterRail, type FilterState } from "@/components/filters/FilterRail";
import { RecordCard } from "@/components/results/RecordCard";
import { OnlinePanel } from "@/components/results/OnlinePanel";
import { GuidePanel } from "@/components/guide/GuidePanel";
import { PushToTalk } from "@/components/guide/PushToTalk";
import { Notice } from "@/components/ui/Notice";
import { WorldControls } from "@/components/world/WorldControls";
import { PageSurface } from "@/components/layout/PageSurface";
import { ensureGsap, prefersReducedMotion } from "@/lib/motion";
import { character } from "@/lib/character";
import { Link, useFormat, useHref, useT } from "@/lib/i18n";
import { DESKTOP_QUERY, useMediaQuery } from "@/lib/useMediaQuery";

const DRAWER_LG = 460;
const DRAWER_XL = 540;
const TOPBAR = 178; // header + ask bar + its secondary row

function filtersFromParams(sp: URLSearchParams): FilterState {
  const list = (k: string) => (sp.get(k) ?? "").split(",").filter(Boolean);
  return { types: list("types"), access: list("access"), institution: list("institution"), lang: list("lang"), verification: list("verification"), rights: list("rights"), country: list("country"), people: list("people"), places: list("places"), communities: list("communities"), date_from: sp.get("date_from") ?? "", date_to: sp.get("date_to") ?? "" };
}

function Legend() {
  const { t } = useT();
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-muted" aria-label={t("world.legendAria")}>
      <li className="flex items-center gap-1"><span className="pin-dot" /> {t("world.legend.verified")}</li>
      <li className="flex items-center gap-1"><span className="pin-dot" data-precision="catalogue" /> {t("world.legend.catalogue")}</li>
      <li className="flex items-center gap-1"><span className="pin-dot" data-precision="approximate" /> {t("world.legend.approximate")}</li>
      <li className="flex items-center gap-1"><span className="pin-dot" data-precision="demo" /> {t("world.legend.demo")}</li>
    </ul>
  );
}

/** Paper placeholders while the catalogues answer: the drawer is never an empty box with a spinner. */
function Skeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <div key={i} className="card sk-card" style={{ "--i": i } as React.CSSProperties}>
          <div className="flex items-start gap-3">
            <span className="sk h-11 w-11 shrink-0 rounded-2xl" />
            <div className="min-w-0 flex-1 space-y-2.5 pt-1">
              <div className="flex gap-1.5"><span className="sk h-5 w-16" /><span className="sk h-5 w-28" /></div>
              <span className="sk h-6 w-[88%]" />
              <span className="sk h-6 w-[58%]" />
              <span className="sk h-3.5 w-[70%]" />
            </div>
          </div>
          <span className="sk mt-4 h-3.5 w-[94%]" />
          <span className="sk mt-2 h-3.5 w-[52%]" />
        </div>
      ))}
    </div>
  );
}

/** Same-page navigation: the URL is the state; Next syncs useSearchParams with native pushState. */
function go(url: string) { window.history.pushState(null, "", url); }

export function SearchView() {
  const { t, tn, locale } = useT();
  const fmt = useFormat();
  const href = useHref();
  const sp = useSearchParams();
  const q = sp.get("q") ?? "";
  const mode = (sp.get("mode") === "advanced" ? "advanced" : "natural") as "natural" | "advanced";
  const wantGuide = sp.get("guide") === "1" && mode === "natural" && q.trim().length > 0;
  const inputMode = sp.get("input") === "voice" ? "voice" : "text";
  const page = Number(sp.get("page") ?? "1") || 1;
  const filters = useMemo(() => filtersFromParams(new URLSearchParams(sp.toString())), [sp]);

  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [guide, setGuide] = useState<GuideResponse | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);
  const [draft, setDraft] = useState(q);
  const [draftMode, setDraftMode] = useState<"text" | "voice">("text");
  const [filtersOpen, setFiltersOpen] = useState(false);
  // the guide reads the active filters and the last turns; refs so the guide effect does not re-fire on filter changes
  const filtersRef = useRef(filters);
  useEffect(() => { filtersRef.current = filters; }, [filters]);
  const historyRef = useRef<{ question: string; answer: string; record_ids: string[] }[]>([]);
  const { reset, selectedRecordId, setHighlights } = useSelection();
  const { publish, setInset, setPending } = useWorld();
  const rootRef = useRef<HTMLDivElement>(null);
  // one layout branch is rendered, not both: 20 record cards, not 40
  const isDesktop = useMediaQuery(DESKTOP_QUERY);

  // the draft follows the URL query (URL is the source of truth)
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setDraft(q), [q]);

  // results mode flag on <html>: the map attribution moves right of the drawer (globals.css)
  useEffect(() => {
    document.documentElement.dataset.results = "true";
    return () => { delete document.documentElement.dataset.results; };
  }, []);

  // the drawer slides in over the world
  useEffect(() => {
    const root = rootRef.current;
    if (!root || prefersReducedMotion()) return;
    const gsap = ensureGsap();
    const ctx = gsap.context(() => {
      gsap.from("[data-drawer]", { x: -48, opacity: 0, duration: 0.7, ease: "power3.out", clearProps: "all" });
    }, root);
    return () => ctx.revert();
  }, []);

  // reserve the drawer area so camera fits land in the visible part of the world
  useEffect(() => {
    const compute = () => {
      const w = window.innerWidth, h = window.innerHeight;
      if (w >= 1024) {
        const gutter = Math.min(Math.max(16, 8 + 0.02 * w), 40);
        const drawer = w >= 1280 ? DRAWER_XL : DRAWER_LG;
        setInset({ left: (gutter + drawer + 24) / w, top: TOPBAR / h, right: (gutter + 90) / w, bottom: 0.14 });
      } else {
        setInset({ left: 0, top: TOPBAR / h, right: 0, bottom: 0.52 });
      }
    };
    compute();
    window.addEventListener("resize", compute);
    return () => window.removeEventListener("resize", compute);
  }, [setInset]);

  // search
  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- URL-driven fetch; loading state must flip synchronously
    setLoading(true);
    setError(null);
    setPending(true); // the world leans in until publish() hands it the pins
    reset();
    // shared: joins the request Explorer started at ask time (and React's dev double-run) instead of sending another
    apiGetShared<SearchResponse>(searchPath(new URLSearchParams(sp.toString()), locale))
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) { setError(e.message); setPending(false); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp, locale]);
  useEffect(() => () => setPending(false), [setPending]);

  // guide (natural mode only, same path for text and voice); the UI locale is sent so the answer language can fall back to it
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- clears the previous answer when the question changes
    if (!wantGuide) { setGuide(null); setHighlights([], []); return; }
    let cancelled = false;
    setGuideLoading(true);
    const f = filtersRef.current;
    const guideFilters = Object.fromEntries(Object.entries({
      types: f.types.join(","), access: f.access.join(","), institution: f.institution.join(","), lang: f.lang.join(","), verification: f.verification.join(","),
      rights: f.rights.join(","), country: f.country.join(","), people: f.people.join(","), places: f.places.join(","), communities: f.communities.join(","),
      date_from: f.date_from, date_to: f.date_to,
    }).filter(([, v]) => v));
    apiPostShared<GuideResponse>("/api/guide/ask", { question: q, input_mode: inputMode, filters: guideFilters, history: historyRef.current.slice(-3), locale })
      .then((g) => {
        if (cancelled) return;
        setGuide(g);
        if (!g.abstain && g.answer) historyRef.current = [...historyRef.current, { question: q, answer: g.answer, record_ids: g.highlight_record_ids.slice(0, 12) }].slice(-6);
      })
      .catch((e) => { if (!cancelled) setGuide({ question: q, answer: "", citations: [], abstain: true, abstain_reason: t("guide.requestFailed", { error: e.message }), records: [], highlight_record_ids: [], map_focus_institution_ids: [], provider: { name: "none", model: null, configured: false }, validation_error: null, evidence_count: 0 }); })
      .finally(() => { if (!cancelled) setGuideLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, wantGuide, inputMode, setHighlights, locale]);

  const recordsById = useMemo(() => {
    const m = new Map<string, RecordCardT>();
    data?.results.forEach((r) => m.set(r.id, r));
    data?.online_resources.forEach((r) => m.set(r.id, r));
    guide?.records.forEach((r) => m.set(r.id, r));
    return m;
  }, [data, guide]);

  // hand the pins to the world once results exist
  useEffect(() => {
    if (!data) return;
    publish(data.pins, recordsById, "results", data.locality ?? null);
  }, [data, recordsById, publish]);

  const citationsByRecord = useMemo(() => {
    const m = new Map<string, number[]>();
    guide?.citations.forEach((c) => m.set(c.record_id, [...(m.get(c.record_id) ?? []), c.n]));
    return m;
  }, [guide]);

  const navigate = useCallback((next: Partial<Record<string, string>>) => {
    const p = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(next)) { if (v) p.set(k, v); else p.delete(k); }
    if (!("page" in next)) p.delete("page");
    go(href(`/?${p.toString()}`));
  }, [sp, href]);

  const onFilters = (f: FilterState) => navigate({ types: f.types.join(","), access: f.access.join(","), institution: f.institution.join(","), lang: f.lang.join(","), verification: f.verification.join(","), rights: f.rights.join(","), country: f.country.join(","), people: f.people.join(","), places: f.places.join(","), communities: f.communities.join(","), date_from: f.date_from, date_to: f.date_to });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    character.set("pointing", { text: draft.trim() });
    navigate({ q: draft.trim(), mode: "natural", guide: "1", input: draftMode });
  };

  const startOver = () => { character.set("idle"); go(href("/")); };

  useEffect(() => {
    if (!selectedRecordId) return;
    document.getElementById(`record-${selectedRecordId}`)?.scrollIntoView({ block: "nearest", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [selectedRecordId]);

  const totalPages = data ? Math.max(1, Math.ceil(Math.min(data.total, data.capped ? data.candidate_limit : data.total) / data.page_size)) : 1;
  const alsoCited = guide ? guide.records.filter((r) => !data?.results.some((x) => x.id === r.id) && citationsByRecord.has(r.id)) : [];
  const activeFilters = countActive(filters);

  const askBar = (
    <form onSubmit={submit} role="search" aria-label={t("search.aria")} className="pointer-events-auto">
      <div className="flex items-start gap-3">
        <button type="button" className="btn btn-secondary btn-icon shrink-0" onClick={startOver} aria-label={t("search.back")} title={t("search.back")}><span aria-hidden className="text-lg leading-none">←</span></button>
        <PushToTalk size="md" onInterim={(tr) => { setDraftMode("voice"); setDraft(tr); }} onTranscript={(tr) => { setDraftMode("voice"); setDraft(tr); }} />
        <div className="min-w-0 flex-1">
          <label htmlFor="search-q" className="sr-only">{mode === "advanced" ? t("search.labelAdvanced") : t("search.labelAsk")}</label>
          <div className="ask-pill">
            <input id="search-q" value={draft} onChange={(e) => { setDraftMode("text"); setDraft(e.target.value); }} placeholder={t("search.placeholder")} autoComplete="off" />
            <button type="submit" className="btn">{t("search.ask")}</button>
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-nowrap items-center gap-2 overflow-x-auto pl-[6.75rem] text-xs [scrollbar-width:none]">
        {mode === "advanced" ? (<><span className="badge">{t("search.advancedBadge")}</span><Link href={`/advanced?${sp.toString()}`} className="btn btn-secondary btn-sm shrink-0">{t("search.edit")}</Link></>) : (<Link href="/advanced" className="btn btn-secondary btn-sm shrink-0"><span aria-hidden>⚙</span> {t("search.advanced")}</Link>)}
        {data && data.alias_expansion.length > 0 && mode === "natural" && (
          <>
            <span className="shrink-0 whitespace-nowrap rounded-full bg-cream/80 px-2 py-1 text-ink-muted">{t("search.also")}</span>
            {data.alias_expansion.map((term) => <span key={term} className="shrink-0 whitespace-nowrap rounded-full bg-cream/80 px-2.5 py-1 text-ink">{term}</span>)}
          </>
        )}
      </div>
    </form>
  );

  const results = (
    <section aria-labelledby="results-heading" className="space-y-5">
      {wantGuide && <GuidePanel guide={guide} loading={guideLoading} question={q} />}
      {error && <Notice kind="error">{t("search.failed", { error })}</Notice>}
      <div className="flex flex-wrap items-end justify-between gap-3 pt-1">
        <h2 id="results-heading" className="text-[1.7rem] leading-tight">
          {loading ? t("search.searching") : data ? <span className="tnum">{tn("common.records", data.total)}</span> : t("search.results")}
          {q && <span className="accent block text-ink-muted"> {t("search.for", { q })}</span>}
        </h2>
        <button type="button" className={`btn btn-sm ${filtersOpen || activeFilters ? "" : "btn-secondary"}`} aria-expanded={filtersOpen} aria-controls="filters" onClick={() => setFiltersOpen((v) => !v)}>
          {t("search.filters")}{activeFilters ? ` · ${activeFilters}` : ""}
        </button>
      </div>
      {data?.locality && (
        <p className="text-sm font-semibold text-ink">{t("search.localFirst", { region: data.locality.label })}</p>
      )}
      {data && (
        <p className="text-xs text-ink-muted">
          {data.capped ? t("search.top", { n: fmt.number(data.candidate_limit) }) : ""}<span className="tnum">{fmt.number(data.pins.length)}</span> {t("search.holdersPinned")} · <span className="tnum">{fmt.number(data.online_only_count)}</span> {t("search.onlineOnly")} · <span className="tnum">{fmt.number(data.unknown_location_count)}</span> {t("search.noLocation")}
        </p>
      )}
      <Legend />
      {filtersOpen && <div id="filters" className="plate-white p-4"><FilterRail facets={data?.facets ?? {}} value={filters} onChange={onFilters} unknownLocationCount={data?.unknown_location_count ?? 0} /></div>}
      {data && data.total === 0 && !loading && (<Notice>{t("search.noMatch")} <Link href="/about/sources" className="underline">{t("search.sourcesWeSearch")}</Link> {t("search.weSearch")}</Notice>)}
      {loading && !data && <Skeleton />}
      {data && (
        <div key={sp.toString()} className={`cards-in space-y-3 transition-opacity duration-300 ${loading ? "opacity-50" : ""}`} aria-busy={loading}>
          {data.results.map((r, i) => (<div key={r.id} style={{ "--i": Math.min(i, 10) } as React.CSSProperties}><RecordCard record={r} citationNumbers={citationsByRecord.get(r.id)} /></div>))}
        </div>
      )}
      {alsoCited.length > 0 && (
        <div>
          <h3 className="kicker text-ink-muted">{t("search.alsoCited")}</h3>
          <div className="mt-2 space-y-3">{alsoCited.map((r) => (<RecordCard key={r.id} record={r} citationNumbers={citationsByRecord.get(r.id)} compact />))}</div>
        </div>
      )}
      {data && totalPages > 1 && (
        <nav aria-label={t("search.pagination")} className="flex items-center justify-between text-sm">
          <button type="button" className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => navigate({ page: String(page - 1) })}>{t("search.previous")}</button>
          <span className="tnum text-ink-muted">{t("search.pageOf", { page: fmt.number(page), total: fmt.number(totalPages) })}</span>
          <button type="button" className="btn btn-secondary btn-sm" disabled={page >= totalPages} onClick={() => navigate({ page: String(page + 1) })}>{t("search.next")}</button>
        </nav>
      )}
    </section>
  );

  return (
    <div ref={rootRef} className="pointer-events-none relative">
      <PageSurface tone="flame" />
      {/* ------------------------------------------------------------ desktop: everything floats over the world */}
      {isDesktop && <div className="hidden lg:block" style={{ height: "calc(100svh - var(--header-h))" }}>
        <div data-drawer className="results-askbar">{askBar}</div>
        <div data-drawer className="drawer results-drawer pointer-events-auto">
          <div className="drawer-scroll flex-1 p-5 pr-4" data-lenis-prevent>{results}</div>
        </div>
        <WorldControls className="pointer-events-auto fixed right-[var(--gutter)] top-[calc(var(--header-h)+8px)]" />
        <div data-drawer-side className="pointer-events-auto fixed bottom-4 right-[var(--gutter)]">{data && <OnlinePanel records={data.online_resources} />}</div>
      </div>}

      {/* ------------------------------------------------------------ mobile: the world on top, a sheet that scrolls over it */}
      {!isDesktop && <div className="lg:hidden">
        <div className="px-[var(--gutter)] pt-2">{askBar}</div>
        <div className="h-[44svh]" aria-hidden />
        <div data-drawer className="drawer pointer-events-auto relative mx-2 mb-4 p-4">
          <p className="kicker text-ink-muted">{t("search.pinsAreHolders")}</p>
          <div className="mb-4 mt-2"><WorldControls className="!flex-row flex-wrap" /></div>
          {data && data.online_resources.length > 0 && <div className="mb-4"><OnlinePanel records={data.online_resources} docked={false} /></div>}
          {results}
        </div>
      </div>}
    </div>
  );
}
