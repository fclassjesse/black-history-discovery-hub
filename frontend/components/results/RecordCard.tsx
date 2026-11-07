"use client";

import { useSelection } from "@/lib/store";
import type { RecordCard as RecordCardT } from "@/lib/types";
import { AccessBadge, VerificationBadge } from "@/components/ui/Badges";
import { Stamp } from "@/components/art/Stamps";
import { Link, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

export function RecordCard({ record, citationNumbers, compact = false }: { record: RecordCardT; citationNumbers?: number[]; compact?: boolean }) {
  const { t } = useT();
  const L = useLabels();
  const { selectedRecordId, highlightRecordIds, selectRecord, hoverRecord } = useSelection();
  const selected = selectedRecordId === record.id;
  const highlighted = highlightRecordIds.includes(record.id);
  const inst = record.institution;
  const physical = record.access_type === "physical" || record.access_type === "both";
  const online = record.access_type === "online" || record.access_type === "both";
  const languages = record.language_labels ?? record.language.map((c) => L.language(c));
  return (
    <article
      id={`record-${record.id}`}
      className={`card ${selected ? "card-selected" : ""} ${highlighted ? "card-highlight" : ""}`}
      onMouseEnter={() => hoverRecord(record.id)}
      onMouseLeave={() => hoverRecord(null)}
      aria-current={selected ? "true" : undefined}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-chalk" aria-hidden><Stamp kind={inst?.kind ?? "unknown"} className="h-9 w-9" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {citationNumbers?.map((n) => <span key={n} className="grid h-6 min-w-6 place-items-center rounded-md bg-sun px-1 text-xs font-bold" aria-label={t("record.citedAs", { n })}>{n}</span>)}
            <AccessBadge access={record.access_type} />
            <VerificationBadge verification={record.holding_verification} />
          </div>
          <h3 className="mt-2 text-[1.3rem] leading-tight">
            <button type="button" className="text-left hover:text-flame-deep" onClick={() => selectRecord(record.id, inst?.id ?? null)} aria-pressed={selected}>{record.title}</button>
          </h3>
          <p className="mt-1.5 text-sm text-ink-2">
            {record.creators.length > 0 && <span>{record.creators.slice(0, 3).join("; ")} · </span>}
            {record.date_text && <span className="tnum">{record.date_text} · </span>}
            <span>{L.resourceType(record.resource_type)}</span>
            {languages.length > 0 && <span className="text-ink-muted"> · {languages.join(", ")}</span>}
          </p>
        </div>
      </div>
      {!compact && record.summary && <p className="mt-3 line-clamp-2 text-[0.95rem] leading-relaxed text-ink-2">{record.summary}</p>}
      <dl className="mt-3 grid gap-x-5 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="text-ink-muted">{t("record.heldBy")}</dt>
        <dd>
          {inst ? (<><Link href={`/institutions/${inst.slug}`} className="font-medium underline">{inst.name}</Link>{inst.city && <span className="text-ink-muted"> · {inst.city}{inst.region ? `, ${inst.region}` : ""}</span>}</>) : <span className="text-ink-muted">{t("record.unknownHolder")}</span>}
        </dd>
        {record.call_number && (<><dt className="text-ink-muted">{t("record.callNumber")}</dt><dd className="tnum">{record.call_number}{record.shelf_label ? ` · ${record.shelf_label}` : ""}</dd></>)}
        {record.access_note && (<><dt className="text-ink-muted">{t("record.access")}</dt><dd>{record.access_note}</dd></>)}
        {record.also_catalogued_at.length > 0 && (<><dt className="text-ink-muted">{t("record.alsoCatalogued")}</dt><dd>{record.also_catalogued_at.map((l, i) => (<span key={l.id}>{i > 0 && "; "}<a href={l.original_url} className="underline" target="_blank" rel="noreferrer">{l.institution_name ?? l.source_system}</a></span>))}</dd></>)}
      </dl>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <a href={record.original_url} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">{t("common.source")}</a>
        {online && record.digital_url && record.digital_url !== record.original_url && (<a href={record.digital_url} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">{t("common.openOnline")}</a>)}
        {physical && inst && (<Link href={`/institutions/${inst.slug}`} className="btn btn-sm">{t("common.visit")}</Link>)}
        <Link href={`/records/${record.id}`} className="btn btn-quiet btn-sm">{t("common.details")}</Link>
      </div>
    </article>
  );
}
