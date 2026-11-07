"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import { useAppSession } from "@/lib/appSession";
import type { Dashboard } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { AppHeader } from "@/components/app/AppHeader";
import { CameraIcon, ChevronIcon, PenIcon, UploadIcon } from "@/components/app/AppIcons";
import { Link, useFormat, useT } from "@/lib/i18n";

function titleOf(v: unknown): string | null {
  return v && typeof v === "object" && "title" in v && typeof (v as { title?: unknown }).title === "string" ? (v as { title: string }).title : null;
}

const QUICK: { href: string; Icon: typeof CameraIcon }[] = [
  { href: "/app/scan", Icon: CameraIcon },
  { href: "/app/upload", Icon: UploadIcon },
  { href: "/app/upload?tab=manual", Icon: PenIcon },
];

export function AppHome() {
  const { t, tn, raw } = useT();
  const fmt = useFormat();
  const { me, membership } = useAppSession();
  const [d, setD] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { apiGet<Dashboard>(`${base(membership.institution_id)}/dashboard`).then(setD).catch((e) => setError(e.message)); }, [membership.institution_id]);
  const counts = d?.records_by_status;
  const waiting = (counts?.draft ?? 0) + (counts?.in_review ?? 0);
  const first = me.display_name.split(" ")[0] || t("app.home.there");
  const quick = raw<{ title: string; sub: string }[]>("app.home.quick");
  return (
    <div className="app-screen">
      <AppHeader eyebrow={t("app.home.eyebrow")} title={t("app.home.hi", { name: first })} line={d ? (waiting ? tn("app.home.waiting", waiting) : t("app.home.nothingWaiting")) : t("app.home.loadingShelf")} mood={waiting ? "pointing" : "celebrate"} />
      {error && <Notice kind="error">{error}</Notice>}
      <section aria-label={t("app.home.byStatus")} className="grid grid-cols-2 gap-3">
        <Link href="/app/review?status=published" className="tile tile-moss col-span-2 flex items-end justify-between">
          <span><span className="kicker text-cream/70">{t("app.home.onWorld")}</span><span className="display tnum block text-5xl">{counts ? fmt.number(counts.published) : "–"}</span></span>
          <span className="text-sm text-cream/80">{t("app.home.published")}</span>
        </Link>
        <Link href="/app/review?status=draft" className="tile tile-sun"><span className="kicker">{t("app.home.drafts")}</span><span className="display tnum block text-4xl">{counts ? fmt.number(counts.draft) : "–"}</span></Link>
        <Link href="/app/review?status=in_review" className="tile tile-rose"><span className="kicker">{t("app.home.inReview")}</span><span className="display tnum block text-4xl">{counts ? fmt.number(counts.in_review) : "–"}</span></Link>
      </section>
      <section aria-labelledby="quick">
        <h2 id="quick" className="kicker text-ink-muted">{t("app.home.addRecords")}</h2>
        <div className="mt-2 grid gap-2">
          {QUICK.map(({ href, Icon }, i) => (
            <Link key={href} href={href} className="tile flex items-center gap-3">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-chalk"><Icon /></span>
              <span className="min-w-0 flex-1"><span className="display block text-lg leading-tight">{quick[i]?.title}</span><span className="block text-sm text-ink-muted">{quick[i]?.sub}</span></span>
              <ChevronIcon className="shrink-0 text-ink-muted" />
            </Link>
          ))}
        </div>
      </section>
      {d && (
        <section aria-labelledby="recent" className="tile">
          <h2 id="recent" className="kicker text-ink-muted">{t("app.home.recent")}</h2>
          {d.recent_audit.length === 0 ? <p className="mt-2 text-sm text-ink-muted">{t("common.nothingYet")}</p> : (
            <ul className="hairline-list mt-1 text-sm">
              {d.recent_audit.slice(0, 6).map((a) => (
                <li key={a.id} className="py-2">
                  <span className="font-medium">{a.action.replace(/[._]/g, " ")}</span>
                  {titleOf(a.after) && <span className="text-ink-2"> · {titleOf(a.after)}</span>}
                  <span className="tnum block text-xs text-ink-muted">{fmt.dateTime(a.at)}{a.actor ? ` · ${a.actor}` : ""}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
