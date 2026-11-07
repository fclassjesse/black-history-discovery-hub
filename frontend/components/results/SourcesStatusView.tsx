"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { SearchGaps, SourcesStatus } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { useFormat, useT } from "@/lib/i18n";

const STATE_CLS: Record<string, string> = { ok: "badge-ok", unconfigured: "badge", blocked: "badge-danger", error: "badge-danger", untested: "badge" };

export function SourcesStatusView() {
  const { t, raw } = useT();
  const fmt = useFormat();
  const [s, setS] = useState<SourcesStatus | null>(null);
  const [gaps, setGaps] = useState<SearchGaps | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiGet<SourcesStatus>("/api/status/sources").then(setS).catch((e) => setError(e.message));
    apiGet<SearchGaps>("/api/status/search-log").then(setGaps).catch(() => setGaps(null));
  }, []);
  if (error) return <div className="mt-4"><Notice kind="error">{t("sources.couldNotLoad", { error })}</Notice></div>;
  if (!s) return <p className="mt-4 text-sm text-ink-muted" role="status">{t("sources.checking")}</p>;
  const terms = raw<string[]>("sources.termsList");
  return (
    <div className="mt-10 space-y-8">
      <div className="plate-white overflow-auto p-4 sm:p-6"><table className="table">
        <thead><tr><th>{t("sources.connector")}</th><th>{t("sources.state")}</th><th>{t("sources.detail")}</th><th className="text-right">{t("sources.publishedRecords")}</th><th>{t("sources.lastRun")}</th></tr></thead>
        <tbody>
          {s.connectors.map((c) => (
            <tr key={c.name}>
              <td><strong>{c.label}</strong><br /><span className="text-xs text-ink-muted">{c.name} · {c.requires_key ? t("sources.key", { env: c.key_env ?? "" }) : t("sources.keyless")} · {c.docs_url && <a href={c.docs_url} className="underline" target="_blank" rel="noreferrer">{t("sources.docs")}</a>}</span></td>
              <td><span className={`badge ${STATE_CLS[c.state]}`}>{c.state}</span></td>
              <td className="max-w-md">{c.detail}</td>
              <td className="tnum text-right">{fmt.number(c.published_records)}</td>
              <td className="text-xs">{c.last_run ? <>{c.last_run.status} · {fmt.dateTime(c.last_run.started_at)}{c.last_run.query ? ` · “${c.last_run.query}”` : ""}{c.last_run.error ? <><br /><span className="text-danger">{c.last_run.error.slice(0, 160)}</span></> : null}</> : t("common.never")}</td>
            </tr>
          ))}
          <tr><td><strong>{t("sources.partnerUploads")}</strong><br /><span className="text-xs text-ink-muted">{t("sources.partnerSub")}</span></td><td><span className="badge badge-ok">ok</span></td><td>{t("sources.partnerDetail")}</td><td className="tnum text-right">{fmt.number(s.partner_published_records)}</td><td className="text-xs">—</td></tr>
        </tbody>
      </table></div>
      <div className="grid gap-6 sm:grid-cols-2">
        <div className="card">
          <p className="kicker text-ink-muted">{t("sources.ai")}</p>
          <ul className="mt-2 space-y-1 text-sm">
            <li>{t("sources.guide")} {s.ai.guide.configured ? <span className="badge badge-ok">{s.ai.guide.name} · {s.ai.guide.model}</span> : <span className="badge badge-danger">{t("sources.unconfigured")}</span>} {t("sources.guideNote")}</li>
            <li>{t("sources.vision")} {s.ai.vision.configured ? <span className="badge badge-ok">{s.ai.vision.name} · {s.ai.vision.model}</span> : <span className="badge badge-danger">{t("sources.visionUnconfigured")}</span>}</li>
            <li>{t("sources.embeddings")} <span className="badge">{s.ai.embeddings.provider} · {s.ai.embeddings.model}</span> · {t("sources.passages", { n: fmt.number(s.full_text_chunks) })}. {t("sources.embeddingsNote")}</li>
            <li>{t("sources.voice", { browser: s.ai.voice.browser_speech ? t("sources.available") : t("sources.unavailable"), server: s.ai.voice.server_transcription ? t("sources.configured") : t("sources.serverUnconfigured") })} {s.ai.voice.note}</li>
          </ul>
        </div>
        <div className="card">
          <p className="kicker text-ink-muted">{t("sources.mapGeo")}</p>
          <ul className="mt-2 space-y-1 text-sm">
            <li>{t("sources.tiles")} <a href={s.map.tiles} className="underline break-all" target="_blank" rel="noreferrer">{s.map.tiles}</a></li>
            <li>{t("sources.attribution")} {s.map.attribution}</li>
            <li>{t("sources.geocoder", { name: s.map.geocoder })}</li>
          </ul>
        </div>
      </div>
      <div className="card text-sm">
        <p className="kicker text-ink-muted">{t("sources.terms")}</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          {terms.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </div>
      {gaps && (
        <section className="plate-white p-4 sm:p-6" aria-labelledby="gaps-h">
          <h2 id="gaps-h" className="kicker text-ink-muted">{t("sources.gapsTitle", { n: gaps.days })}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("sources.gapsLede")}</p>
          <div className="mt-4 grid gap-6 sm:grid-cols-3">
            <div><h3 className="text-sm font-semibold">{t("sources.mostAsked")}</h3>
              {gaps.top_queries.length === 0 ? <p className="mt-1 text-sm text-ink-muted">{t("sources.nothingLogged")}</p> : <ul className="mt-1 space-y-1 text-sm">{gaps.top_queries.map((g) => <li key={g.query}>“{g.query}” <span className="tnum text-ink-muted">×{g.count}</span>{g.best_result_count === 0 ? <span className="badge badge-danger ml-1">{t("sources.noResults")}</span> : null}</li>)}</ul>}</div>
            <div><h3 className="text-sm font-semibold">{t("sources.zeroResults")}</h3>
              {gaps.zero_result_queries.length === 0 ? <p className="mt-1 text-sm text-ink-muted">{t("common.none")}</p> : <ul className="mt-1 space-y-1 text-sm">{gaps.zero_result_queries.map((g) => <li key={g.query}>“{g.query}” <span className="tnum text-ink-muted">×{g.count}</span></li>)}</ul>}</div>
            <div><h3 className="text-sm font-semibold">{t("sources.abstained")}</h3>
              {gaps.guide_abstained.length === 0 ? <p className="mt-1 text-sm text-ink-muted">{t("common.none")}</p> : <ul className="mt-1 space-y-1 text-sm">{gaps.guide_abstained.map((g) => <li key={g.query}>“{g.query}” <span className="tnum text-ink-muted">×{g.count}</span></li>)}</ul>}</div>
          </div>
          {Object.keys(gaps.latency).length > 0 && (
            <p className="mt-4 text-xs text-ink-muted">{t("sources.latency", { text: Object.entries(gaps.latency).map(([k, v]) => `${k} p50 ${v.p50_ms} ms · p95 ${v.p95_ms} ms (${v.count})`).join(" · ") })}</p>
          )}
        </section>
      )}
    </div>
  );
}
