"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { RecordCard as RecordCardT } from "@/lib/types";
import { AccessBadge, VerificationBadge } from "@/components/ui/Badges";
import { Notice } from "@/components/ui/Notice";
import { Page, PageIntro } from "@/components/layout/PageIntro";
import { Stamp } from "@/components/art/Stamps";
import { Link, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

export function RecordDetail({ id }: { id: string }) {
  const { t, locale } = useT();
  const L = useLabels();
  const [r, setR] = useState<RecordCardT | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { apiGet<RecordCardT>(`/api/records/${id}?locale=${locale}`).then(setR).catch((e) => setError(e.message)); }, [id, locale]);
  if (error) return <Page><div className="pt-10"><Notice kind="error">{error}</Notice></div></Page>;
  if (!r) return <Page><p className="pt-10 text-sm text-ink-muted">{t("record.loading")}</p></Page>;
  const inst = r.institution;
  const physical = r.access_type === "physical" || r.access_type === "both";
  const languages = r.language_labels ?? r.language.map((c) => L.language(c));
  return (
    <Page width="max-w-[1200px]">
      <PageIntro eyebrow={`${L.resourceType(r.resource_type)} `} accent={`· ${r.source_system.replace("_", " ")}`} title={r.title} lede={<>{r.creators.join("; ")}{r.date_text ? <span className="tnum"> · {r.date_text}</span> : ""}</>}>
        <div className="mt-5 flex flex-wrap gap-1.5"><AccessBadge access={r.access_type} /><VerificationBadge verification={r.holding_verification} /><span className="badge">{t("record.rightsBadge", { status: L.rights(r.rights_status) })}</span></div>
        <div className="mt-6 flex flex-wrap gap-2">
          <a href={r.original_url} target="_blank" rel="noreferrer" className="btn">{t("record.viewOriginal")}</a>
          {r.digital_url && r.digital_url !== r.original_url && <a href={r.digital_url} target="_blank" rel="noreferrer" className="btn btn-secondary">{t("common.openOnline")}</a>}
          {physical && inst && <Link href={`/institutions/${inst.slug}`} className="btn btn-secondary">{t("common.visitRequest")}</Link>}
        </div>
      </PageIntro>
      <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_300px]">
        <dl className="plate-white grid gap-x-6 gap-y-3 p-6 text-[0.95rem] sm:grid-cols-[180px_1fr]">
          <dt className="text-ink-muted">{t("record.catalogueDescription")}</dt><dd>{r.description ?? <span className="text-ink-muted">{t("record.noneInSource")}</span>}</dd>
          <dt className="text-ink-muted">{t("record.subjects")}</dt><dd>{r.subjects.length ? r.subjects.join(" · ") : "—"}</dd>
          <dt className="text-ink-muted">{t("record.heldBy")}</dt><dd>{inst ? <Link href={`/institutions/${inst.slug}`} className="underline">{inst.name}</Link> : t("common.unknown")}</dd>
          {r.call_number && (<><dt className="text-ink-muted">{t("record.callNumber")}</dt><dd className="tnum">{r.call_number}{r.shelf_label ? ` · ${r.shelf_label}` : ""}</dd></>)}
          <dt className="text-ink-muted">{t("record.access")}</dt><dd>{r.access_note ?? "—"}</dd>
          <dt className="text-ink-muted">{t("record.rights")}</dt><dd>{r.rights ?? t("record.notStated")}</dd>
          <dt className="text-ink-muted">{t("record.language")}</dt><dd>{languages.join(", ") || "—"}</dd>
          <dt className="text-ink-muted">{t("record.identifiers")}</dt><dd className="tnum break-all">{Object.entries(r.identifiers).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`).join(" · ") || "—"}</dd>
          {r.also_catalogued_at.length > 0 && (<><dt className="text-ink-muted">{t("record.alsoCatalogued")}</dt><dd>{r.also_catalogued_at.map((l) => <a key={l.id} href={l.original_url} className="mr-2 underline" target="_blank" rel="noreferrer">{l.institution_name ?? l.source_system}</a>)}</dd></>)}
          <dt className="text-ink-muted">{t("record.provenance")}</dt><dd className="break-all text-xs">{Object.entries(r.provenance).filter(([, v]) => v).map(([k, v]) => `${k}: ${String(v)}`).join(" · ")}</dd>
        </dl>
        <div className="plate-sun halftone grid aspect-square place-items-center self-start p-8" aria-hidden><Stamp kind={inst?.kind ?? "unknown"} className="w-[70%]" /></div>
      </div>
      {r.excerpts && r.excerpts.length > 0 && (
        <section className="mt-12" aria-labelledby="excerpt-heading">
          <h2 id="excerpt-heading" className="text-[length:var(--text-h2)]">{t("record.excerpts")}</h2>
          <p className="mt-2 text-sm text-ink-muted">{t("record.excerptsNote")}</p>
          <div className="mt-4 space-y-3">
            {r.excerpts.map((e, i) => (
              <blockquote key={i} className="bubble bubble-white p-5 text-[0.95rem] text-ink-2">
                {e.text}… {e.page_url && <a href={e.page_url} className="font-medium underline" target="_blank" rel="noreferrer">{t("record.page", { n: e.page_number ?? "" })}</a>}
              </blockquote>
            ))}
          </div>
        </section>
      )}
    </Page>
  );
}
