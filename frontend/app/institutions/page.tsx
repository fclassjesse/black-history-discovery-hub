import type { Metadata } from "next";
import { InstitutionGrid } from "@/components/results/InstitutionStrip";
import { Page, PageIntro } from "@/components/layout/PageIntro";
import { PageSurface } from "@/components/layout/PageSurface";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.institutions") }; }

export default async function InstitutionsPage() {
  const { t } = await getT();
  return (
    <>
      <PageSurface tone="chalk" />
      <Page>
        <PageIntro eyebrow={t("institutions.eyebrow")} accent={t("institutions.accent")} title={t("institutions.title")} lede={t("institutions.lede")} />
        <InstitutionGrid />
      </Page>
      <SiteFooter tone="chalk" />
    </>
  );
}
