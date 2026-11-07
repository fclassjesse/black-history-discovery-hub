"use client";

import { useEffect, useState } from "react";
import { useSelection } from "@/lib/store";
import { character } from "@/lib/character";
import type { Citation, GuideResponse } from "@/lib/types";
import { BCP47, useT, type Translator } from "@/lib/i18n";

const SHORT_SENTENCES = 2;

function renderAnswer(answer: string, citations: Citation[], t: Translator["t"]) {
  const parts = answer.split(/(\[\d+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/);
    if (!m) return <span key={i}>{p}</span>;
    const n = Number(m[1]);
    const c = citations.find((x) => x.n === n);
    if (!c) return <span key={i}>{p}</span>;
    return (
      <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" className="cite" title={t("guide.citeTitle", { title: c.title, institution: c.institution ?? t("guide.sourceFallback") })} aria-label={t("guide.citationAria", { n, title: c.title })}>{n}</a>
    );
  });
}

/** Split an answer into sentences, keeping the [n] markers attached to the sentence they close. */
function sentences(text: string): string[] {
  return text.match(/[^.!?]+[.!?]+(?:\s*\[\d+\])*\s*|[^.!?]+$/g)?.map((s) => s.trim()).filter(Boolean) ?? [text];
}

/** Nova's bubble: a two-sentence answer, the sources right under it, the rest behind "more". */
export function GuidePanel({ guide, loading, question }: { guide: GuideResponse | null; loading: boolean; question: string }) {
  const { t, locale } = useT();
  const { setHighlights, selectRecord } = useSelection();
  const [speaking, setSpeaking] = useState(false);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (guide) setHighlights(guide.highlight_record_ids, guide.map_focus_institution_ids);
  }, [guide, setHighlights]);
  useEffect(() => {
    if (loading) character.set("thinking", { text: question });
    else if (guide?.abstain) character.set("abstain", { text: guide.abstain_reason ?? undefined });
    else if (guide) character.set("speaking", { text: guide.answer, citations: guide.citations.length, institution: guide.citations[0]?.institution ?? null });
  }, [loading, guide, question]);
  useEffect(() => () => { if (typeof window !== "undefined") window.speechSynthesis?.cancel(); }, []);

  if (!question) return null;
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
  const speak = () => {
    if (!guide || !canSpeak) return;
    if (speaking) { window.speechSynthesis.cancel(); setSpeaking(false); character.set("idle"); return; }
    const u = new SpeechSynthesisUtterance((guide.abstain ? guide.abstain_reason ?? "" : guide.answer).replace(/\[\d+\]/g, ""));
    u.lang = BCP47[locale];
    u.onend = () => { setSpeaking(false); character.set("idle"); };
    setSpeaking(true);
    character.set("speaking", { text: guide.answer }, 120000);
    window.speechSynthesis.speak(u);
  };

  const all = guide ? sentences(guide.answer) : [];
  const isLong = all.length > SHORT_SENTENCES;
  const shown = expanded || !isLong ? guide?.answer ?? "" : all.slice(0, SHORT_SENTENCES).join(" ");
  const tone = guide?.abstain ? "bubble-sun" : "bubble-white";

  return (
    <section aria-labelledby="guide-heading" aria-busy={loading} className={`bubble ${tone} p-5 sm:p-6`}>
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="guide-heading" className="text-xl">{t("guide.novaSays")}{guide?.follow_up && !loading ? <span className="badge ml-2 align-middle text-xs" title={t("guide.followUpTitle")}>{t("guide.followUp")}</span> : null}</h2>
        {!loading && guide && canSpeak && !guide.abstain && (
          <button type="button" className="text-xs underline" onClick={speak} aria-pressed={speaking}>{speaking ? t("guide.stop") : t("guide.readAloud")}</button>
        )}
      </div>
      {loading && (
        <p className="mt-2 flex items-center gap-2 text-sm text-ink-muted" role="status">
          <span className="inline-flex gap-1" aria-hidden><span className="think-dot inline-block h-2 w-2 rounded-full bg-ink" /><span className="think-dot inline-block h-2 w-2 rounded-full bg-ink" /><span className="think-dot inline-block h-2 w-2 rounded-full bg-ink" /></span>
          {t("guide.reading")}
        </p>
      )}
      {!loading && guide && (
        <div className="mt-3 space-y-4">
          {guide.abstain ? (
            <p className="text-[1rem] leading-snug"><span className="display">{t("guide.wontGuess")}</span> {guide.abstain_reason}{guide.answer && <span> {renderAnswer(guide.answer, guide.citations, t)}</span>}</p>
          ) : (
            <p className="text-[1.02rem] leading-snug">
              {renderAnswer(shown, guide.citations, t)}
              {isLong && <button type="button" className="ml-1 text-sm underline" onClick={() => setExpanded((v) => !v)}>{expanded ? t("guide.less") : t("guide.more")}</button>}
            </p>
          )}
          {guide.citations.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label={t("guide.sources")}>
              {guide.citations.map((c) => (
                <li key={`${c.n}-${c.evidence_id}`} className="flex max-w-full items-stretch overflow-hidden rounded-full border-[1.5px] border-ink bg-cream text-xs">
                  <a href={c.url} target="_blank" rel="noopener noreferrer" className="flex min-w-0 items-center gap-2 py-1.5 pl-1.5 pr-2.5 no-underline hover:bg-sun" title={`${t("guide.openSource", { title: c.title })}${c.page_number != null ? `, ${t("guide.page", { n: c.page_number })}` : ""}`}>
                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-sun font-bold">{c.n}</span>
                    <span className="truncate font-medium">{c.title}</span>
                    <span aria-hidden>↗</span>
                  </a>
                  <button type="button" className="border-l-[1.5px] border-ink/30 px-2 text-ink-muted hover:bg-chalk" title={t("guide.showRecordTitle")} aria-label={t("guide.showRecordAria", { n: c.n })} onClick={() => selectRecord(c.record_id, c.institution_id)}>↓</button>
                </li>
              ))}
            </ul>
          )}
          {guide.validation_error && <p className="text-xs text-ink-muted">{t("guide.validatorNote", { error: guide.validation_error })}</p>}
        </div>
      )}
    </section>
  );
}
