"use client";

import { Link, useT } from "@/lib/i18n";

export function SiteFooter({ tone = "flame" }: { tone?: "flame" | "chalk" }) {
  const { t } = useT();
  return (
    <footer className={`${tone === "flame" ? "bg-flame text-ink" : "bg-chalk text-ink"} pointer-events-auto relative z-10 px-[var(--gutter)] pb-6 pt-[var(--space-section)]`}>
      <div className="mx-auto max-w-[1600px]">
        <div className="plate-stone halftone p-5 sm:p-7">
          <p className="eyebrow text-white"><span className="sq" /> {t("footer.liveStatus")}</p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <p className="display max-w-2xl text-[length:var(--text-h3)] text-white">{t("footer.statusLine")}</p>
            <Link href="/about/sources" className="btn btn-pill-chalk btn-lg ml-auto">{t("footer.seeSources")}</Link>
          </div>
        </div>
        <div className="plate grid gap-8 p-5 sm:grid-cols-3 sm:p-7" style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
          <div>
            <p className="display text-xl">{t("meta.siteName")}</p>
            <p className="mt-2 text-sm text-ink-2">{t("footer.builtFor")}</p>
          </div>
          <div className="text-sm">
            <p className="kicker">{t("footer.sourcesAttribution")}</p>
            <ul className="mt-2 space-y-1 text-ink-2">
              <li>{t("footer.sourcesList")}</li>
              <li>{t("footer.tiles")} © <a href="https://openfreemap.org" className="underline">OpenFreeMap</a> · © <a href="https://www.openmaptiles.org/" className="underline">OpenMapTiles</a> · © <a href="https://www.openstreetmap.org/copyright" className="underline">{t("footer.contributors")}</a></li>
              <li>{t("footer.geocoding")}</li>
            </ul>
          </div>
          <div className="text-sm">
            <p className="kicker">{t("footer.accessibility")}</p>
            <p className="mt-2 text-ink-2">{t("footer.a11yText")}</p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
              <Link href="/institutions" className="underline">{t("footer.institutions")}</Link>
              <Link href="/about/sources" className="underline">{t("footer.sources")}</Link>
              <Link href="/app" className="underline">{t("footer.app")}</Link>
              <Link href="/partner" className="underline">{t("footer.partner")}</Link>
              <Link href="/privacy" className="underline">{t("footer.privacy")}</Link>
              <a href="/api-docs" className="underline">{t("common.apiDocs")}</a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
