import type { Metadata } from "next";
import { InstitutionPicker } from "@/components/partner/InstitutionPicker";
import { Page, PageIntro } from "@/components/layout/PageIntro";
import { PageSurface } from "@/components/layout/PageSurface";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.partner") }; }

export default async function PartnerHome() {
  const { t } = await getT();
  return (
    <>
      <PageSurface tone="chalk" />
      <Page width="max-w-[900px]">
        <PageIntro eyebrow={t("partner.eyebrow")} title={t("partner.homeTitle")} lede={t("partner.homeLede")} />
        <InstitutionPicker />
      </Page>
    </>
  );
}
