import type { Metadata } from "next";
import { SourcesStatusView } from "@/components/results/SourcesStatusView";
import { Page, PageIntro } from "@/components/layout/PageIntro";
import { PageSurface } from "@/components/layout/PageSurface";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.sources") }; }

export default async function SourcesPage() {
  const { t } = await getT();
  return (
    <>
      <PageSurface tone="chalk" />
      <Page width="max-w-[1300px]">
        <PageIntro eyebrow={t("sources.eyebrow")} accent={t("sources.accent")} title={t("sources.title")} lede={<>{t("sources.lede1")}<em>{t("sources.unconfigured")}</em>{t("sources.lede2")}<em>{t("sources.blocked")}</em>{t("sources.lede3")}</>} />
        <SourcesStatusView />
      </Page>
      <SiteFooter tone="chalk" />
    </>
  );
}
