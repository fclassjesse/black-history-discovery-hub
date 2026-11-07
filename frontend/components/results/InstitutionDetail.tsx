"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { InstitutionCard, RecordCard as RecordCardT } from "@/lib/types";
import { PrecisionBadge } from "@/components/ui/Badges";
import { RecordCard } from "@/components/results/RecordCard";
import { Notice } from "@/components/ui/Notice";
import { Stamp } from "@/components/art/Stamps";
import { tileTone } from "@/components/results/InstitutionTile";
import { Page, PageIntro } from "@/components/layout/PageIntro";
import { detectLanguage, Link, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

/** Institution descriptions stay in their source language; a small badge says so when it differs from the UI language. */
export function SourceLanguageBadge({ text }: { text: string | null | undefined }) {
  const { t, locale } = useT();
  const lang = detectLanguage(text);
  if (!lang || lang === locale) return null;
  return <span className="badge" title={t("institutions.descriptionLanguage")} lang={lang}>{lang === "en" ? t("common.englishOnly") : t("common.frenchOnly")}</span>;
}

export function InstitutionDetail({ slug }: { slug: string }) {
  const { t, tn, locale } = useT();
  const L = useLabels();
  const [inst, setInst] = useState<InstitutionCard | null>(null);
  const [records, setRecords] = useState<{ total: number; results: RecordCardT[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiGet<InstitutionCard>(`/api/institutions/${slug}`).then(setInst).catch((e) => setError(e.message));
    apiGet<{ total: number; results: RecordCardT[] }>(`/api/institutions/${slug}/records?page_size=50&locale=${locale}`).then(setRecords).catch(() => {});
  }, [slug, locale]);
  if (error) return <Page><div className="pt-10"><Notice kind="error">{error}</Notice></div></Page>;
  if (!inst) return <Page><p className="pt-10 text-sm text-ink-muted">{t("common.loading")}</p></Page>;
  const tone = tileTone(slug.length);
  const dark = tone === "plate-moss" || tone === "plate-ink";
  const status = inst.partner_status === "demo" ? t("common.sampleData") : inst.partner_status === "partner" ? t("common.partner") : t("common.linkOnly");
  const descLang = detectLanguage(inst.description);
  return (
    <Page>
      <div className="grid gap-8 lg:grid-cols-[1fr_340px] lg:items-start">
        <PageIntro eyebrow={`${L.kind(inst.kind)} `} accent={`· ${status}`} title={inst.name} lede={inst.description ? <span lang={descLang ?? undefined}>{inst.description}</span> : undefined}>
          <div className="mt-6 flex flex-wrap gap-2">
            <PrecisionBadge precision={inst.location_precision} />
            <SourceLanguageBadge text={inst.description} />
            {inst.latitude != null && <span className="badge tnum">{inst.latitude.toFixed(4)}, {inst.longitude?.toFixed(4)}</span>}
            {inst.latitude != null && <Link href={`/?institution=${inst.slug}`} className="btn btn-sm">{t("institutions.openOnWorld")}</Link>}
          </div>
        </PageIntro>
        <div className={`${tone} halftone grid aspect-square place-items-center p-8 lg:mt-10`} aria-hidden>
          <Stamp kind={inst.kind} className="w-[70%]" />
        </div>
      </div>

      <div className="mt-12 grid gap-6 lg:grid-cols-[1fr_360px]">
        <dl className="plate-white grid gap-x-6 gap-y-3 p-6 text-[0.95rem] sm:grid-cols-[180px_1fr]">
          <dt className="text-ink-muted">{t("institutions.visit")}</dt><dd>{inst.address ?? [inst.city, inst.region, inst.country].filter(Boolean).join(", ") ?? "—"}</dd>
          <dt className="text-ink-muted">{t("institutions.accessRequirements")}</dt><dd>{inst.access_requirements ? <>{inst.access_requirements} <SourceLanguageBadge text={inst.access_requirements} /></> : t("institutions.contactInstitution")}</dd>
          <dt className="text-ink-muted">{t("institutions.collection")}</dt><dd>{inst.collection_summary ? <>{inst.collection_summary} <SourceLanguageBadge text={inst.collection_summary} /></> : "—"}</dd>
          <dt className="text-ink-muted">{t("institutions.contact")}</dt><dd>{inst.contact_email ? <a href={`mailto:${inst.contact_email}`} className="underline">{inst.contact_email}</a> : "—"}{inst.contact_phone ? ` · ${inst.contact_phone}` : ""}</dd>
          <dt className="text-ink-muted">{t("institutions.website")}</dt><dd>{inst.website_url ? <a href={inst.website_url} className="underline" target="_blank" rel="noreferrer">{inst.website_url}</a> : "—"}</dd>
          <dt className="text-ink-muted">{t("institutions.catalogue")}</dt><dd>{inst.catalogue_url ? <a href={inst.catalogue_url} className="underline" target="_blank" rel="noreferrer">{t("institutions.searchCatalogue")}</a> : "—"}</dd>
          <dt className="text-ink-muted">{t("institutions.locationSource")}</dt><dd className="text-sm text-ink-muted">{inst.location_source ?? "—"}</dd>
        </dl>
        <div className={`bubble ${dark ? "bubble-sun" : "bubble-rose"} self-start p-6`}>
          <p className="kicker text-ink-muted">{t("institutions.howToUse")}</p>
          <p className="display mt-2 text-xl">{t("institutions.weIndex")}</p>
          <p className="mt-2 text-sm">{t("institutions.consult")}</p>
        </div>
      </div>

      <section className="mt-14" aria-labelledby="holdings-heading">
        <h2 id="holdings-heading" className="text-[length:var(--text-h2)]">{records ? <span className="tnum">{tn("institutions.indexed", records.total)}</span> : t("institutions.indexedRecords")}</h2>
        {records && records.total === 0 && (
          <div className="mt-4"><Notice>{t("institutions.noRecords")} {inst.partner_status === "partner" ? t("institutions.partnerAdd") : t("institutions.searchOwn")}</Notice></div>
        )}
        <div className="mt-5 grid gap-3 lg:grid-cols-2">{records?.results.map((r) => <RecordCard key={r.id} record={r} compact />)}</div>
      </section>
    </Page>
  );
}
