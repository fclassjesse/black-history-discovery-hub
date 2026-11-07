import { Suspense } from "react";
import type { Metadata } from "next";
import { AdvancedForm } from "@/components/filters/AdvancedForm";
import { Page, PageIntro } from "@/components/layout/PageIntro";
import { PageSurface } from "@/components/layout/PageSurface";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.advanced") }; }

export default async function AdvancedPage() {
  const { t } = await getT();
  return (
    <>
      <PageSurface tone="chalk" />
      <Page width="max-w-[1100px]">
        <PageIntro eyebrow={t("advanced.eyebrow")} accent={t("advanced.accent")} title={t("advanced.title")} lede={<>{t("advanced.lede1")}<code className="rounded-md bg-white px-1.5 py-0.5 text-sm">{t("advanced.ledeOr")}</code>{t("advanced.lede2")}</>} />
        <Suspense fallback={null}><AdvancedForm /></Suspense>
      </Page>
      <SiteFooter tone="chalk" />
    </>
  );
}
