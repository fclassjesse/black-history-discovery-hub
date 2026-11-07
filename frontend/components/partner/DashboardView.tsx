"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import type { Dashboard } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { PrecisionBadge } from "@/components/ui/Badges";
import { Link, useFormat, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

export function DashboardView({ institutionId }: { institutionId: string }) {
  const { t, tn } = useT();
  const L = useLabels();
  const fmt = useFormat();
  const [d, setD] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { apiGet<Dashboard>(`${base(institutionId)}/dashboard`).then(setD).catch((e) => setError(e.message)); }, [institutionId]);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!d) return <p className="text-sm text-ink-muted">{t("partner.dashboard.loading")}</p>;
  const root = `/partner/${institutionId}`;
  return (
    <div className="space-y-8">
      <div>
        <p className="eyebrow">{t("partner.dashboard.eyebrow")}</p>
        <h1 className="mt-1 text-[length:var(--text-h1)]">{d.institution.name}</h1>
        <div className="mt-2 flex flex-wrap gap-2 text-sm"><PrecisionBadge precision={d.institution.location_precision} />{d.institution.partner_status === "demo" && <span className="badge badge-demo">{t("common.sampleData")}</span>}</div>
      </div>
      <section aria-labelledby="counts" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <h2 id="counts" className="sr-only">{t("partner.dashboard.byStatus")}</h2>
        {(["draft", "in_review", "published", "withdrawn"] as const).map((s) => (
          <Link key={s} href={`${root}/records?status=${s}`} className="card no-underline hover:no-underline">
            <p className="eyebrow">{L.status(s)}</p>
            <p className="display tnum text-3xl">{fmt.number(d.records_by_status[s])}</p>
          </Link>
        ))}
      </section>
      <section className="grid gap-6 md:grid-cols-2">
        <div className="card">
          <h2 className="text-lg">{t("partner.dashboard.sync")}</h2>
          <dl className="mt-2 text-sm">
            <dt className="text-ink-muted">{t("partner.dashboard.mode")}</dt><dd>{d.sync.mode}</dd>
            <dt className="mt-2 text-ink-muted">{t("partner.dashboard.lastImport")}</dt><dd>{d.sync.last_import ? fmt.dateTime(d.sync.last_import) : t("partner.dashboard.noneYet")}</dd>
            <dt className="mt-2 text-ink-muted">{t("partner.dashboard.api")}</dt><dd><a href="/api-docs" className="underline">{t("partner.dashboard.openapi")}</a> · {t("partner.dashboard.template")} <a href="/partner-import-template.csv" className="underline" download>partner-import-template.csv</a></dd>
          </dl>
          {d.jobs.length > 0 && (<><h3 className="eyebrow mt-4">{t("partner.dashboard.jobs")}</h3><ul className="mt-1 text-xs">{d.jobs.map((j) => <li key={j.id}>{j.kind} · <span className={j.status === "failed" ? "text-danger" : ""}>{j.status}</span> · {fmt.dateTime(j.created_at)}{j.error && <span className="text-danger"> — {j.error}</span>}</li>)}</ul></>)}
        </div>
        <div className="card">
          <h2 className="text-lg">{t("partner.dashboard.recentImports")}</h2>
          {d.import_batches.length === 0 ? <p className="mt-2 text-sm text-ink-muted">{t("partner.dashboard.noImports")} <Link href={`${root}/import`} className="underline">{t("partner.dashboard.importCsv")}</Link>.</p> : (
            <ul className="hairline-list mt-2 text-sm">{d.import_batches.map((b) => <li key={b.id} className="py-2"><Link href={`${root}/import?batch=${b.id}`} className="underline">{b.filename ?? b.kind}</Link> · {b.status} · {tn("common.rows", b.row_count)} · {tn("common.errors", b.error_count)} · {tn("common.duplicates", b.duplicate_count)} · {tn("common.drafts", b.committed_count)}</li>)}</ul>
          )}
        </div>
      </section>
      <section className="card">
        <h2 className="text-lg">{t("partner.dashboard.audit")}</h2>
        {d.recent_audit.length === 0 ? <p className="mt-2 text-sm text-ink-muted">{t("common.nothingYet")}</p> : (
          <div className="mt-2 overflow-auto"><table className="table"><thead><tr><th>{t("partner.dashboard.when")}</th><th>{t("partner.dashboard.who")}</th><th>{t("partner.dashboard.action")}</th><th>{t("partner.dashboard.entity")}</th></tr></thead>
            <tbody>{d.recent_audit.map((a) => <tr key={a.id}><td className="tnum whitespace-nowrap">{fmt.dateTime(a.at)}</td><td>{a.actor}</td><td>{a.action}</td><td className="text-xs">{a.entity_type} {a.entity_id?.slice(0, 8)}{a.after && typeof a.after === "object" && "title" in (a.after as object) ? ` · ${(a.after as { title?: string }).title}` : ""}</td></tr>)}</tbody>
          </table></div>
        )}
        <Link href={`${root}/records`} className="mt-2 inline-block text-sm underline">{t("partner.dashboard.fullAudit")}</Link>
      </section>
    </div>
  );
}
